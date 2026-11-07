"""Offline tests for the conversation exporter's pure helpers (no API, no network).

The network paths (list_conversations / pull_events) are exercised by the scheduled
watcher-session-log.yml workflow; these tests cover the logic that classifies owner
text vs automation templates and redacts secrets.
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("export_conversations", ROOT / "scripts" / "export_conversations.py")
ex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ex)


def _user_event(text):
    return {"source": "user", "llm_message": {"role": "user", "content": [{"type": "text", "text": text}]}}


def test_owner_text_returns_verbatim_words():
    ev = _user_event("delete everything in thisrepo")
    assert ex.owner_text(ev) == "delete everything in thisrepo"


def test_owner_text_preserves_garbled_speech():
    raw = "why there is something in a sandbox it should be published on main and working"
    assert ex.owner_text(_user_event(raw)) == raw


def test_owner_text_rejects_automation_templates():
    for tmpl in ("## Cloned Repositories\n\nfoo", "You are requested to fix issue #240",
                 "[Stop hook feedback] x", "Read the attached WATCHER.md in full"):
        assert ex.owner_text(_user_event(tmpl)) is None


def test_owner_text_ignores_non_user_sources():
    assert ex.owner_text({"source": "environment", "llm_message": {"role": "user", "content": "x"}}) is None
    assert ex.owner_text({"source": "user"}) is None


def test_is_automation_conversation():
    assert ex.is_automation_conversation({"title": "Openhands loop — 2026-11-01 12:02:01 UTC"})
    assert ex.is_automation_conversation({"title": "GitHub Issue #240: Watcher is alive"})
    assert not ex.is_automation_conversation({"title": "Watcher"})


def test_redact_removes_real_secret_shapes():
    assert ex.redact("token gAAAAA" + "A" * 30) == "token [REDACTED-FERNET]"
    assert ex.redact("key sk-" + "a" * 30) == "key [REDACTED-OPENAI]"
    assert ex.redact("ghp_" + "b" * 30) == "[REDACTED-GITHUB]"
    assert "AIza" not in ex.redact("x AIza" + "c" * 35 + " y")
    # A token embedded in a git URL is redacted (the GitHub-token rule fires first).
    red = ex.redact("https://ghp_" + "d" * 30 + "@github.com/x")
    assert "ghp_" not in red and red.endswith("@github.com/x")


def test_redact_leaves_plain_doc_text_alone():
    # Documentation that merely names a pattern must survive (no false redaction).
    assert ex.redact("starts with `gAAAAA`") == "starts with `gAAAAA`"


def test_text_of_flattens_blocks():
    assert ex.text_of([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]) == "ab"
    assert ex.text_of("plain") == "plain"


def test_render_is_deterministic():
    # The manifest hashes the rendered section, so identical input must render identically;
    # otherwise the scheduled export opens a noise PR on every run.
    c = {"id": "x", "title": "T", "created_at": "2026-11-01T00:00:00Z", "sandbox_status": "PAUSED"}
    evs = [_user_event("hello"), _user_event("world")]
    assert ex.render_conversation(c, evs) == ex.render_conversation(c, evs)


def test_rendered_lines_have_no_trailing_whitespace():
    # Multi-paragraph owner text becomes a blockquote; blank lines must render as a bare ">",
    # never "> " with a trailing space, which git diff --check rejects.
    c = {"id": "x", "title": "T", "created_at": "2026-11-01T00:00:00Z", "sandbox_status": "PAUSED"}
    evs = [_user_event("first para\n\nsecond para\n\n")]
    out = ex.render_conversation(c, evs)
    assert not any(ln != ln.rstrip() for ln in out.split("\n")), "trailing whitespace in render"
    assert "\n>\n" in out


def test_main_export_is_deterministic(tmp_path, monkeypatch):
    """Two full export runs over the same conversations produce byte-identical files.

    This is the property the scheduled workflow depends on: if it did not hold, every run
    would open a noise PR. The API is stubbed with a fixed conversation that carries
    volatile fields the renderer ignores (updated_at, sandbox id).
    """
    import json

    convo = {"id": "abc123", "title": "Watcher", "created_at": "2026-11-01T03:22:19Z",
             "updated_at": "2026-11-01T18:00:00Z", "sandbox_status": "PAUSED",
             "sandbox_id": "volatile-xyz"}
    events = [_user_event("delete everything in thisrepo"), _user_event("carry on")]
    monkeypatch.setattr(ex, "KEY", "test-key")  # main() bails if the module KEY is empty
    monkeypatch.setattr(ex, "list_conversations", lambda: [convo])
    monkeypatch.setattr(ex, "pull_events", lambda cid: (events, 1))

    def run(out, raw):
        monkeypatch.setattr("sys.argv", ["export_conversations.py", "--date", "2026-11-01",
                                         "--out", str(out), "--raw-dir", str(raw)])
        assert ex.main() == 0
        return (out / "2026-11-01.md").read_bytes(), (out / "2026-11-01.manifest.json").read_bytes()

    md1, man1 = run(tmp_path / "a", tmp_path / "ra")
    md2, man2 = run(tmp_path / "b", tmp_path / "rb")
    assert md1 == md2
    assert man1 == man2
    assert json.loads(man1)["conversations"][0]["log_sha256"] == json.loads(man2)["conversations"][0]["log_sha256"]


def test_check_leaks_flags_each_secret_shape():
    for sample, kind in [
        ("gAAAAA" + "A" * 30, "fernet"),
        ("sk-" + "a" * 30, "openai-sk"),
        ("ghp_" + "b" * 30, "github-token"),
        ("AIza" + "c" * 35, "google-key"),
        ("AQ." + "d" * 45, "google-oauth"),
        ("-----BEGIN RSA PRIVATE KEY-----\n" + "M" * 40 + "\n-----END RSA PRIVATE KEY-----", "private-key"),
    ]:
        hits = ex.check_leaks(sample)
        assert hits and hits[0][0] == kind, (sample, hits)


def test_check_leaks_ignores_a_lone_pem_header_in_prose():
    # A doc line that names the pattern without a real key body is not a secret.
    assert ex.check_leaks("literal `-----BEGIN PRIVATE KEY-----` in prose") == []


def test_check_leaks_clean_on_ordinary_text():
    assert ex.check_leaks("see docs/WORKFLOW.md and brain#292 comment 6712989336") == []
    # The doc line that merely names the pattern must not trip the scanner.
    assert ex.check_leaks("starts with `gAAAAA`") == []


def test_main_fails_closed_when_a_secret_survives(tmp_path, monkeypatch):
    """If a secret-shaped value reaches the rendered output, the run aborts with exit 2.

    redact() is neutralised so the secret survives on purpose; the leak scan must catch it.
    """
    convo = {"id": "leaky", "title": "Watcher", "created_at": "2026-11-01T03:22:19Z",
             "sandbox_status": "PAUSED"}
    events = [_user_event("token ghp_" + "e" * 30)]
    monkeypatch.setattr(ex, "KEY", "test-key")
    monkeypatch.setattr(ex, "list_conversations", lambda: [convo])
    monkeypatch.setattr(ex, "pull_events", lambda cid: (events, 1))
    monkeypatch.setattr(ex, "redact", lambda t: t)  # sabotage: let the secret through
    monkeypatch.setattr("sys.argv", ["export_conversations.py", "--date", "2026-11-01",
                                     "--out", str(tmp_path / "o"), "--raw-dir", str(tmp_path / "r")])
    assert ex.main() == 2


def test_main_exit_zero_is_leak_clean(tmp_path, monkeypatch):
    convo = {"id": "ok", "title": "Watcher", "created_at": "2026-11-01T03:22:19Z",
             "sandbox_status": "PAUSED"}
    events = [_user_event("carry on"), _user_event("token ghp_" + "f" * 30)]
    monkeypatch.setattr(ex, "KEY", "test-key")
    monkeypatch.setattr(ex, "list_conversations", lambda: [convo])
    monkeypatch.setattr(ex, "pull_events", lambda cid: (events, 1))
    monkeypatch.setattr("sys.argv", ["export_conversations.py", "--date", "2026-11-01",
                                     "--out", str(tmp_path / "o"), "--raw-dir", str(tmp_path / "r")])
    assert ex.main() == 0
    text = (tmp_path / "o" / "2026-11-01.md").read_text()
    assert "ghp_" not in text and "[REDACTED-GITHUB]" in text


def test_scan_mode_reports_and_exits_nonzero(tmp_path, monkeypatch, capsys):
    bad = tmp_path / "leak.md"
    bad.write_text("oops sk-" + "z" * 30)
    monkeypatch.setattr("sys.argv", ["export_conversations.py", "--scan", str(bad)])
    assert ex.main() == 2
    assert "FAIL" in capsys.readouterr().out


def test_scan_mode_clean_exits_zero(tmp_path, monkeypatch, capsys):
    ok = tmp_path / "clean.md"
    ok.write_text("nothing secret here")
    monkeypatch.setattr("sys.argv", ["export_conversations.py", "--scan", str(ok)])
    assert ex.main() == 0


def test_verify_canary_passes(capsys):
    assert ex.verify_canary() == 0
    assert "canary ok" in capsys.readouterr().out


def test_verify_canary_fails_when_redaction_is_sabotaged(monkeypatch):
    monkeypatch.setattr(ex, "redact", lambda t: t)
    assert ex.verify_canary() == 2


def test_cursor_roundtrip(tmp_path):
    p = str(tmp_path / "cursor.json")
    assert ex.read_cursor(p) == {}
    ex.write_cursor(p, "2026-11-07", [{"id": "a", "log_sha256": "h1"}])
    cur = ex.read_cursor(p)
    assert cur["last_date"] == "2026-11-07" and cur["conversations"] == {"a": "h1"}
    assert cur["last_run_utc"].endswith("Z")

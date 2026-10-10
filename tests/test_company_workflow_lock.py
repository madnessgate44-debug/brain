from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_company_workflow_lease_release_matches_exact_run_id():
    workflow = (ROOT / ".github/workflows/brain-chat-company-workflow.yml").read_text(
        encoding="utf-8"
    )

    assert "const leaseRun = ((commit.data.message || '').match(/(?:^|\\\\s)run=(\\\\d+)(?:\\\\s|$)/) || [])[1];" in workflow
    assert "if (leaseRun === String(context.runId)) {" in workflow
    assert ".includes('run=' + context.runId)" not in workflow

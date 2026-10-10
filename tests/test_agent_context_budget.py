"""Prompt-budget regression tests for role-specific repository evidence."""

from brain.company.agent_runner import AgentOutputError, SpecialistAgentRunner, _prepare_prompt_evidence, _select_source_contents


def _snapshot(source_contents):
    paths = list(source_contents)
    return {
        "repository": "owner/repository",
        "default_branch": "main",
        "base_commit": "abc123",
        "files": [{"path": path, "size": len(content)} for path, content in source_contents.items()],
        "source_contents": source_contents,
        "source_manifest": {
            "candidate_count": len(paths),
            "read_count": len(paths),
            "coverage_complete": True,
            "candidate_paths": paths,
            "read_paths": paths,
            "failed_paths": {},
            "omitted_by_aggregate_budget": [],
            "aggregate_bytes_read": sum(len(value) for value in source_contents.values()),
        },
    }


def test_non_implementation_roles_receive_a_bounded_source_index_not_all_source_text():
    contents = {
        f"src/module_{index}.py": f"module {index}\n" * 1000
        for index in range(240)
    }
    evidence = {"repository_snapshot": _snapshot(contents)}
    prepared = _prepare_prompt_evidence("product_owner", "Define the product requirements.", evidence)

    snapshot = prepared["repository_snapshot"]
    assert "source_contents" not in snapshot
    assert len(snapshot["file_index"]) <= 160
    assert snapshot["source_manifest"]["candidate_count"] == 240
    assert "source_contents" in evidence["repository_snapshot"]


def test_developer_receives_complete_relevant_files_within_the_source_budget():
    contents = {
        "docs/BRAIN_RUNTIME_VERIFICATION.md": "target evidence\n" * 1000,
        ".github/workflows/brain-chat-runtime-check.yml": "runtime check\n" * 1200,
        "src/unrelated_feature.py": "unrelated implementation\n" * 2000,
    }
    request = (
        "Create or update only docs/BRAIN_RUNTIME_VERIFICATION.md. "
        "Verify the Gemini chat runtime workflow and report evidence."
    )
    prepared = _prepare_prompt_evidence(
        "developer",
        request,
        {"repository_snapshot": _snapshot(contents)},
    )

    snapshot = prepared["repository_snapshot"]
    selected = snapshot["source_contents"]
    assert "docs/BRAIN_RUNTIME_VERIFICATION.md" in selected
    assert ".github/workflows/brain-chat-runtime-check.yml" in selected
    assert "src/unrelated_feature.py" not in selected
    assert sum(len(value) for value in selected.values()) <= 90000
    assert snapshot["source_selection"]["selected_file_count"] == len(selected)


def test_review_and_quality_roles_do_not_receive_duplicate_full_change_set_contents():
    evidence = {
        "change_set": {
            "summary": "Add a report",
            "files": [{"path": "docs/report.md", "content": "x" * 100000}],
        },
        "actual_diff": "d" * 80000,
        "changed_files": ["docs/report.md"],
    }

    reviewer = _prepare_prompt_evidence("code_reviewer", "Review the change.", evidence)
    qa = _prepare_prompt_evidence("qa_engineer", "Verify the change.", evidence)

    assert reviewer["change_set"]["files"] == [
        {"path": "docs/report.md", "content_chars": 100000}
    ]
    assert len(reviewer["actual_diff"]) < 61000
    assert reviewer["actual_diff_truncated"] is True
    assert reviewer["diff_review_blocked"] is True
    assert len(qa["actual_diff"]) < 31000
    assert qa["actual_diff_truncated"] is True
    assert qa["diff_review_blocked"] is True
    assert "content" not in reviewer["change_set"]["files"][0]
    assert "content" in evidence["change_set"]["files"][0]


def test_developer_gets_multiple_fallback_files_when_no_path_matches_the_request():
    contents = {
        "src/alpha.py": "alpha\n" * 1000,
        "src/beta.py": "beta\n" * 1000,
        "src/gamma.py": "gamma\n" * 1000,
    }
    prepared = _prepare_prompt_evidence(
        "developer",
        "Implement an unrelated task whose terms do not match any path.",
        {"repository_snapshot": _snapshot(contents)},
    )
    selected = prepared["repository_snapshot"]["source_contents"]
    assert len(selected) == 3


def test_developer_context_prioritizes_architect_file_plan():
    contents = {
        "src/alpha.py": "alpha implementation\\n" * 1000,
        "src/planned.py": "planned implementation\\n" * 1000,
        "src/other.py": "other implementation\\n" * 1000,
    }
    selected = _select_source_contents(
        contents,
        "Implement a change with unrelated request wording.",
        planned_files=["src/planned.py"],
    )
    assert "src/planned.py" in selected


def test_existing_explicit_file_omitted_by_budget_is_reported_to_developer():
    path = "src/large_module.py"
    prepared = _prepare_prompt_evidence(
        "developer",
        f"Update only {path}.",
        {"repository_snapshot": _snapshot({path: "x" * 70000})},
    )
    selection = prepared["repository_snapshot"]["source_selection"]
    assert path in selection["omitted_explicit_paths"]


@pytest.mark.asyncio
async def test_developer_blocks_before_model_when_existing_target_source_is_omitted():
    path = "src/large_module.py"

    class NeverCalledProvider:
        async def complete(self, system_prompt, user_prompt):
            raise AssertionError("developer must not be called without the complete target file")

    evidence = {
        "product_brief": "A small change",
        "acceptance_criteria": ["AC-1"],
        "screen_specification": "No UI changes",
        "architecture": "Update one source file",
        "file_plan": [path],
        "repository_snapshot": _snapshot({path: "x" * 70000}),
    }
    runner = SpecialistAgentRunner(NeverCalledProvider())

    with pytest.raises(AgentOutputError, match="complete source contents are unavailable"):
        await runner.run("developer", f"Update only {path}.", evidence)

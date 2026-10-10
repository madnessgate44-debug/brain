"""Company workflow orchestration with mandatory tool-backed quality gates.

The engine coordinates specialist model calls, but repository edits and test execution
must be performed by injected tools. It never treats model claims as execution evidence.
"""

from typing import Any, Protocol

from brain.company.agent_runner import SpecialistAgentRunner
from brain.company.roles import WORKFLOW_ORDER
from brain.company.workflow import evaluate_release_gate


class CompanyWorkflowTools(Protocol):
    """Capabilities required to turn specialist decisions into verified work."""

    async def inspect_repository(self, repository: str) -> dict[str, Any]:
        """Read bounded project context from the actual repository."""

    async def apply_change_set(
        self, change_set: dict[str, Any], repository: str
    ) -> dict[str, Any]:
        """Apply proposed changes to an isolated branch and return the actual diff."""

    async def run_checks(self, repository: str, branch: str) -> dict[str, Any]:
        """Run real tests/build/lint and return execution evidence."""

    async def open_pull_request(
        self, repository: str, branch: str, workflow_result: dict[str, Any]
    ) -> dict[str, Any]:
        """Open a reviewable pull request after all required gates pass."""


class CompanyWorkflowBlocked(RuntimeError):
    """Raised when a workflow cannot safely advance to the next stage."""





def _gate_summary(output: dict[str, Any], decision_field: str) -> str:
    """Return compact, non-content-bearing diagnostics for a blocked specialist gate."""
    decision = output.get("deliverables", {}).get(decision_field, "<missing>")
    decision = " ".join(str(decision).split())[:40]
    return (
        f"role_status={str(output.get('status', '<missing>')).upper()}, "
        f"decision={decision!r}, findings={len(output.get('findings', []))}, "
        f"blockers={len(output.get('blockers', []))}, "
        f"evidence_needed={len(output.get('evidence_needed', []))}"
    )


def _compact_repository_snapshot(
    snapshot: dict[str, Any],
    user_request: str,
    max_chars: int = 40_000,
    max_files: int = 20,
) -> dict[str, Any]:
    """Bound repository context sent to every model call while retaining source evidence."""
    source_contents = snapshot.get("source_contents", {})
    if not isinstance(source_contents, dict):
        source_contents = {}

    explicit_paths = {
        token.strip("`'\".,:;()[]{}")
        for token in user_request.split()
        if "/" in token and "." in token
    }

    def priority(path: str) -> tuple[int, int, str]:
        lowered = path.casefold()
        if path in explicit_paths:
            group = 0
        elif lowered in {"readme.md", "pyproject.toml", "package.json", "requirements.txt"}:
            group = 1
        elif any(part in {"tests", "test", "__tests__"} for part in lowered.split("/")):
            group = 2
        elif lowered.startswith(".github/workflows/"):
            group = 3
        else:
            group = 4
        return (group, len(path), path)

    paths = sorted(
        (path for path, content in source_contents.items() if isinstance(path, str) and isinstance(content, str)),
        key=priority,
    )
    compact_contents: dict[str, str] = {}
    omitted_paths: list[str] = []
    remaining = max_chars
    for path in paths:
        if len(compact_contents) >= max_files or remaining <= 0:
            omitted_paths.append(path)
            continue
        content = source_contents[path]
        header = "FILE: " + path
        budget = min(4_000, remaining - len(header))
        if budget <= 0:
            omitted_paths.append(path)
            continue
        truncated = len(content) > budget
        excerpt = content[:budget]
        if truncated:
            excerpt += " [TRUNCATED: source excerpt capped for model context]"
        compact_contents[path] = excerpt
        remaining -= len(header) + min(len(content), budget)
        if truncated:
            omitted_paths.append(path)

    manifest = snapshot.get("source_manifest", {})
    if not isinstance(manifest, dict):
        manifest = {}
    files = snapshot.get("files", [])
    if not isinstance(files, list):
        files = []
    compact_files = [
        {
            "path": item.get("path"),
            "size": item.get("size"),
        }
        for item in files[:300]
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    ]
    failed_paths = manifest.get("failed_paths", {})
    if not isinstance(failed_paths, dict):
        failed_paths = {}
    return {
        "repository": snapshot.get("repository"),
        "default_branch": snapshot.get("default_branch"),
        "base_commit": snapshot.get("base_commit"),
        "truncated": snapshot.get("truncated", False),
        "source_files_read": snapshot.get("source_files_read", len(source_contents)),
        "files": compact_files,
        "source_contents": compact_contents,
        "source_manifest": {
            "candidate_count": manifest.get("candidate_count", len(paths)),
            "read_count": manifest.get("read_count", len(source_contents)),
            "coverage_complete": manifest.get("coverage_complete", False),
            "tree_truncated": manifest.get("tree_truncated", snapshot.get("truncated", False)),
            "aggregate_bytes_read": manifest.get("aggregate_bytes_read"),
            "failed_path_count": len(failed_paths),
            "failed_paths_sample": list(failed_paths)[:20],
            "omitted_by_aggregate_budget_count": len(
                manifest.get("omitted_by_aggregate_budget", [])
                if isinstance(manifest.get("omitted_by_aggregate_budget", []), list)
                else []
            ),
            "model_context_omitted_or_truncated_paths": omitted_paths,
            "model_context_char_limit": max_chars,
            "model_context_file_limit": max_files,
        },
    }


def validate_change_set(change_set: Any) -> tuple[str, ...]:
    """Validate a model-proposed patch before any GitHub write is attempted."""
    if not isinstance(change_set, dict):
        return ("change_set must be an object",)
    files = change_set.get("files")
    if not isinstance(files, list):
        return ("change_set.files must be a list",)
    errors: list[str] = []
    if not 1 <= len(files) <= 30:
        errors.append("change_set.files must contain between 1 and 30 files")
    seen: set[str] = set()
    total_bytes = 0
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            errors.append(f"files[{index}] must be an object")
            continue
        path = item.get("path")
        content = item.get("content")
        if not isinstance(path, str) or not path:
            errors.append(f"files[{index}].path must be a non-empty string")
        else:
            parts = path.split("/")
            if (
                path.startswith("/")
                or "\\" in path
                or any(part in {"", ".", ".."} for part in parts)
                or path.startswith(".git/")
            ):
                errors.append(f"files[{index}].path is unsafe: {path!r}")
            if path in seen:
                errors.append(f"duplicate file path: {path}")
            seen.add(path)
        if not isinstance(content, str):
            errors.append(f"files[{index}].content must be text")
            continue
        size = len(content.encode("utf-8"))
        if size > 200_000:
            errors.append(f"{path or index} exceeds the 200,000-byte per-file limit")
        total_bytes += size
    if total_bytes > 2_200_000:
        errors.append("change set exceeds the 2,200,000-byte aggregate limit")
    return tuple(errors)


class CompanyWorkflowEngine:
    """Run specialist roles in order, with bounded repair and evidence-based release."""

    def __init__(
        self,
        agent_runner: SpecialistAgentRunner,
        tools: CompanyWorkflowTools,
        max_repair_cycles: int = 2,
    ):
        self.agent_runner = agent_runner
        self.tools = tools
        self.max_repair_cycles = max_repair_cycles

    async def run(
        self,
        user_request: str,
        repository: str,
        initial_evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not repository or "/" not in repository:
            raise ValueError("repository must be in owner/repository format")

        repository_snapshot = await self.tools.inspect_repository(repository)
        model_snapshot = _compact_repository_snapshot(repository_snapshot, user_request)
        evidence: dict[str, Any] = {
            **(initial_evidence or {}),
            "user_request": user_request,
            "repository": repository,
            "repository_snapshot": model_snapshot,
        }
        outputs: dict[str, Any] = {}
        timeline: list[dict[str, Any]] = []

        # Product, UX, and architecture are completed before implementation.
        for role_key in WORKFLOW_ORDER[:3]:
            output = await self.agent_runner.run(role_key, user_request, evidence)
            outputs[role_key] = output
            timeline.append({"role": role_key, "status": output["status"]})
            if output["status"] != "PASS":
                raise CompanyWorkflowBlocked(
                    f"{role_key} did not pass: {output.get('blockers', [])}"
                )
            evidence.update(output["deliverables"])

        # Implementation may be repaired only a bounded number of times.
        developer_output = await self.agent_runner.run("developer", user_request, evidence)
        change_set = None
        validation_errors: tuple[str, ...] = ()
        for validation_cycle in range(self.max_repair_cycles + 1):
            if developer_output.get("status") != "PASS":
                raise CompanyWorkflowBlocked("Developer did not produce an approved change set.")
            change_set = developer_output.get("deliverables", {}).get("change_set")
            validation_errors = validate_change_set(change_set)
            if not validation_errors:
                break
            timeline.append({
                "role": "developer_preflight",
                "status": "NEEDS_REPAIR",
                "cycle": validation_cycle,
                "errors": list(validation_errors),
            })
            if validation_cycle >= self.max_repair_cycles:
                raise CompanyWorkflowBlocked(
                    "Developer change set remained invalid after repair limit: "
                    + "; ".join(validation_errors)
                )
            repair_evidence = {
                **evidence,
                "implementation_validation_errors": list(validation_errors),
                "implementation_feedback": (
                    "Correct the change set to satisfy every validation error. "
                    "Return a complete replacement change_set; do not claim changes were applied. "
                    + "; ".join(validation_errors)
                ),
                "repair_cycle": validation_cycle + 1,
            }
            developer_output = await self.agent_runner.run(
                "developer", user_request, repair_evidence
            )
        if validation_errors:
            raise CompanyWorkflowBlocked("Invalid change set reached the write boundary.")
        assert isinstance(change_set, dict)

        applied = await self.tools.apply_change_set(change_set, repository)
        if not applied.get("branch") or not isinstance(applied.get("diff"), str):
            raise CompanyWorkflowBlocked("Repository tool did not return branch and actual diff.")
        evidence.update({
            "change_set": change_set,
            "actual_diff": applied["diff"],
            "branch": applied["branch"],
            "changed_files": applied.get("changed_files", []),
        })
        outputs["developer"] = developer_output
        timeline.append({"role": "developer", "status": "APPLIED", "branch": applied["branch"]})

        review_output = None
        test_evidence = None
        for cycle in range(self.max_repair_cycles + 1):
            review_evidence = {**evidence, "repair_cycle": cycle}
            review_output = await self.agent_runner.run(
                "code_reviewer", user_request, review_evidence
            )
            outputs["code_reviewer"] = review_output
            timeline.append({"role": "code_reviewer", "status": review_output["status"],
                             "cycle": cycle})
            review_decision = review_output.get("deliverables", {}).get("review_decision")
            if review_output["status"] == "PASS" and str(review_decision).upper() in {"PASS", "APPROVED"}:
                break
            if cycle >= self.max_repair_cycles:
                raise CompanyWorkflowBlocked(
                    "Independent code review failed after repair limit ("
                    + _gate_summary(review_output, "review_decision")
                    + ")."
                )

            repair_evidence = {
                **evidence,
                "review_findings": review_output.get("findings", []),
                "review_blockers": review_output.get("blockers", []),
                "repair_cycle": cycle + 1,
            }
            repair = await self.agent_runner.run("developer", user_request, repair_evidence)
            if repair["status"] != "PASS":
                raise CompanyWorkflowBlocked("Developer could not resolve reviewer findings.")
            revised_change_set = repair["deliverables"].get("change_set")
            repair_errors = validate_change_set(revised_change_set)
            if repair_errors:
                raise CompanyWorkflowBlocked(
                    "Reviewer repair returned an invalid change set: "
                    + "; ".join(repair_errors)
                )
            applied = await self.tools.apply_change_set(revised_change_set, repository)
            if not applied.get("branch") or not isinstance(applied.get("diff"), str):
                raise CompanyWorkflowBlocked("Repair tool did not return actual diff evidence.")
            evidence.update({
                "change_set": revised_change_set,
                "actual_diff": applied["diff"],
                "branch": applied["branch"],
                "changed_files": applied.get("changed_files", []),
            })
            outputs["developer"] = repair

        # QA is not permitted to invent test execution. The runner must provide proof.
        test_evidence = await self.tools.run_checks(repository, evidence["branch"])
        if test_evidence.get("executed") is not True:
            raise CompanyWorkflowBlocked("QA tool did not confirm actual test execution.")
        if test_evidence.get("status") != "PASS":
            raise CompanyWorkflowBlocked("Repository checks failed; release is blocked.")
        evidence["test_results"] = test_evidence
        qa_output = await self.agent_runner.run("qa_engineer", user_request, evidence)
        outputs["qa_engineer"] = qa_output
        timeline.append({"role": "qa_engineer", "status": qa_output["status"]})
        if qa_output["status"] != "PASS":
            raise CompanyWorkflowBlocked("QA analysis found unresolved issues.")

        security_output = await self.agent_runner.run("security_auditor", user_request, evidence)
        outputs["security_auditor"] = security_output
        timeline.append({"role": "security_auditor", "status": security_output["status"]})
        if security_output["status"] != "PASS" or str(
            security_output.get("deliverables", {}).get("security_decision", "")
        ).upper() not in {"PASS", "APPROVED"}:
            raise CompanyWorkflowBlocked(
                "Security audit did not pass ("
                + _gate_summary(security_output, "security_decision")
                + ")."
            )

        customer_output = await self.agent_runner.run("customer_advocate", user_request, evidence)
        outputs["customer_advocate"] = customer_output
        timeline.append({"role": "customer_advocate", "status": customer_output["status"]})
        if customer_output["status"] != "PASS" or str(
            customer_output.get("deliverables", {}).get("customer_review", "")
        ).upper() not in {"PASS", "APPROVED"}:
            raise CompanyWorkflowBlocked(
                "Customer review did not pass ("
                + _gate_summary(customer_output, "customer_review")
                + ")."
            )

        # Release decision is evidence-based and remains a recommendation, not an auto-merge.
        evidence["review_decision"] = {
            "status": "PASS",
            "reviewer_role": "code_reviewer",
            "findings": review_output.get("findings", []),
        }
        evidence["security_decision"] = {"status": "PASS"}
        evidence["customer_review"] = {"status": "PASS"}
        gate = evaluate_release_gate(evidence)
        if not gate.passed:
            raise CompanyWorkflowBlocked("; ".join(gate.blockers))

        release_input = {
            **evidence,
            "review_decision": "PASS",
            "security_decision": "PASS",
            "customer_review": "PASS",
            "test_results": {"status": "PASS", "executed": True,
                             "run_url": test_evidence.get("run_url")},
        }
        release_output = await self.agent_runner.run(
            "release_manager", user_request, release_input
        )
        outputs["release_manager"] = release_output
        timeline.append({"role": "release_manager", "status": release_output["status"]})
        if release_output["status"] != "PASS" or str(
            release_output.get("deliverables", {}).get("release_decision", "")
        ).upper() not in {"PASS", "READY_FOR_HUMAN_APPROVAL"}:
            raise CompanyWorkflowBlocked("Release manager blocked release.")

        workflow_result = {
            "summary": outputs["product_owner"]["deliverables"].get(
                "product_brief", "Reviewed implementation"
            ),
            "repository": repository,
            "branch": evidence["branch"],
            "changed_files": evidence.get("changed_files", []),
            "test_evidence": test_evidence,
            "timeline": timeline,
            "role_outputs": outputs,
            "release_gate": {"passed": gate.passed, "blockers": list(gate.blockers)},
        }
        pull_request = await self.tools.open_pull_request(
            repository, evidence["branch"], workflow_result
        )
        if not pull_request.get("url") or pull_request.get("merged") is True:
            raise CompanyWorkflowBlocked(
                "Review pull request was not created safely; automatic merge is forbidden."
            )
        workflow_result.update({
            "status": "READY_FOR_HUMAN_APPROVAL",
            "pull_request": pull_request,
            "next_action": "Human review required; no automatic merge or deployment occurred.",
        })
        return workflow_result

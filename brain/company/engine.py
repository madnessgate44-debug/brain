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

    async def apply_change_set(
        self, change_set: dict[str, Any], repository: str
    ) -> dict[str, Any]:
        """Apply proposed changes to an isolated branch and return the actual diff."""

    async def run_checks(self, repository: str, branch: str) -> dict[str, Any]:
        """Run real tests/build/lint and return execution evidence."""


class CompanyWorkflowBlocked(RuntimeError):
    """Raised when a workflow cannot safely advance to the next stage."""


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

        evidence: dict[str, Any] = {
            **(initial_evidence or {}),
            "user_request": user_request,
            "repository": repository,
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
        if developer_output["status"] != "PASS":
            raise CompanyWorkflowBlocked("Developer did not produce an approved change set.")
        change_set = developer_output["deliverables"].get("change_set")
        if not isinstance(change_set, dict) or not change_set:
            raise CompanyWorkflowBlocked("Developer did not return a structured change set.")

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
            if review_output["status"] == "PASS":
                break
            if cycle >= self.max_repair_cycles:
                raise CompanyWorkflowBlocked("Independent code review failed after repair limit.")

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
            if not isinstance(revised_change_set, dict) or not revised_change_set:
                raise CompanyWorkflowBlocked("Repair did not provide a revised change set.")
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
        if security_output["status"] != "PASS":
            raise CompanyWorkflowBlocked("Security audit did not pass.")

        customer_output = await self.agent_runner.run("customer_advocate", user_request, evidence)
        outputs["customer_advocate"] = customer_output
        timeline.append({"role": "customer_advocate", "status": customer_output["status"]})
        if customer_output["status"] != "PASS":
            raise CompanyWorkflowBlocked("Customer review did not pass.")

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
        if release_output["status"] != "PASS":
            raise CompanyWorkflowBlocked("Release manager blocked release.")

        return {
            "status": "READY_FOR_HUMAN_APPROVAL",
            "repository": repository,
            "branch": evidence["branch"],
            "changed_files": evidence.get("changed_files", []),
            "test_evidence": test_evidence,
            "timeline": timeline,
            "role_outputs": outputs,
            "release_gate": {"passed": gate.passed, "blockers": list(gate.blockers)},
            "next_action": "Human review required; no automatic merge or deployment occurred.",
        }

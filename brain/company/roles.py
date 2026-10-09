"""Specialist roles and mandatory gates for Brain's software-company workflow."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SpecialistRole:
    key: str
    title: str
    mission: str
    required_inputs: tuple[str, ...]
    deliverables: tuple[str, ...]
    must_be_independent_of: tuple[str, ...] = ()


ROLE_CATALOG: tuple[SpecialistRole, ...] = (
    SpecialistRole(
        key="product_owner",
        title="Product Owner / Requirements Analyst",
        mission="Convert the request into a testable product brief; identify assumptions, "
                "scope boundaries, users, and measurable acceptance criteria.",
        required_inputs=("user_request",),
        deliverables=("product_brief", "acceptance_criteria", "open_questions"),
    ),
    SpecialistRole(
        key="ux_designer",
        title="Product and UX/UI Designer",
        mission="Design the end-to-end user journey, screen inventory, interaction states, "
                "accessibility expectations, and visual direction before implementation.",
        required_inputs=("product_brief", "acceptance_criteria"),
        deliverables=("user_journeys", "screen_specification", "design_system"),
    ),
    SpecialistRole(
        key="architect",
        title="Software Architect",
        mission="Define the implementation approach, component boundaries, data contracts, "
                "integration points, risks, and implementation sequence.",
        required_inputs=("product_brief", "acceptance_criteria", "screen_specification"),
        deliverables=("architecture", "file_plan", "technical_risks"),
    ),
    SpecialistRole(
        key="developer",
        title="Implementation Engineer",
        mission="Implement only approved requirements and architecture; produce a traceable "
                "change set and explain every changed file.",
        required_inputs=("acceptance_criteria", "architecture", "file_plan"),
        deliverables=("change_set", "implementation_notes"),
    ),
    SpecialistRole(
        key="code_reviewer",
        title="Independent Code Reviewer",
        mission="Review the actual proposed diff against requirements and architecture. "
                "Find correctness, maintainability, regression, and scope problems. "
                "Do not assume the implementation is correct.",
        required_inputs=("acceptance_criteria", "architecture", "change_set"),
        deliverables=("review_findings", "review_decision"),
        must_be_independent_of=("developer",),
    ),
    SpecialistRole(
        key="qa_engineer",
        title="Quality Assurance Engineer",
        mission="Verify the actual implementation using reproducible tests. Separate "
                "executed test evidence from proposed or inferred tests.",
        required_inputs=("acceptance_criteria", "change_set"),
        deliverables=("test_plan", "test_results", "defect_list"),
    ),
    SpecialistRole(
        key="security_auditor",
        title="Security Auditor",
        mission="Audit authentication, authorization, secrets, input validation, data "
                "exposure, dependency risk, and unsafe execution paths.",
        required_inputs=("architecture", "change_set", "test_results"),
        deliverables=("security_findings", "security_decision"),
        must_be_independent_of=("developer",),
    ),
    SpecialistRole(
        key="customer_advocate",
        title="Customer Advocate",
        mission="Evaluate the result against the intended user's needs, usability, "
                "accessibility, clarity, and acceptance criteria. Flag unmet needs.",
        required_inputs=("product_brief", "acceptance_criteria", "screen_specification",
                         "change_set", "test_results"),
        deliverables=("customer_review", "usability_findings"),
    ),
    SpecialistRole(
        key="release_manager",
        title="Release Manager",
        mission="Make a release recommendation only from recorded evidence and gate "
                "decisions. List blockers and never turn missing evidence into a pass.",
        required_inputs=("review_decision", "test_results", "security_decision",
                         "customer_review"),
        deliverables=("release_decision", "release_checklist"),
    ),
)

ROLE_BY_KEY = {role.key: role for role in ROLE_CATALOG}

# The developer cannot approve their own work. QA, security, customer, and release
# gates are mandatory; a failed gate routes work back for repair instead of passing.
WORKFLOW_ORDER = tuple(role.key for role in ROLE_CATALOG)
MANDATORY_RELEASE_GATES = (
    "review_decision",
    "test_results",
    "security_decision",
    "customer_review",
)

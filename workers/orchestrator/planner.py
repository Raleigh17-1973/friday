from __future__ import annotations

from typing import TYPE_CHECKING

from packages.common.models import PlannerOutput, RiskLevel

if TYPE_CHECKING:
    from packages.llm.base import LLMProvider

_PLANNER_SYSTEM = """\
You are Friday's planning engine. Analyze the user's business request and produce a routing plan.

Available specialist IDs: chief_of_staff_strategist, project_manager, finance, operations, sales_revenue, writer_scribe, research, critic_red_team

Respond ONLY with valid JSON (no markdown fences):
{
  "problem_statement": "<restate the core problem clearly>",
  "missing_information": ["<question about missing info>"],
  "domains_involved": ["strategy|finance|operations|sales|project_management|research|legal"],
  "recommended_specialists": ["<specialist_id>"],
  "required_tools": ["docs.retrieve"],
  "risk_level": "low|medium|high",
  "output_format": "executive_brief|business_case_draft|full_deliverable"
}

Rules:
- Always include at least one specialist
- Include web.research in required_tools only if current market or external data is needed
- Set risk_level to medium or high if legal, compliance, security, or customer data is involved
- Set output_format to business_case_draft only if user explicitly wants a business case or ROI analysis
- Set output_format to full_deliverable if the user asks you to develop, write, create, draft, or build a specific document (charter, plan, report, proposal, memo, etc.) — in this case Friday must produce the actual document, not advice"""


def build_plan(message: str, llm: "LLMProvider | None" = None) -> PlannerOutput:
    if llm is not None:
        try:
            parsed = llm.complete_json(_PLANNER_SYSTEM, message)
            if parsed and "recommended_specialists" in parsed and parsed["recommended_specialists"]:
                risk_raw = str(parsed.get("risk_level", "low")).lower()
                risk_level = RiskLevel.HIGH if risk_raw == "high" else (RiskLevel.MEDIUM if risk_raw == "medium" else RiskLevel.LOW)
                return PlannerOutput(
                    problem_statement=str(parsed.get("problem_statement", message.strip())),
                    missing_information=list(parsed.get("missing_information", [])),
                    domains_involved=list(parsed.get("domains_involved", ["strategy"])),
                    recommended_specialists=list(parsed["recommended_specialists"]),
                    required_tools=list(parsed.get("required_tools", ["docs.retrieve"])),
                    risk_level=risk_level,
                    output_format=str(parsed.get("output_format", "executive_brief")),
                )
        except Exception:
            pass
    text = message.lower()
    domains: list[str] = []
    specialists: list[str] = ["chief_of_staff_strategist"]
    tools: list[str] = ["docs.retrieve"]
    is_business_case = any(token in text for token in ["business case", "template", "investment"])
    is_project_charter = "project charter" in text
    is_creation_request = any(
        token in text
        for token in ["develop", "write", "create", "draft", "build", "produce", "generate", "design"]
    )
    is_project_management = any(
        token in text
        for token in [
            "project",
            "pmo",
            "charter",
            "stakeholder",
            "milestone",
            "timeline",
            "schedule",
            "raid",
            "wbs",
            "deliverable",
        ]
    )

    if is_project_management:
        domains.append("project_management")
        specialists.append("project_manager")

    if any(token in text for token in [
        "roi", "budget", "pricing", "cash flow", "payback", "ebitda", "margin",
        "revenue", "cost", "implementation cost", "arr", "mrr", "annual", "loaded cost",
    ]):
        if "finance" not in domains:
            domains.append("finance")
        if "finance" not in specialists:
            specialists.append("finance")
    if any(token in text for token in [
        "process", "throughput", "bottleneck", "execution", "workflow", "manual",
        "automation", "hours per", "rework", "reporting", "ops",
    ]):
        if "operations" not in domains:
            domains.append("operations")
        if "operations" not in specialists:
            specialists.append("operations")
    if any(token in text for token in ["sales", "pipeline", "revenue", "lead", "conversion"]):
        domains.append("sales")
        specialists.append("sales_revenue")
    if any(token in text for token in ["business case", "template", "proposal", "investment"]):
        domains.append("strategy")
        specialists.append("finance")
        specialists.append("writer_scribe")
    if is_business_case:
        specialists.append("operations")
    if "risk" in text or "assumption" in text:
        specialists.append("critic_red_team")
    if any(token in text for token in ["research", "market", "competitor", "benchmark", "latest"]):
        specialists.append("research")
        tools.append("web.research")

    if not domains:
        domains.append("strategy")

    risk_level = RiskLevel.LOW
    if any(token in text for token in ["legal", "compliance", "security", "customer data"]):
        risk_level = RiskLevel.MEDIUM

    missing_info = []
    has_timeline = any(
        token in text
        for token in ["deadline", "days", "weeks", "months", "q1", "q2", "q3", "q4", "by ", "within", "30", "60", "90"]
    )

    # Detect rich financial / operational data already in the message
    has_financial_data = any(
        token in text
        for token in [
            "payback", "ebitda", "margin", "loaded cost", "implementation cost", "revenue",
            "arr", "mrr", "per month", "per quarter", "hours per", "/hour", "$ per",
            "one-time", "ongoing cost", "software cost", "annual", "monthly cost",
        ]
    )
    has_baseline_metrics = any(
        token in text
        for token in ["hours", "% of", "rework", "late", "satisfaction", "score", "/10", "baseline", "current-state"]
    )
    has_headcount = any(token in text for token in ["person", "-person", "team", "headcount", "employees", "staff"])
    has_industry = any(
        token in text
        for token in ["saas", "retail", "healthcare", "finance", "agency", "b2b", "b2c", "revops", "startup"]
    )
    has_constraints = any(
        token in text
        for token in ["constraint", "cannot", "no new hire", "must not", "requirement", "i need", "i want", "i do not"]
    )

    # If user provided rich data, skip discovery questions — just produce the deliverable
    data_rich = has_financial_data and has_baseline_metrics

    foundational_missing: list[str] = []
    if is_project_charter and any(token in text for token in ["ai", "automation", "copilot", "assistant"]):
        use_case_tokens = [
            "status report", "risk", "issue", "schedule", "resource", "forecast",
            "stakeholder update", "planning", "raid", "meeting", "scope", "change request",
        ]
        if not any(token in text for token in use_case_tokens):
            foundational_missing.append(
                "Which exact project-management workflow should AI support first (for example: status reporting, risk triage, schedule forecasting)?"
            )
        if not any(token in text for token in ["pain", "problem", "bottleneck", "delay", "manual", "rework", "issue"]):
            foundational_missing.append("What problem is most urgent today in that workflow?")
        if not any(token in text for token in ["sponsor", "stakeholder", "executive", "steering", "audience"]):
            foundational_missing.append("Who is the charter audience and decision-maker (sponsor/steering group)?")

    missing_info.extend(foundational_missing)
    if not foundational_missing and not data_rich:
        # Only ask for missing data if the user hasn't already provided rich context
        if not has_timeline:
            missing_info.append("What timeline or decision deadline should this target?")
        if "metric" not in text and not has_baseline_metrics:
            missing_info.append("Which KPI matters most for success?")
    if is_business_case and not data_rich:
        if not has_industry:
            missing_info.append("What industry and business model are you in?")
        if not any(token in text for token in ["deal size", "acv", "arr", "revenue"]):
            missing_info.append("What is your average deal size or revenue per customer?")
        if not has_headcount:
            missing_info.append("How large is the team that would use this workflow?")
        if not has_baseline_metrics:
            missing_info.append("What are your current baseline metrics for the workflow?")
        if not has_financial_data:
            missing_info.append("What budget range is acceptable for this initiative?")
        if "risk" not in text and not has_constraints:
            missing_info.append("What failure risks are you most concerned about?")

    if is_business_case:
        output_format = "business_case_draft"
    elif is_creation_request:
        output_format = "full_deliverable"
    else:
        output_format = "executive_brief"

    return PlannerOutput(
        problem_statement=message.strip(),
        missing_information=missing_info,
        domains_involved=domains,
        recommended_specialists=sorted(set(specialists)),
        required_tools=tools,
        risk_level=risk_level,
        output_format=output_format,
    )

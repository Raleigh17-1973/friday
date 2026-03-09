from __future__ import annotations

from packages.common.models import PlannerOutput, RiskLevel


def build_plan(message: str) -> PlannerOutput:
    text = message.lower()
    domains: list[str] = []
    specialists: list[str] = ["chief_of_staff_strategist"]
    tools: list[str] = ["docs.retrieve"]
    is_business_case = any(token in text for token in ["business case", "template", "investment"])
    is_project_charter = "project charter" in text
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

    if any(token in text for token in ["roi", "budget", "pricing", "cash flow"]):
        domains.append("finance")
        specialists.append("finance")
    if any(token in text for token in ["process", "throughput", "bottleneck", "execution"]):
        domains.append("operations")
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
    foundational_missing: list[str] = []
    if is_project_charter and any(token in text for token in ["ai", "automation", "copilot", "assistant"]):
        use_case_tokens = [
            "status report",
            "risk",
            "issue",
            "schedule",
            "resource",
            "forecast",
            "stakeholder update",
            "planning",
            "raid",
            "meeting",
            "scope",
            "change request",
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
    if not foundational_missing:
        if "deadline" not in text:
            missing_info.append("What timeline or decision deadline should this target?")
        if "metric" not in text:
            missing_info.append("Which KPI matters most for success?")
    if is_business_case:
        if not any(token in text for token in ["industry", "vertical", "saas", "retail", "healthcare", "finance"]):
            missing_info.append("What industry and business model are you in?")
        if not any(token in text for token in ["deal size", "acv", "arr", "revenue"]):
            missing_info.append("What is your average deal size or revenue per customer?")
        if not any(token in text for token in ["team", "headcount", "rep", "sdr", "ae"]):
            missing_info.append("How large is the team that would use this workflow?")
        if not any(token in text for token in ["baseline", "current", "today"]):
            missing_info.append("What are your current baseline metrics for the workflow?")
        if not any(token in text for token in ["budget", "capex", "opex", "cost"]):
            missing_info.append("What budget range is acceptable for this initiative?")
        if "risk" not in text:
            missing_info.append("What failure risks are you most concerned about?")

    return PlannerOutput(
        problem_statement=message.strip(),
        missing_information=missing_info,
        domains_involved=domains,
        recommended_specialists=sorted(set(specialists)),
        required_tools=tools,
        risk_level=risk_level,
        output_format="business_case_draft" if is_business_case else "executive_brief",
    )

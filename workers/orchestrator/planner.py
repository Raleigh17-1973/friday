from __future__ import annotations

from typing import TYPE_CHECKING

from packages.common.models import PlannerOutput, RiskLevel

if TYPE_CHECKING:
    from packages.llm.base import LLMProvider

_PLANNER_SYSTEM = """\
You are Friday's planning engine. Analyze the user's business request and produce a routing plan.

Available specialist IDs: chief_of_staff_strategist, project_manager, finance, operations, sales_revenue, writer_scribe, research, critic_red_team, process_mapper, document_specialist, ai_strategy, internal_comms, public_relations, mergers_acquisitions, okr_coach

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
    # Process mapping detection — must come before the general "process" operations check
    _PROCESS_MAP_KEYWORDS = [
        "map a process", "map the process", "map our process",
        "document a process", "document the process", "document our process",
        "process flow", "process mapping", "process documentation",
        "flowchart", "flow chart",
        "swim lane", "swimlane", "swim-lane",
        "workflow diagram",
        "standard operating procedure", "sop",
        "walk me through", "walk us through",
        "capture our process", "capture the process",
        "business process",
    ]
    _process_map_hits = sum(1 for kw in _PROCESS_MAP_KEYWORDS if kw in text)
    # Also count single-word signals
    _PROCESS_MAP_SINGLES = ["diagram", "flowchart", "swimlane", "sop", "procedure"]
    _process_map_hits += sum(1 for kw in _PROCESS_MAP_SINGLES if kw in text.split())
    is_process_mapping = _process_map_hits >= 1

    if is_process_mapping:
        domains.append("operations")
        if "process_mapper" not in specialists:
            specialists.append("process_mapper")
        # process mapping is self-contained — remove noisy catch-all
        if "chief_of_staff_strategist" in specialists and len(specialists) > 1:
            specialists.remove("chief_of_staff_strategist")

    if any(token in text for token in [
        "process", "throughput", "bottleneck", "execution", "workflow", "manual",
        "automation", "hours per", "rework", "reporting", "ops",
    ]) and not is_process_mapping:
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

    # Document generation detection
    _DOCUMENT_KEYWORDS = [
        "word doc", "powerpoint", "pptx", "docx", "excel", "spreadsheet",
        "pdf", "slide deck", "presentation", "board deck", "pitch deck",
        "write up as", "export as", "as a document", "google doc", "google slides",
        "google sheets", "make a deck", "create a report", "generate a memo",
    ]
    is_document_request = any(kw in text for kw in _DOCUMENT_KEYWORDS)
    if is_document_request:
        if "document_specialist" not in specialists:
            specialists.append("document_specialist")
        if "writer_scribe" not in specialists:
            specialists.append("writer_scribe")

    # Data analysis / code interpreter detection
    _ANALYSIS_KEYWORDS = [
        "analyze", "analyse", "plot", "chart", "graph", "visualize", "visualise",
        "csv", "excel file", "spreadsheet data", "run the numbers", "calculate",
        "correlation", "regression", "distribution", "histogram", "trend",
        "data analysis", "run python", "write code to", "pandas", "numpy",
    ]
    if any(kw in text for kw in _ANALYSIS_KEYWORDS):
        if "analysis.run" not in tools:
            tools.append("analysis.run")
        if "research" not in specialists:
            specialists.append("research")

    # Financial modeling detection
    _MODELING_KEYWORDS = [
        "runway", "burn rate", "dcf", "valuation", "ltv", "cac", "unit economics",
        "sensitivity", "scenario model", "three case", "three-case", "forecast model",
        "payback period", "break even", "break-even", "wacc", "terminal value",
        "headcount model", "hiring plan",
    ]
    if any(kw in text for kw in _MODELING_KEYWORDS):
        if "modeling.scenarios" not in tools:
            tools.append("modeling.scenarios")
        if "modeling.runway" not in tools:
            tools.append("modeling.runway")
        if "finance" not in specialists:
            specialists.append("finance")

    # Meeting intelligence detection
    _MEETING_KEYWORDS = [
        "meeting notes", "action items", "follow up", "follow-up items",
        "what was decided", "recap the meeting", "process notes", "meeting summary",
        "next steps from", "who is responsible for",
    ]
    if any(kw in text for kw in _MEETING_KEYWORDS):
        if "meetings.action_items" not in tools:
            tools.append("meetings.action_items")

    # Decision log detection
    _DECISION_KEYWORDS = [
        "why did we", "past decision", "previously decided", "log this decision",
        "decision log", "record this", "what did we decide about",
    ]
    if any(kw in text for kw in _DECISION_KEYWORDS):
        if "decisions.context" not in tools:
            tools.append("decisions.context")
        if "decisions.search" not in tools:
            tools.append("decisions.search")

    # Proactive / alerts detection
    if any(kw in text for kw in ["alerts", "what's at risk", "kpi status", "weekly digest", "digest", "what needs attention"]):
        if "proactive.alerts" not in tools:
            tools.append("proactive.alerts")

    # Initialize risk_level and output_format before specialist routing blocks
    risk_level = RiskLevel.LOW
    output_format = None

    # AI Strategy routing
    _AI_STRATEGY_KEYWORDS = [
        "automate", "automation opportunity", "agent strategy", "where can ai",
        "agentize", "ai readiness", "process automation", "replace with ai",
        "augment with ai", "ai operating model", "intelligent automation",
        "workflow automation", "where should ai", "ai strategy", "automate this",
        "repetitive work", "manual process", "candidate for automation",
    ]
    if any(kw in text for kw in _AI_STRATEGY_KEYWORDS):
        if "ai_strategy" not in specialists:
            specialists.append("ai_strategy")

    # Internal Comms routing
    _INTERNAL_COMMS_KEYWORDS = [
        "internal announcement", "internal memo", "all-hands", "all hands",
        "change management", "employee communication", "rollout communication",
        "org memo", "leadership update", "internal launch", "reorg communication",
        "policy change announcement", "announce to the team", "communicate to employees",
        "staff announcement", "manager update", "internal message",
    ]
    if any(kw in text for kw in _INTERNAL_COMMS_KEYWORDS):
        if "internal_comms" not in specialists:
            specialists.append("internal_comms")
        if output_format != "full_deliverable":
            output_format = "full_deliverable"

    # PR routing
    _PR_KEYWORDS = [
        "press release", "media strategy", "pr strategy", "public announcement",
        "press statement", "journalist", "media response", "reputation",
        "external narrative", "public relations", "launch announcement",
        "talking points", "media q&a", "spokesperson", "external comms",
        "narrative control", "news release", "pr angle", "crisis comms",
    ]
    if any(kw in text for kw in _PR_KEYWORDS):
        if "public_relations" not in specialists:
            specialists.append("public_relations")
        if risk_level == RiskLevel.LOW:
            risk_level = RiskLevel.MEDIUM

    # M&A routing
    _MA_KEYWORDS = [
        "acquisition", "acquire", "acqui-hire", "merger", "m&a",
        "due diligence", "diligence", "divestiture", "synergy",
        "post-merger", "integration plan", "buy vs build", "strategic partnership",
        "target company", "deal structure", "term sheet", "loi", "letter of intent",
        "acquihire", "strategic acquisition", "ma strategy",
    ]
    if any(kw in text for kw in _MA_KEYWORDS):
        if "mergers_acquisitions" not in specialists:
            specialists.append("mergers_acquisitions")
        risk_level = RiskLevel.HIGH

    # OKR Coach routing
    _OKR_COACH_KEYWORDS = [
        "write an okr", "review my okr", "is this a good kr", "key result",
        "okr coach", "okr review", "measurable goal", "okr framework",
        "help me set okrs", "okr quality", "okr scoring", "okr alignment",
        "write okrs", "improve my okrs", "review these okrs",
        "is this measurable", "help with okrs", "okr structure",
    ]
    if any(kw in text for kw in _OKR_COACH_KEYWORDS):
        if "okr_coach" not in specialists:
            specialists.append("okr_coach")

    if not domains:
        domains.append("strategy")

    if risk_level == RiskLevel.LOW:
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

    if output_format is None:
        if is_process_mapping:
            output_format = "full_deliverable"
        elif is_business_case:
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

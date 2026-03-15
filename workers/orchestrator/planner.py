from __future__ import annotations

from typing import TYPE_CHECKING

from packages.common.models import PlannerOutput, RiskLevel

if TYPE_CHECKING:
    from packages.llm.base import LLMProvider

_PLANNER_SYSTEM = """\
You are Friday's planning engine. Analyze the user's business request and produce a routing plan.

Available specialist IDs and their domains:
- chief_of_staff_strategist: strategy, priorities, tradeoffs, executive decision-making
- project_manager: project charters, milestones, timelines, PMO, RAID, WBS
- finance: budget, ROI, unit economics, pricing, cash flow, financial modeling
- operations: process optimization, bottlenecks, execution, workflow efficiency
- sales_revenue: pipeline, revenue, lead conversion, sales strategy, deal structure
- writer_scribe: drafting documents, memos, reports, structured writing
- research: market research, competitive analysis, external data gathering
- critic_red_team: risk assessment, assumption challenging, failure mode analysis
- process_mapper: mapping, documenting, diagramming business processes and SOPs
- document_specialist: document structure, templates, Word/PowerPoint/PDF generation
- ai_strategy: automation opportunities, AI readiness, intelligent workflow design
- internal_comms: internal announcements, change management communications, all-hands
- public_relations: press releases, media strategy, external narrative, crisis comms
- mergers_acquisitions: acquisitions, due diligence, deal structure, integration planning
- okr_coach: OKR writing, key result quality, OKR alignment and coaching
- people_hr: org design, hiring, HR policy, compensation, performance, internal mobility, employee experience, change management
- legal_compliance: legal exposure, regulatory compliance, contracts, data privacy, GDPR, policy risk
- marketing_brand: brand strategy, messaging, positioning, campaigns, go-to-market, content
- product: product roadmap, feature prioritization, requirements, PRDs, sprint planning
- customer_success_support: customer retention, churn prevention, NPS, support playbooks, account health
- data_analytics: metrics strategy, KPI frameworks, dashboards, experimentation, analytics plans
- security_risk: security posture, data exposure, risk controls, vulnerability assessment, InfoSec

Respond ONLY with valid JSON (no markdown fences):
{
  "problem_statement": "<restate the core problem clearly>",
  "missing_information": ["<question about missing info>"],
  "domains_involved": ["strategy|finance|operations|sales|project_management|research|legal|hr|marketing|product|data|security"],
  "recommended_specialists": ["<specialist_id>"],
  "required_tools": ["docs.retrieve"],
  "risk_level": "low|medium|high",
  "output_format": "executive_brief|business_case_draft|full_deliverable"
}

Rules:
- Always include at least one specialist
- For HR, people, hiring, recruiting, org design, employee, workforce, internal mobility, internal movement, internal transfer, role transition, promotion process, succession, performance management, compensation, benefits, onboarding, offboarding, or change management topics: ALWAYS include people_hr
- For legal, compliance, regulation, contracts, data privacy, or policy topics: ALWAYS include legal_compliance
- For marketing, brand, campaigns, messaging, or go-to-market topics: ALWAYS include marketing_brand
- For product roadmap, features, requirements, or prioritization topics: ALWAYS include product
- For customer success, churn, retention, NPS, or support topics: ALWAYS include customer_success_support
- For metrics, analytics, KPIs, dashboards, or experimentation: ALWAYS include data_analytics
- For security, risk posture, data exposure, or InfoSec topics: ALWAYS include security_risk
- Include web.research in required_tools only if current market or external data is needed
- Set risk_level to medium or high if legal, compliance, security, or customer data is involved
- Set output_format to business_case_draft only if user explicitly wants a business case or ROI analysis
- Set output_format to full_deliverable if the user asks you to develop, write, create, draft, or build a specific document (charter, plan, report, proposal, memo, etc.) — in this case Friday must produce the actual document, not advice"""


def _process_discovery_check(message_lower: str, output_format: str) -> tuple[bool, list[str]]:
    """Return (requires_clarification, questions) for a full_deliverable process-map request.

    Called from both the LLM path and the keyword fallback path so that the discovery
    gate behaves identically regardless of which planning route was taken.
    """
    if output_format != "full_deliverable":
        return False, []

    _QUESTION_STARTERS = (
        "why ", "what ", "how ", "should ", "can ", "could ", "is ", "are ",
        "does ", "do ", "who ", "when ", "where ", "which ", "would ", "will ",
        "tell me ", "explain ", "help me understand", "walk me through",
        "walk us through",
    )
    _is_question = message_lower.rstrip().endswith("?") or any(
        message_lower.lstrip().startswith(q) for q in _QUESTION_STARTERS
    )
    if _is_question:
        return False, []

    _PROC_MAP_KW = [
        "map a process", "map the process", "map our process", "map out",
        "document a process", "document the process", "document our process",
        "process flow", "process mapping", "process documentation",
        "flowchart", "flow chart", "swim lane", "swimlane", "swim-lane",
        "workflow diagram", "standard operating procedure", "sop",
        "capture our process", "capture the process", "business process",
    ]
    _CREATE_VERBS = [
        "create a", "create an", "write a", "write an", "draft a", "draft an",
        "build a", "build an", "develop a", "develop an", "produce a", "produce an",
        "generate a", "generate an", "make a", "make an", "put together a",
        "put together an", "map a", "map an", "map the", "map our", "map this",
    ]
    _ARTIFACT_NOUNS = [
        "document", "report", "memo", "brief", "charter", "plan", "proposal",
        "strategy", "playbook", "roadmap", "presentation", "deck", "sop",
        "process map", "flowchart", "diagram", "template", "policy", "framework",
        "process",
    ]
    _is_proc_map = any(kw in message_lower for kw in _PROC_MAP_KW)
    _is_explicit = (
        any(v in message_lower for v in _CREATE_VERBS)
        and any(n in message_lower for n in _ARTIFACT_NOUNS)
    )
    _explicit_proc = _is_explicit and "process" in message_lower

    if not (_is_proc_map or _explicit_proc):
        return False, []

    _DETAIL_SIGNALS = [
        "step", "stage", "phase", "first", "then", "next", "finally",
        "owner", "responsible", "owned by", "trigger", "triggered", "initiated",
        "input", "output", "deliverable", "department", "team ", " role",
        "decision", "approval", "exception", "condition", "if ", " if",
        " when ", "starts when", "ends when",
    ]
    _has_detail = (
        len(message_lower.split()) > 30
        or sum(1 for sig in _DETAIL_SIGNALS if sig in message_lower) >= 3
    )
    if _has_detail:
        return False, []

    return True, [
        "Which team or role owns this process end-to-end?",
        "What event or action triggers it, and what is the final output or outcome?",
        "Roughly how many steps are involved, and are there any key decision points or exceptions I should capture?",
    ]


def _keyword_augment_specialists(message_lower: str, specialists: list[str]) -> list[str]:
    """Add any domain-critical agents the LLM missed based on keyword rules.

    This is a belt-and-suspenders pass applied after the LLM returns its list.
    It ensures people_hr, legal_compliance, and security_risk are never silently omitted
    when the topic clearly belongs to their domain.
    """
    _HR = [
        "hr ", " hr,", "human resources", "hiring", "recruit",
        "org design", "org chart", "people ops", "people team",
        "change management", "employee", "employee onboarding", "staff onboarding",
        "new hire onboarding", "performance review", "performance management",
        "compensation", "benefits", "headcount plan",
        "internal movement", "internal mobility", "internal transfer",
        "role transition", "promotion process", "promotion", "succession",
        "workforce plan", "talent", "employee engagement", "offboarding",
        "termination", "leave policy", "parental leave", "pay band",
        "leveling", "career path", "team structure", "org restructure",
        "reorg", "people strategy", "talent acquisition", "job description",
        "interview process",
    ]
    _LEGAL = [
        "legal", "compliance", "regulation", "regulatory", "gdpr", "hipaa",
        "ccpa", "contract", "liability", "data privacy", "privacy policy",
        "terms of service", "terms and conditions", "legal review",
        "data protection", "intellectual property", "trademark", "patent",
        "nda", "confidentiality", "labor law", "employment law", "sox",
    ]
    _SECURITY = [
        "security posture", "infosec", "cybersecurity", "data breach",
        "vulnerability", "penetration test", "pen test", "access control",
        "zero trust", "soc 2", "soc2", "iso 27001", "threat model",
        "incident response", "data exposure", "risk posture", "security audit",
        "pii handling",
    ]
    augmented = list(specialists)
    if any(kw in message_lower for kw in _HR) and "people_hr" not in augmented:
        augmented.append("people_hr")
    if any(kw in message_lower for kw in _LEGAL) and "legal_compliance" not in augmented:
        augmented.append("legal_compliance")
    if any(kw in message_lower for kw in _SECURITY) and "security_risk" not in augmented:
        augmented.append("security_risk")
    return augmented


def build_plan(message: str, llm: "LLMProvider | None" = None) -> PlannerOutput:
    if llm is not None:
        try:
            parsed = llm.complete_json(_PLANNER_SYSTEM, message)
            if parsed and "recommended_specialists" in parsed and parsed["recommended_specialists"]:
                risk_raw = str(parsed.get("risk_level", "low")).lower()
                risk_level = RiskLevel.HIGH if risk_raw == "high" else (RiskLevel.MEDIUM if risk_raw == "medium" else RiskLevel.LOW)
                # Augment LLM specialist list with any domain-critical agents it missed
                specialists = _keyword_augment_specialists(
                    message.lower(), list(parsed["recommended_specialists"])
                )
                _llm_output_format = str(parsed.get("output_format", "executive_brief"))
                _llm_missing = list(parsed.get("missing_information", []))
                _req_clarif, _discovery_qs = _process_discovery_check(
                    message.lower(), _llm_output_format
                )
                if _req_clarif:
                    # Surface discovery questions instead of (or ahead of) generic ones
                    _llm_missing = _discovery_qs
                return PlannerOutput(
                    problem_statement=str(parsed.get("problem_statement", message.strip())),
                    missing_information=_llm_missing,
                    domains_involved=list(parsed.get("domains_involved", ["strategy"])),
                    recommended_specialists=specialists,
                    required_tools=list(parsed.get("required_tools", ["docs.retrieve"])),
                    risk_level=risk_level,
                    output_format=_llm_output_format,
                    requires_clarification=_req_clarif,
                )
        except Exception:
            pass
    text = message.lower()
    domains: list[str] = []
    specialists: list[str] = ["chief_of_staff_strategist"]
    tools: list[str] = ["docs.retrieve"]

    # ── Intent detection ──────────────────────────────────────────────────────
    # Detect questions: these get executive_brief even when topic keywords would
    # normally suggest full_deliverable.  A question wants an *answer*, not a draft.
    _QUESTION_STARTERS = (
        "why ", "what ", "how ", "should ", "can ", "could ", "is ", "are ",
        "does ", "do ", "who ", "when ", "where ", "which ", "would ", "will ",
        "tell me ", "explain ", "help me understand", "walk me through",
        "walk us through",
    )
    _is_question = text.rstrip().endswith("?") or any(
        text.lstrip().startswith(q) for q in _QUESTION_STARTERS
    )

    # Explicit deliverable request: verb + artifact noun pair → user wants a document
    _EXPLICIT_CREATE_VERBS = [
        "create a", "create an", "write a", "write an", "draft a", "draft an",
        "build a", "build an", "develop a", "develop an", "produce a", "produce an",
        "generate a", "generate an", "make a", "make an", "put together a",
        "put together an",
        # "map" used as a verb (to create a map/diagram of something)
        "map a", "map an", "map the", "map our", "map this",
    ]
    _ARTIFACT_NOUNS = [
        "document", "report", "memo", "brief", "charter", "plan", "proposal",
        "strategy", "playbook", "roadmap", "presentation", "deck", "sop",
        "process map", "flowchart", "diagram", "template", "policy", "framework",
        # "process" is a valid artifact noun when the verb is an explicit creation verb
        "process",
    ]
    _is_explicit_deliverable = (
        any(verb in text for verb in _EXPLICIT_CREATE_VERBS)
        and any(noun in text for noun in _ARTIFACT_NOUNS)
    )
    # ─────────────────────────────────────────────────────────────────────────

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
        # "walk me through" / "walk us through" removed — those are questions (explain to me),
        # not requests to produce a process map document.
        "capture our process", "capture the process",
        "business process",
    ]
    _process_map_hits = sum(1 for kw in _PROCESS_MAP_KEYWORDS if kw in text)
    # Also count single-word signals
    _PROCESS_MAP_SINGLES = ["diagram", "flowchart", "swimlane", "sop", "procedure"]
    _process_map_hits += sum(1 for kw in _PROCESS_MAP_SINGLES if kw in text.split())
    is_process_mapping = _process_map_hits >= 1

    # Also treat explicit-deliverable + "process" as process mapping (but not questions)
    _explicit_process_deliverable = _is_explicit_deliverable and not _is_question and "process" in text
    if is_process_mapping or _explicit_process_deliverable:
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
        # Only force full_deliverable for comms if user wants a document, not just advice
        if output_format != "full_deliverable" and not _is_question:
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

    # People / HR routing
    _PEOPLE_HR_KEYWORDS = [
        "hr ", " hr,", "human resources", "hiring", "recruit", "org design", "org chart",
        "people ops", "people team", "change management", "employee",
        "employee onboarding", "staff onboarding", "new hire onboarding",
        "performance review", "performance management", "compensation", "benefits",
        "headcount plan", "internal movement", "internal mobility", "internal transfer",
        "role transition", "promotion process", "promotion", "succession",
        "workforce plan", "talent", "culture",
        "employee engagement", "offboarding", "termination", "leave policy",
        "parental leave", "pay band", "leveling", "career path",
        "team structure", "org restructure", "reorg", "people strategy",
        "talent acquisition", "job description", "interview process",
    ]
    if any(kw in text for kw in _PEOPLE_HR_KEYWORDS):
        if "people_hr" not in specialists:
            specialists.append("people_hr")

    # Legal / Compliance routing
    _LEGAL_COMPLIANCE_KEYWORDS = [
        "legal", "compliance", "regulation", "regulatory", "gdpr", "hipaa", "ccpa",
        "contract", "liability", "data privacy", "privacy policy", "terms of service",
        "terms and conditions", "legal review", "data protection",
        "intellectual property", "trademark", "patent",
        "nda", "confidentiality", "labor law", "employment law", "sox",
    ]
    if any(kw in text for kw in _LEGAL_COMPLIANCE_KEYWORDS):
        if "legal_compliance" not in specialists:
            specialists.append("legal_compliance")
        if risk_level == RiskLevel.LOW:
            risk_level = RiskLevel.MEDIUM

    # Marketing / Brand routing
    _MARKETING_BRAND_KEYWORDS = [
        "marketing", "brand strategy", "campaign", "go-to-market", "gtm",
        "content strategy", "brand guidelines", "launch marketing", "demand generation",
        "social media strategy", "advertising strategy", "seo strategy",
        "email marketing", "brand identity", "value proposition", "tagline",
        "brand voice", "content calendar", "thought leadership", "brand positioning",
    ]
    if any(kw in text for kw in _MARKETING_BRAND_KEYWORDS):
        if "marketing_brand" not in specialists:
            specialists.append("marketing_brand")

    # Product routing
    _PRODUCT_KEYWORDS = [
        "product roadmap", "user story", "product requirements", "prd",
        "product backlog", "sprint planning", "release planning", "mvp",
        "product strategy", "product vision", "product discovery",
        "jobs to be done", "product-led", "north star metric",
        "feature prioritization", "feature flag", "beta launch", "product spec",
    ]
    if any(kw in text for kw in _PRODUCT_KEYWORDS):
        if "product" not in specialists:
            specialists.append("product")

    # Customer Success / Support routing
    _CS_KEYWORDS = [
        "customer success", "customer support", "churn", "churn rate", "retention",
        "nps", "customer health", "customer satisfaction", "csat", "support ticket",
        "escalation", "customer journey", "renewal", "expansion revenue",
        "upsell", "customer onboarding", "time to value",
        "support playbook", "customer feedback", "customer complaint",
    ]
    if any(kw in text for kw in _CS_KEYWORDS):
        if "customer_success_support" not in specialists:
            specialists.append("customer_success_support")

    # Data / Analytics routing (strategy-level, distinct from code-interpreter analysis)
    _DATA_ANALYTICS_KEYWORDS = [
        "metrics plan", "kpi framework", "analytics strategy", "measurement plan",
        "dashboard design", "reporting strategy", "data strategy", "experiment design",
        "funnel analysis", "cohort analysis", "attribution model", "tracking plan",
        "data governance", "data quality", "event schema", "instrumentation plan",
    ]
    if any(kw in text for kw in _DATA_ANALYTICS_KEYWORDS):
        if "data_analytics" not in specialists:
            specialists.append("data_analytics")

    # Security / Risk routing
    _SECURITY_RISK_KEYWORDS = [
        "security posture", "infosec", "cybersecurity", "data breach", "vulnerability",
        "penetration test", "pen test", "access control policy", "zero trust",
        "soc 2", "soc2", "iso 27001", "threat model", "incident response",
        "data exposure", "risk posture", "security audit", "password policy",
        "mfa", "multi-factor", "encryption strategy", "pii handling",
    ]
    if any(kw in text for kw in _SECURITY_RISK_KEYWORDS):
        if "security_risk" not in specialists:
            specialists.append("security_risk")
        if risk_level == RiskLevel.LOW:
            risk_level = RiskLevel.MEDIUM

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

    # Use word-boundary-safe AI detection: " ai " / starts-with "ai " to avoid
    # false-positive on "raid" which contains "ai" as a substring.
    _text_padded = f" {text} "  # pad once, reuse below
    _has_ai_token = (
        " ai " in _text_padded
        or " automation " in _text_padded
        or "copilot" in text
        or "assistant" in text
    )

    foundational_missing: list[str] = []
    if is_project_charter and _has_ai_token:
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
        if _is_explicit_deliverable and not _is_question:
            # User explicitly asked for a specific document artifact → produce it
            # (Guards against "Should we create a process?" — that's a question, not a creation request)
            output_format = "full_deliverable"
        elif is_process_mapping and not _is_question:
            # User wants a process map created (not just explained)
            output_format = "full_deliverable"
        elif is_business_case:
            output_format = "business_case_draft"
        elif is_creation_request and not _is_question:
            # Creation verb detected but only when it's not phrased as a question
            # ("How do I create X?" → executive_brief; "Create X for me" → full_deliverable)
            output_format = "full_deliverable"
        else:
            output_format = "executive_brief"

    # Process-mapping discovery — run after output_format is finalized.
    # When discovery questions are needed, they replace generic enrichment questions
    # so the user only sees the focused questions that actually block production.
    _req_clarif_kw, _discovery_qs_kw = (
        _process_discovery_check(text, output_format)
        if not foundational_missing
        else (False, [])
    )
    if _req_clarif_kw:
        # Override: surface only the discovery questions, not generic enrichment ones
        final_missing = _discovery_qs_kw
    else:
        final_missing = missing_info

    return PlannerOutput(
        problem_statement=message.strip(),
        missing_information=final_missing,
        domains_involved=domains,
        recommended_specialists=sorted(set(specialists)),
        required_tools=tools,
        risk_level=risk_level,
        output_format=output_format,
        requires_clarification=_req_clarif_kw,
    )

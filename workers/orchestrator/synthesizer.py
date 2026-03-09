from __future__ import annotations

from packages.common.models import CriticReport, FinalAnswerPackage, PlannerOutput, SpecialistMemo


def _render_questions(questions: list[str]) -> str:
    if not questions:
        return ""
    lines = ["Questions I need from you (answer in bullets):"]
    lines.extend([f"- {question}" for question in questions[:6]])
    return "\n".join(lines)


def _template_response(questions: list[str]) -> str:
    body = [
        "Here is a practical business case template you can fill in right now:",
        "",
        "1) Objective",
        "- Decision to make:",
        "- Business outcome targeted:",
        "- Why now:",
        "",
        "2) Current baseline (today)",
        "- Current process:",
        "- Volume per month:",
        "- Conversion rate:",
        "- Average deal size / revenue impact:",
        "- Cycle time:",
        "",
        "3) AI use case options",
        "- Option A:",
        "- Option B:",
        "- What changes in workflow:",
        "",
        "4) Financial model",
        "- One-time implementation cost:",
        "- Monthly run cost:",
        "- Expected uplift (%):",
        "- Payback period (months):",
        "",
        "5) Pilot design (90 days)",
        "- Owner:",
        "- Teams involved:",
        "- Success KPI:",
        "- Stop/go criteria:",
        "",
        "6) Risks and controls",
        "- Top 3 risks:",
        "- Mitigations:",
        "- Approval gates required:",
    ]
    questions_block = _render_questions(questions)
    if questions_block:
        body.extend(["", questions_block])
    return "\n".join(body)


def _business_case_draft(plan: PlannerOutput, top_recs: list[str], questions: list[str]) -> str:
    core_guidance = top_recs[:3] if top_recs else []
    lines = [
        "I drafted a first-pass business case below so you can move immediately, then refine with your data.",
        "",
        "Draft Business Case v1",
        f"- Problem statement: {plan.problem_statement}",
        "- Decision: fund a 90-day pilot before full rollout.",
        "",
        "Recommended scope",
        "- Start with 1-2 high-frequency workflows where cycle-time and quality are visible.",
        "- Assign one accountable owner and one measurable KPI.",
        "- Keep tooling read-only initially, then introduce write actions behind approvals.",
        "",
        "Expected value framework",
        "- Baseline: current throughput, conversion, cycle time, and error/rework rate.",
        "- Impact model: (volume x uplift per event) - implementation and run costs.",
        "- Financial decision: approve scale only if payback and risk thresholds are met.",
        "",
        "Implementation plan",
        "- Week 1-2: baseline measurement + workflow design.",
        "- Week 3-8: pilot execution with weekly KPI reviews.",
        "- Week 9-12: decision memo (scale / adjust / stop).",
    ]
    if core_guidance:
        lines.extend(["", "Specialist guidance applied:"])
        lines.extend([f"- {item}" for item in core_guidance])
    questions_block = _render_questions(questions)
    if questions_block:
        lines.extend(["", questions_block])
    return "\n".join(lines)


def _project_charter_draft(questions: list[str]) -> str:
    lines = [
        "Here is a project charter draft you can use immediately:",
        "",
        "Project Charter v1",
        "1) Project title",
        "- AI Enablement for Project Management Workflow",
        "",
        "2) Objective",
        "- Improve planning quality, reduce coordination overhead, and shorten delivery cycle time.",
        "",
        "3) Scope",
        "- In scope: planning, status reporting, risk/issue tracking, decision memo drafting.",
        "- Out of scope: autonomous production changes without approval.",
        "",
        "4) Success metrics",
        "- Planning cycle time reduction (%)",
        "- On-time milestone attainment (%)",
        "- Risk identification lead time (days)",
        "- Team adoption rate (%)",
        "",
        "5) Stakeholders and ownership",
        "- Executive sponsor:",
        "- Program owner:",
        "- PM lead:",
        "- Security/compliance approver:",
        "",
        "6) Timeline and milestones",
        "- Phase 1: baseline + design",
        "- Phase 2: pilot execution",
        "- Phase 3: evaluation and scale decision",
        "",
        "7) Risks and controls",
        "- Data quality risk",
        "- Change adoption risk",
        "- Governance drift risk",
        "- Mitigation: approval gates + weekly metric review + rollback criteria",
    ]
    questions_block = _render_questions(questions)
    if questions_block:
        lines.extend(["", questions_block])
    return "\n".join(lines)


def _project_charter_discovery(questions: list[str]) -> str:
    lines = [
        "Before I draft the charter, I need a few inputs so it is credible and usable.",
        "",
        "Answer these first (bullets are fine):",
    ]
    lines.extend([f"- {question}" for question in questions[:8]])
    lines.extend(
        [
            "",
            "Once you answer, I will generate a complete PMBOK-aligned charter draft with scope, stakeholders, milestones, RAID, and governance.",
        ]
    )
    return "\n".join(lines)


def _general_actionable_response(questions: list[str]) -> str:
    lines = [
        "Here is a practical starting plan you can execute immediately:",
        "",
        "1) Define outcome and owner",
        "- Name the decision owner and one success KPI.",
        "",
        "2) Build the first draft",
        "- Capture scope, constraints, assumptions, and top risks.",
        "",
        "3) Validate quickly",
        "- Run a short pilot and review results against the KPI.",
        "",
        "4) Decide next move",
        "- Scale, revise, or stop based on evidence and risk.",
    ]
    questions_block = _render_questions(questions)
    if questions_block:
        lines.extend(["", questions_block])
    return "\n".join(lines)


def synthesize(plan: PlannerOutput, memos: list[SpecialistMemo], critic: CriticReport) -> FinalAnswerPackage:
    experts = [memo.specialist_id for memo in memos]
    top_recs = [memo.recommendation for memo in memos[:3]]
    assumptions = [assumption for memo in memos for assumption in memo.assumptions][:4]
    risks = list(dict.fromkeys([*critic.residual_risks, *critic.blind_spots]))[:5]

    prompt = plan.problem_statement.strip()
    prompt_lower = prompt.lower()
    if "project charter" in prompt_lower:
        if plan.missing_information:
            direct_answer = _project_charter_discovery(plan.missing_information)
        else:
            direct_answer = _project_charter_draft(plan.missing_information)
    elif "template" in prompt_lower:
        direct_answer = _template_response(plan.missing_information)
    elif plan.output_format == "business_case_draft":
        direct_answer = _business_case_draft(plan, top_recs, plan.missing_information)
    else:
        direct_answer = _general_actionable_response(plan.missing_information)

    summary = f"Friday synthesized {', '.join(experts) if experts else 'manager'} perspectives into one coherent recommendation."

    next_steps = [
        "Confirm timeline, decision owner, and primary success KPI.",
        "Draft the first-pass plan using the recommendation components above.",
        "Run a constrained pilot with a pre-defined stop/go gate.",
        "Review outcomes and decide to scale, revise, or stop.",
    ]
    if top_recs:
        next_steps.insert(1, f"Apply specialist guidance: {top_recs[0]}")
    if plan.missing_information:
        next_steps.append("Answer missing information questions before committing full rollout.")

    return FinalAnswerPackage(
        direct_answer=direct_answer,
        executive_summary=summary,
        key_assumptions=assumptions,
        major_risks=risks,
        recommended_next_steps=next_steps,
        what_i_would_do_first="Set one KPI and owner, then run a constrained pilot.",
        experts_consulted=experts,
        confidence=0.72,
    )

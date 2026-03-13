from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Iterator

from packages.common.models import CriticReport, FinalAnswerPackage, PlannerOutput, SpecialistMemo

if TYPE_CHECKING:
    from packages.llm.base import LLMProvider

_SYNTHESIZER_SYSTEM = """\
You are Friday's synthesis engine. Your job is to produce the actual deliverable the user asked for — not advice about how to create it.

CRITICAL RULE: If the user asked you to develop, write, create, draft, or build something (a charter, plan, business case, analysis, report, etc.), you MUST produce the complete, filled-in document in direct_answer. Do NOT produce a blank template, a to-do list, or generic advice. Write the actual content using reasonable assumptions where data is missing, and note assumptions clearly.

If the user asked a question or requested analysis, produce a specific, structured answer with real numbers where possible.

Respond ONLY with valid JSON (no markdown fences):
{
  "direct_answer": "<the complete deliverable or full answer — write the actual document/analysis, not a template>",
  "executive_summary": "<1-2 sentence summary>",
  "key_assumptions": ["<assumption 1>"],
  "major_risks": ["<risk 1>"],
  "recommended_next_steps": ["<step 1>", "<step 2>"],
  "what_i_would_do_first": "<single most important first action>",
  "confidence": <0.0-1.0 float>
}"""

_SYNTHESIZER_STREAM_SYSTEM = """\
You are Friday's synthesis engine producing a live-streamed response for the user.

Write a complete, specific, professional response to the user's request — the actual deliverable, not advice about how to create it. Use narrative prose with clear markdown headers. If numbers were provided, compute with them and show your math. If a document was requested, write the full document.

Do NOT wrap your response in JSON. Write directly — the user will read your tokens as they stream in.
Be crisp, expert, and complete."""

_SYNTHESIZER_REFINEMENT_SYSTEM = """\
You are Friday's synthesis engine performing a REFINEMENT PASS. A previous synthesis attempt had low confidence.

Your task: produce a stronger, more complete version of the deliverable by directly addressing the critic's objections and blind spots.

RULES:
1. The direct_answer must be more complete and specific than the first attempt
2. Directly address every blind spot and challenged assumption from the critic
3. If numbers were provided in the problem, use them — show calculations
4. Do NOT produce a template or placeholder text
5. Your confidence score must be higher than the previous attempt

Respond ONLY with valid JSON (no markdown fences):
{
  "direct_answer": "<improved, complete deliverable — more specific than the first pass>",
  "executive_summary": "<1-2 sentence summary>",
  "key_assumptions": ["<assumption 1>"],
  "major_risks": ["<risk 1>"],
  "recommended_next_steps": ["<step 1>", "<step 2>"],
  "what_i_would_do_first": "<single most important first action>",
  "confidence": <0.0-1.0 float — aim higher than previous attempt>
}"""

_STUB_WARNING = (
    "\n\n---\n⚠️ *Running in limited mode (LLM unavailable). "
    "This is a structured outline using your data. Connect a working API key for full AI analysis.*"
)


# ---------------------------------------------------------------------------
# Number extraction helpers
# ---------------------------------------------------------------------------

def _extract_numbers(text: str) -> dict:
    """Pull key financial/operational metrics out of free-form text."""
    nums: dict = {}

    # Dollar amounts
    dollars = re.findall(r'\$[\d,]+(?:\.\d+)?(?:M|K|B)?', text, re.IGNORECASE)
    if dollars:
        nums["dollar_amounts"] = dollars

    # Percentages
    pcts = re.findall(r'\d+(?:\.\d+)?%', text)
    if pcts:
        nums["percentages"] = pcts

    # Hours
    hours = re.findall(r'[\d.]+\s*hours?', text, re.IGNORECASE)
    if hours:
        nums["hours"] = hours

    # Named metrics with values
    for pattern, key in [
        (r'(\d+)\s*(?:retainer\s*)?clients?', "clients"),
        (r'\$?([\d,]+(?:\.\d+)?)[MK]?\s*(?:annual\s*)?revenue', "revenue"),
        (r'(\d+(?:\.\d+)?)\s*%\s*(?:ebitda|margin)', "margin_pct"),
        (r'(\d+(?:\.\d+)?)\s*%.*?late', "late_pct"),
        (r'(\d+(?:\.\d+)?)\s*%.*?rework', "rework_pct"),
        (r'\$([\d,]+(?:\.\d+)?)\s*/\s*hour', "hourly_rate"),
        (r'([\d.]+)\s*/\s*10\s*(?:satisfaction|score|csat)', "sat_score"),
        (r'\$([\d,]+(?:\.\d+)?)\s*(?:one-time|implementation)', "impl_cost"),
        (r'\$([\d,]+(?:\.\d+)?)\s*/\s*month', "monthly_cost"),
        (r'payback.*?(\d+)\s*months?', "payback_months"),
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            nums[key] = m.group(1)

    return nums


def _calc_roi(text: str) -> dict | None:
    """Attempt to compute ROI math from text if enough numbers are present."""
    n = _extract_numbers(text)

    try:
        clients = int(n.get("clients", 0))
        rate = float(n.get("hourly_rate", 0))
        impl_cost = float(n.get("impl_cost", "0").replace(",", ""))
        monthly_sw = 0.0

        # Extract monthly software cost
        m = re.search(r'\$([\d,]+(?:\.\d+)?)\s*/\s*month', text, re.IGNORECASE)
        if m:
            monthly_sw = float(m.group(1).replace(",", ""))

        # Current hours
        m = re.search(r'([\d.]+)\s*hours?\s*per\s*client\s*per\s*month', text, re.IGNORECASE)
        current_hours = float(m.group(1)) if m else 0

        # Future hours
        m = re.search(r'(?:drops?|down)\s*to\s*([\d.]+)\s*hours?\s*per\s*client\s*per\s*month', text, re.IGNORECASE)
        future_hours = float(m.group(1)) if m else 0

        if clients and rate and current_hours and future_hours:
            saved_hrs_mo = (current_hours - future_hours) * clients
            saved_cost_mo = saved_hrs_mo * rate
            net_monthly = saved_cost_mo - monthly_sw
            payback_mo = impl_cost / net_monthly if net_monthly > 0 else None
            annual_savings = net_monthly * 12

            # QBR savings
            qbr_current = 0.0
            qbr_future = 0.0
            m1 = re.search(r'([\d.]+)\s*hours?\s*per\s*client\s*per\s*quarter', text, re.IGNORECASE)
            m2 = re.search(r'(?:drops?|down)\s*to\s*([\d.]+)\s*hours?\s*per\s*client\s*per\s*quarter', text, re.IGNORECASE)
            if m1:
                qbr_current = float(m1.group(1))
            if m2:
                qbr_future = float(m2.group(1))
            if qbr_current and qbr_future:
                qbr_saved_hrs = (qbr_current - qbr_future) * clients
                qbr_saved_quarterly = qbr_saved_hrs * rate
                annual_savings += qbr_saved_quarterly * 4

            return {
                "clients": clients,
                "rate": rate,
                "current_hours_mo": current_hours,
                "future_hours_mo": future_hours,
                "saved_hrs_mo": round(saved_hrs_mo, 1),
                "saved_cost_mo": round(saved_cost_mo),
                "monthly_sw_cost": monthly_sw,
                "net_monthly_benefit": round(net_monthly),
                "impl_cost": impl_cost,
                "payback_months": round(payback_mo, 1) if payback_mo else None,
                "annual_net_benefit": round(annual_savings),
                "year1_roi_pct": round((annual_savings - impl_cost) / impl_cost * 100, 1) if impl_cost else None,
            }
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Stub response builders (used only when LLM is unavailable)
# ---------------------------------------------------------------------------

def _render_questions(questions: list[str]) -> str:
    if not questions:
        return ""
    lines = ["To sharpen this further, answer:"]
    lines.extend([f"- {question}" for question in questions[:6]])
    return "\n".join(lines)


def _business_case_draft(plan: PlannerOutput, top_recs: list[str], questions: list[str]) -> str:
    roi = _calc_roi(plan.problem_statement)
    lines = [
        "**Draft Business Case**",
        "",
        f"**Problem:** {plan.problem_statement[:300]}{'...' if len(plan.problem_statement) > 300 else ''}",
        "",
    ]

    if roi:
        payback_str = f"{roi['payback_months']} months" if roi.get("payback_months") else "< 12 months (estimated)"
        lines += [
            "**Financial Analysis**",
            f"- Monthly hours saved: {roi['saved_hrs_mo']} hrs × ${roi['rate']}/hr = **${roi['saved_cost_mo']:,}/month** gross savings",
            f"- Less software cost: ${roi['monthly_sw_cost']:,}/month",
            f"- **Net monthly benefit: ${roi['net_monthly_benefit']:,}**",
            f"- Implementation cost: ${roi['impl_cost']:,} one-time",
            f"- **Payback period: {payback_str}**",
            f"- Year-1 net benefit: ${roi['annual_net_benefit']:,}",
        ]
        if roi.get("year1_roi_pct") is not None:
            lines.append(f"- Year-1 ROI: {roi['year1_roi_pct']}%")
    else:
        lines += [
            "**Financial Model (template — fill in your numbers)**",
            "- Monthly labor saved: (hours saved × clients × hourly rate)",
            "- Less ongoing software cost",
            "- Payback: implementation cost ÷ net monthly benefit",
        ]

    lines += [
        "",
        "**Recommendation:** Fund a 90-day pilot before full rollout.",
        "",
        "**Pilot Plan**",
        "- Week 1–2: Baseline measurement and KPI confirmation",
        "- Week 3–8: Pilot execution with weekly KPI reviews",
        "- Week 9–12: Decision memo — scale / adjust / stop with evidence",
    ]

    if top_recs:
        lines += ["", "**Specialist Guidance**"]
        lines += [f"- {r}" for r in top_recs[:3]]

    if questions:
        lines += ["", _render_questions(questions)]

    return "\n".join(lines) + _STUB_WARNING


def _project_charter_draft(questions: list[str], plan: "PlannerOutput | None" = None, top_recs: "list[str] | None" = None) -> str:
    problem = plan.problem_statement.strip() if plan else "Project initiative"
    domains = ", ".join(plan.domains_involved) if plan and plan.domains_involved else "strategy, operations"
    recs = top_recs or []
    roi = _calc_roi(problem)

    # Derive title from first meaningful sentence
    first_sentence = re.split(r'[.!?]', problem)[0].strip()
    title = first_sentence[:80] if first_sentence else problem[:80]

    lines = [
        f"**Project Charter**",
        f"**Project:** {title}",
        "",
        "**1. Problem Statement**",
        f"{problem[:500]}{'...' if len(problem) > 500 else ''}",
        "",
        "**2. Objective**",
        "Deliver a measurable reduction in the problem above within a defined pilot window.",
        "Success is defined by one primary KPI confirmed before kick-off.",
        "",
        f"**3. Scope**",
        f"- In scope: {domains} work streams directly tied to the stated problem",
        "- Out of scope: adjacent initiatives, autonomous production changes without approval",
    ]

    if roi:
        payback_str = f"{roi['payback_months']} months" if roi.get("payback_months") else "to be confirmed"
        lines += [
            "",
            "**4. Financial Case**",
            f"- Monthly hours saved: {roi['saved_hrs_mo']} hrs (across {roi['clients']} clients)",
            f"- Gross monthly savings: ${roi['saved_cost_mo']:,} @ ${roi['rate']}/hr",
            f"- Net monthly benefit: ${roi['net_monthly_benefit']:,} (after ${roi['monthly_sw_cost']:,}/mo software)",
            f"- Implementation cost: ${roi['impl_cost']:,} one-time",
            f"- Payback period: {payback_str}",
            f"- Year-1 net benefit: ${roi['annual_net_benefit']:,}",
        ]
    else:
        lines += [
            "",
            "**4. Financial Case**",
            "- One-time implementation cost: [confirm]",
            "- Ongoing software cost: [confirm]",
            "- Expected payback period: [confirm]",
        ]

    lines += [
        "",
        "**5. Success Metrics**",
        "- Primary KPI: confirmed with decision-maker before Phase 1 starts",
        "- Secondary: cycle time reduction, quality improvement, or cost avoidance",
        "- Stop/go gate: defined threshold agreed before pilot launches",
        "",
        "**6. Stakeholders**",
        "- Executive sponsor: [name]",
        "- Program owner: [name]",
        f"- Domain leads: {domains}",
        "",
        "**7. Delivery Phases**",
        "- Phase 1 (Weeks 1–2): Baseline measurement, workflow mapping, KPI confirmation",
        "- Phase 2 (Weeks 3–8): Pilot execution with weekly KPI reviews",
        "- Phase 3 (Weeks 9–12): Decision memo — scale / adjust / stop with evidence",
        "",
        "**8. Risks & Controls**",
        "- Data quality risk → validate source data before Phase 2 begins",
        "- Change adoption risk → designate a change lead; run weekly check-ins",
        "- Scope creep risk → written change-request process with sponsor approval",
        "- Governance drift → approval gates and rollback criteria defined upfront",
    ]

    if recs:
        lines += ["", "**9. Specialist Analysis Applied**"]
        lines += [f"   - {r}" for r in recs[:4]]

    if questions:
        lines += ["", _render_questions(questions)]

    return "\n".join(lines) + _STUB_WARNING


def _project_charter_discovery(questions: list[str], plan: "PlannerOutput | None" = None) -> str:
    problem = plan.problem_statement.strip() if plan else ""
    lines = []
    if problem:
        lines += [f'Got it — you want a project charter for: "{problem[:200]}{"..." if len(problem) > 200 else ""}"', ""]
    lines += [
        "Before I draft it, a few quick inputs will make the charter specific and credible:",
        "",
    ]
    lines.extend([f"- {question}" for question in questions[:8]])
    lines.extend(
        [
            "",
            "Once you answer, I'll generate a complete charter with scope, stakeholders, milestones, financial case, RAID log, and governance gates — filled in with your specifics.",
        ]
    )
    return "\n".join(lines)


def _general_actionable_response(plan: PlannerOutput, top_recs: list[str], questions: list[str]) -> str:
    roi = _calc_roi(plan.problem_statement)
    lines = [
        "**Analysis & Recommendation**",
        "",
        f"**Problem:** {plan.problem_statement[:400]}{'...' if len(plan.problem_statement) > 400 else ''}",
    ]

    if roi:
        lines += [
            "",
            "**Quick Financial Model**",
            f"- Monthly savings: ${roi['saved_cost_mo']:,}/mo gross → ${roi['net_monthly_benefit']:,}/mo net",
            f"- Implementation cost: ${roi['impl_cost']:,}",
        ]
        if roi.get("payback_months"):
            lines.append(f"- **Payback: {roi['payback_months']} months**")

    lines += [
        "",
        "**Recommended Next Steps**",
        "1. Confirm one decision owner and one primary success KPI",
        "2. Run a constrained pilot (6–8 weeks) against the baseline metrics",
        "3. Set a pre-agreed stop/go gate before the pilot starts",
        "4. Review outcomes and decide: scale, adjust, or stop",
    ]

    if top_recs:
        lines += ["", "**Specialist Input**"]
        lines += [f"- {r}" for r in top_recs[:3]]

    if questions:
        lines += ["", _render_questions(questions)]

    return "\n".join(lines) + _STUB_WARNING


# ---------------------------------------------------------------------------
# Main synthesize() entry point
# ---------------------------------------------------------------------------

def synthesize(
    plan: PlannerOutput,
    memos: list[SpecialistMemo],
    critic: CriticReport,
    llm: "LLMProvider | None" = None,
    refinement_pass: bool = False,
) -> FinalAnswerPackage:
    experts = [memo.specialist_id for memo in memos]
    top_recs = [memo.recommendation for memo in memos[:4]]
    assumptions = [assumption for memo in memos for assumption in memo.assumptions][:4]
    risks = list(dict.fromkeys([*critic.residual_risks, *critic.blind_spots]))[:5]

    if llm is not None:
        try:
            memos_text = "\n\n".join(
                f"Specialist: {m.specialist_id}\nAnalysis: {m.analysis}\nRecommendation: {m.recommendation}"
                for m in memos
            )
            critic_text = (
                f"Critic blind spots: {json.dumps(critic.blind_spots)}\n"
                f"Challenged assumptions: {json.dumps(critic.challenged_assumptions)}\n"
                f"Alternative path: {critic.alternative_path}\n"
                f"Residual risks: {json.dumps(critic.residual_risks)}"
            )
            llm_prompt = (
                f"User question: {plan.problem_statement}\n\n"
                f"Planner identified domains: {', '.join(plan.domains_involved)}\n"
                f"Output format requested: {plan.output_format}\n\n"
                f"Specialist memos:\n{memos_text}\n\n"
                f"Critic review:\n{critic_text}"
            )
            system = _SYNTHESIZER_REFINEMENT_SYSTEM if refinement_pass else _SYNTHESIZER_SYSTEM
            parsed = llm.complete_json(system, llm_prompt, max_tokens=3000)
            if parsed and "direct_answer" in parsed:
                return FinalAnswerPackage(
                    direct_answer=str(parsed["direct_answer"]),
                    executive_summary=str(parsed.get("executive_summary", "")),
                    key_assumptions=list(parsed.get("key_assumptions", assumptions)),
                    major_risks=list(parsed.get("major_risks", risks)),
                    recommended_next_steps=list(parsed.get("recommended_next_steps", [])),
                    what_i_would_do_first=parsed.get("what_i_would_do_first"),
                    experts_consulted=experts,
                    confidence=float(parsed.get("confidence", 0.8)),
                )
        except Exception:
            pass

    # ---- Stub fallback ----
    prompt = plan.problem_statement.strip()
    prompt_lower = prompt.lower()

    if "project charter" in prompt_lower:
        if plan.missing_information:
            direct_answer = _project_charter_discovery(plan.missing_information, plan=plan)
        else:
            direct_answer = _project_charter_draft(plan.missing_information, plan=plan, top_recs=top_recs)
    elif plan.output_format == "business_case_draft" or "business case" in prompt_lower:
        direct_answer = _business_case_draft(plan, top_recs, plan.missing_information)
    else:
        direct_answer = _general_actionable_response(plan, top_recs, plan.missing_information)

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
        next_steps.append("Answer the clarifying questions above before committing to full rollout.")

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


def synthesize_stream(
    plan: PlannerOutput,
    memos: list[SpecialistMemo],
    critic: CriticReport,
    llm: "LLMProvider | None" = None,
) -> Iterator[str]:
    """Stream synthesis tokens as they arrive from the LLM.

    Falls back to yielding the stub response in chunks if LLM is unavailable.
    Callers should buffer yielded tokens to reconstruct the full response.
    """
    if llm is not None:
        try:
            memos_text = "\n\n".join(
                f"Specialist: {m.specialist_id}\nAnalysis: {m.analysis}\nRecommendation: {m.recommendation}"
                for m in memos
            )
            critic_text = (
                f"Critic blind spots: {json.dumps(critic.blind_spots)}\n"
                f"Challenged assumptions: {json.dumps(critic.challenged_assumptions)}\n"
                f"Alternative path: {critic.alternative_path}\n"
                f"Residual risks: {json.dumps(critic.residual_risks)}"
            )
            llm_prompt = (
                f"User question: {plan.problem_statement}\n\n"
                f"Planner identified domains: {', '.join(plan.domains_involved)}\n"
                f"Output format requested: {plan.output_format}\n\n"
                f"Specialist memos:\n{memos_text}\n\n"
                f"Critic review:\n{critic_text}"
            )
            yield from llm.stream(_SYNTHESIZER_STREAM_SYSTEM, llm_prompt, max_tokens=3000)
            return
        except Exception:
            pass

    # Stub fallback — yield the pre-computed stub text in word-sized chunks
    stub_text = synthesize(plan, memos, critic, llm=None).direct_answer
    for word in stub_text.split(" "):
        yield word + " "

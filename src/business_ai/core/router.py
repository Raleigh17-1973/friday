from __future__ import annotations

import re
from collections import defaultdict

from business_ai.core.models import TaskRequest

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sales": ("sales", "deal", "pipeline", "opportunity", "quote", "pricing"),
    "customer_support": ("support", "ticket", "incident", "sla", "customer issue"),
    "hr": ("hr", "hiring", "onboarding", "performance", "employee"),
    "corporate_it": ("it", "vpn", "laptop", "sso", "network", "device"),
    "engineering": ("engineering", "api", "release", "bug", "architecture", "deploy"),
    "finance": ("finance", "budget", "forecast", "roi", "payback", "cost"),
    "grc": ("grc", "compliance", "audit", "regulatory", "control", "governance"),
    "legal": ("legal", "contract", "nda", "msa", "liability", "privacy"),
    "communications": ("communications", "email", "announcement", "messaging", "status update"),
    "strategy": ("strategy", "positioning", "market", "scenario", "competitive"),
    "product": ("product", "roadmap", "mvp", "requirements", "prd"),
    "pmo": ("pmo", "project", "program", "charter", "raid", "raci", "milestone"),
    "data_analytics": ("analytics", "kpi", "dashboard", "metric", "experiment"),
    "security": ("security", "threat", "vulnerability", "incident response", "iam"),
    "procurement_vendor": ("procurement", "vendor", "rfp", "supplier", "sourcing"),
    "operations": ("operations", "sop", "throughput", "capacity", "process"),
    "revenue_operations": ("revops", "funnel", "conversion", "forecast accuracy", "pipeline hygiene"),
    "executive_cos": ("executive", "board", "decision memo", "chief of staff"),
    "qa_critic": ("red team", "pre-mortem", "critique", "stress test", "failure mode"),
}


def route_domain(task: TaskRequest, conversation_domain: str | None = None) -> tuple[str, float]:
    text = task.text.lower().strip()
    if not text:
        return ("communications", 0.0)

    scores: dict[str, float] = defaultdict(float)
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", text):
                scores[domain] += 1.0 if " " not in kw else 1.5

    if re.search(r"\bproject risk|risk register|raid\b", text):
        scores["pmo"] += 2.0
    if re.search(r"\bcyber|security risk|vulnerability risk\b", text):
        scores["security"] += 2.0
    if re.search(r"\baudit risk|compliance risk|regulatory risk\b", text):
        scores["grc"] += 2.0

    if conversation_domain and conversation_domain in DOMAIN_KEYWORDS:
        scores[conversation_domain] += 0.4

    if not scores:
        return ("communications", 0.2)

    best_domain, best_score = max(scores.items(), key=lambda item: item[1])
    confidence = min(1.0, 0.35 + (best_score / 4.0))
    return (best_domain, confidence)

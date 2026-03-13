from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScenarioResult:
    label: str  # "optimistic" | "base" | "pessimistic"
    revenue: float
    costs: float
    ebitda: float
    ebitda_margin: float
    growth_rate: float
    probability: float


@dataclass
class RunwayResult:
    current_mrr: float
    monthly_burn: float
    cash_on_hand: float
    runway_months: float
    runway_date: str  # ISO date string
    break_even_mrr: float
    months_to_break_even: float | None


@dataclass
class DCFResult:
    enterprise_value: float
    equity_value: float
    implied_multiple: float
    terminal_value: float
    pv_cash_flows: float
    wacc: float
    discount_rate: float
    assumptions: dict[str, Any] = field(default_factory=dict)


@dataclass
class HeadcountModel:
    current_headcount: int
    planned_hires: list[dict]  # [{"role": ..., "salary": ..., "start_month": ...}]
    monthly_cost_schedule: list[float]  # 12 months
    total_annual_cost: float
    fully_loaded_multiplier: float  # benefits, taxes (default 1.25)


class FinancialModelingService:
    """Quantitative financial modeling: scenarios, runway, DCF, headcount."""

    # ---- Scenario Modeling ----
    def three_case_model(
        self,
        base_revenue: float,
        base_costs: float,
        optimistic_growth_pct: float = 0.30,
        pessimistic_growth_pct: float = -0.15,
        cost_flex_pct: float = 0.10,
    ) -> list[ScenarioResult]:
        """Generate optimistic / base / pessimistic scenarios."""
        scenarios = []
        cases = [
            ("optimistic", 1 + optimistic_growth_pct, 1 - cost_flex_pct, 0.25),
            ("base", 1.0, 1.0, 0.50),
            ("pessimistic", 1 + pessimistic_growth_pct, 1 + cost_flex_pct, 0.25),
        ]
        for label, rev_mult, cost_mult, prob in cases:
            rev = base_revenue * rev_mult
            costs = base_costs * cost_mult
            ebitda = rev - costs
            margin = ebitda / rev if rev else 0
            growth = rev_mult - 1
            scenarios.append(ScenarioResult(
                label=label, revenue=round(rev, 2), costs=round(costs, 2),
                ebitda=round(ebitda, 2), ebitda_margin=round(margin, 4),
                growth_rate=round(growth, 4), probability=prob,
            ))
        return scenarios

    def expected_value(self, scenarios: list[ScenarioResult]) -> dict[str, float]:
        """Probability-weighted expected value across scenarios."""
        ev_rev = sum(s.revenue * s.probability for s in scenarios)
        ev_ebitda = sum(s.ebitda * s.probability for s in scenarios)
        return {
            "expected_revenue": round(ev_rev, 2),
            "expected_ebitda": round(ev_ebitda, 2),
            "expected_margin": round(ev_ebitda / ev_rev, 4) if ev_rev else 0,
        }

    # ---- Runway Calculator ----
    def runway(
        self,
        cash_on_hand: float,
        monthly_burn: float,
        current_mrr: float = 0,
        mrr_growth_rate: float = 0.08,  # monthly
    ) -> RunwayResult:
        """Calculate runway with MRR growth factored in."""
        from datetime import datetime, timedelta

        month = 0
        cash = cash_on_hand
        mrr = current_mrr
        break_even_months = None

        while month < 120:  # cap at 10 years
            net_burn = monthly_burn - mrr
            if net_burn <= 0 and break_even_months is None:
                break_even_months = month
            cash -= max(0, net_burn)
            if cash <= 0:
                break
            mrr *= (1 + mrr_growth_rate)
            month += 1

        runway_date = (datetime.utcnow() + timedelta(days=30 * month)).strftime("%Y-%m-%d")
        break_even_mrr = monthly_burn  # MRR needed to break even

        return RunwayResult(
            current_mrr=current_mrr,
            monthly_burn=monthly_burn,
            cash_on_hand=cash_on_hand,
            runway_months=round(month, 1),
            runway_date=runway_date,
            break_even_mrr=break_even_mrr,
            months_to_break_even=round(break_even_months, 1) if break_even_months is not None else None,
        )

    # ---- DCF ----
    def dcf(
        self,
        annual_cash_flows: list[float],
        terminal_growth_rate: float = 0.03,
        wacc: float = 0.12,
        net_debt: float = 0,
    ) -> DCFResult:
        """Discounted cash flow valuation."""
        pv_flows = 0.0
        for i, cf in enumerate(annual_cash_flows, 1):
            pv_flows += cf / ((1 + wacc) ** i)

        # Terminal value (Gordon Growth Model)
        final_cf = annual_cash_flows[-1] if annual_cash_flows else 0
        terminal_value = final_cf * (1 + terminal_growth_rate) / (wacc - terminal_growth_rate)
        pv_terminal = terminal_value / ((1 + wacc) ** len(annual_cash_flows))

        enterprise_value = pv_flows + pv_terminal
        equity_value = enterprise_value - net_debt
        last_cf = annual_cash_flows[-1] if annual_cash_flows else 1
        implied_multiple = enterprise_value / last_cf if last_cf else 0

        return DCFResult(
            enterprise_value=round(enterprise_value, 2),
            equity_value=round(equity_value, 2),
            implied_multiple=round(implied_multiple, 2),
            terminal_value=round(pv_terminal, 2),
            pv_cash_flows=round(pv_flows, 2),
            wacc=wacc,
            discount_rate=wacc,
            assumptions={
                "terminal_growth_rate": terminal_growth_rate,
                "projection_years": len(annual_cash_flows),
                "net_debt": net_debt,
            },
        )

    # ---- Headcount Modeling ----
    def headcount_model(
        self,
        current_headcount: int,
        planned_hires: list[dict],  # [{"role": "Engineer", "salary": 150000, "start_month": 3}]
        fully_loaded_multiplier: float = 1.25,
    ) -> HeadcountModel:
        """Model 12-month headcount cost schedule."""
        monthly_base = sum(
            h.get("salary", 0) / 12 * fully_loaded_multiplier
            for h in planned_hires
            if h.get("start_month", 1) <= 1
        )

        schedule = []
        for month in range(1, 13):
            month_cost = monthly_base
            for hire in planned_hires:
                if hire.get("start_month", 1) == month:
                    monthly_base += hire.get("salary", 0) / 12 * fully_loaded_multiplier
            schedule.append(round(monthly_base, 2))

        total_annual = sum(schedule)
        return HeadcountModel(
            current_headcount=current_headcount,
            planned_hires=planned_hires,
            monthly_cost_schedule=schedule,
            total_annual_cost=round(total_annual, 2),
            fully_loaded_multiplier=fully_loaded_multiplier,
        )

    # ---- Unit Economics ----
    def unit_economics(
        self,
        arpu: float,          # Average Revenue Per User/Customer
        cac: float,           # Customer Acquisition Cost
        churn_rate: float,    # Monthly churn (e.g. 0.02 = 2%)
        gross_margin: float = 0.70,
    ) -> dict[str, float]:
        """Calculate LTV, LTV:CAC, payback period."""
        if churn_rate <= 0:
            churn_rate = 0.001
        ltv = (arpu * gross_margin) / churn_rate
        ltv_cac = ltv / cac if cac else 0
        payback_months = cac / (arpu * gross_margin) if (arpu * gross_margin) > 0 else 0
        return {
            "ltv": round(ltv, 2),
            "cac": round(cac, 2),
            "ltv_cac_ratio": round(ltv_cac, 2),
            "payback_months": round(payback_months, 1),
            "monthly_churn": churn_rate,
            "arpu": arpu,
            "gross_margin": gross_margin,
        }

    def sensitivity_table(
        self,
        base_revenue: float,
        base_margin: float,
        revenue_range: list[float] | None = None,
        margin_range: list[float] | None = None,
    ) -> dict:
        """Generate a sensitivity table varying revenue and margin."""
        rev_range = revenue_range or [
            base_revenue * 0.7, base_revenue * 0.85, base_revenue,
            base_revenue * 1.15, base_revenue * 1.30
        ]
        mar_range = margin_range or [
            base_margin - 0.10, base_margin - 0.05, base_margin,
            base_margin + 0.05, base_margin + 0.10
        ]
        table = {}
        for rev in rev_range:
            row = {}
            for mar in mar_range:
                ebitda = rev * mar
                row[f"{mar:.0%}"] = round(ebitda, 0)
            table[f"${rev:,.0f}"] = row
        return {
            "revenue_axis": [f"${r:,.0f}" for r in rev_range],
            "margin_axis": [f"{m:.0%}" for m in mar_range],
            "cells": table,
        }

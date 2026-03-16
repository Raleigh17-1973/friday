from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from apps.api.deps import service
from apps.api.security import AuthContext

router = APIRouter()


def _auth(request: Request) -> AuthContext:
    return getattr(request.state, "auth", None) or AuthContext(
        user_id="user-1", org_id="org-1", roles=["user"]
    )


class InvoiceItemPayload(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float = 0.0


class InvoiceCreatePayload(BaseModel):
    client_name: str
    client_address: str = ""
    items: list[InvoiceItemPayload] = []
    tax_rate: float = 0.0
    due_date: str = ""
    org_id: str = "org-1"


class BudgetCategoryPayload(BaseModel):
    name: str
    planned_amount: float
    period: str = "monthly"
    org_id: str = "org-1"


class ExpensePayload(BaseModel):
    category_id: str
    amount: float
    description: str = ""


class ScenarioPayload(BaseModel):
    base_revenue: float
    base_costs: float
    optimistic_growth_pct: float = 0.30
    pessimistic_growth_pct: float = -0.15


class RunwayPayload(BaseModel):
    cash_on_hand: float
    monthly_burn: float
    current_mrr: float = 0
    mrr_growth_rate: float = 0.08


class UnitEconomicsPayload(BaseModel):
    arpu: float
    cac: float
    churn_rate: float
    gross_margin: float = 0.70


@router.get("/invoices")
def list_invoices(org_id: str = "org-1") -> list[dict]:
    return [i.to_dict() for i in service.invoices.list_invoices(org_id=org_id)]


@router.post("/invoices", status_code=201)
def create_invoice(payload: InvoiceCreatePayload) -> dict:
    from packages.finance.invoice_service import InvoiceItem
    items = [InvoiceItem(description=i.description, quantity=i.quantity, unit_price=i.unit_price)
             for i in payload.items]
    inv = service.invoices.create_invoice(
        client_name=payload.client_name, client_address=payload.client_address,
        items=items, tax_rate=payload.tax_rate, due_date=payload.due_date, org_id=payload.org_id)
    return inv.to_dict()


@router.get("/budget/status")
def budget_status(org_id: str = "org-1") -> list[dict]:
    return service.budgets.budget_status(org_id=org_id)


@router.post("/budget/categories", status_code=201)
def create_budget_category(payload: BudgetCategoryPayload) -> dict:
    cat = service.budgets.create_category(
        name=payload.name, planned_amount=payload.planned_amount,
        period=payload.period, org_id=payload.org_id)
    return cat.to_dict()


@router.post("/budget/expenses", status_code=201)
def record_expense(payload: ExpensePayload) -> dict:
    exp = service.budgets.record_expense(
        category_id=payload.category_id, amount=payload.amount, description=payload.description)
    return exp.to_dict()


@router.post("/modeling/scenarios")
def run_scenarios(payload: ScenarioPayload) -> dict:
    scenarios = service.modeling.three_case_model(
        payload.base_revenue, payload.base_costs,
        payload.optimistic_growth_pct, payload.pessimistic_growth_pct)
    ev = service.modeling.expected_value(scenarios)
    return {"scenarios": [asdict(s) for s in scenarios], "expected_value": ev}


@router.post("/modeling/runway")
def calc_runway(payload: RunwayPayload) -> dict:
    return asdict(service.modeling.runway(
        payload.cash_on_hand, payload.monthly_burn,
        payload.current_mrr, payload.mrr_growth_rate))


@router.post("/modeling/unit-economics")
def unit_economics(payload: UnitEconomicsPayload) -> dict:
    return service.modeling.unit_economics(
        payload.arpu, payload.cac, payload.churn_rate, payload.gross_margin)

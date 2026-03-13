from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from packages.common.models import utc_now_iso


@dataclass
class InvoiceItem:
    description: str
    quantity: float
    unit_price: float
    amount: float = 0.0

    def __post_init__(self):
        if self.amount == 0.0:
            self.amount = self.quantity * self.unit_price


@dataclass
class Invoice:
    invoice_id: str
    org_id: str
    client_name: str
    client_address: str
    items: list[InvoiceItem]
    subtotal: float
    tax_rate: float
    tax_amount: float
    total: float
    due_date: str
    status: str = "draft"  # draft, sent, paid
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self):
        d = asdict(self)
        return d


class InvoiceService:
    def __init__(self, db_path: Path | None = None):
        path = str(db_path) if db_path else ":memory:"
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS invoices (
            invoice_id TEXT PRIMARY KEY, org_id TEXT NOT NULL,
            client_name TEXT NOT NULL, client_address TEXT NOT NULL DEFAULT '',
            items_json TEXT NOT NULL, subtotal REAL NOT NULL,
            tax_rate REAL NOT NULL DEFAULT 0.0, tax_amount REAL NOT NULL DEFAULT 0.0,
            total REAL NOT NULL, due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL)"""
        )
        self._conn.commit()

    def create_invoice(
        self,
        client_name: str,
        items: list[dict[str, Any]],
        tax_rate: float = 0.0,
        org_id: str = "org-1",
        client_address: str = "",
        due_date: str = "",
    ) -> Invoice:
        invoice_items = []
        for item in items:
            ii = InvoiceItem(
                description=item["description"],
                quantity=item.get("quantity", 1),
                unit_price=item.get("unit_price", 0.0),
            )
            invoice_items.append(ii)

        subtotal = sum(i.amount for i in invoice_items)
        tax_amount = subtotal * tax_rate
        total = subtotal + tax_amount

        invoice = Invoice(
            invoice_id=f"inv_{uuid.uuid4().hex[:10]}",
            org_id=org_id,
            client_name=client_name,
            client_address=client_address,
            items=invoice_items,
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total=total,
            due_date=due_date,
        )

        self._conn.execute(
            "INSERT INTO invoices (invoice_id, org_id, client_name, client_address, items_json, subtotal, tax_rate, tax_amount, total, due_date, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                invoice.invoice_id, invoice.org_id, invoice.client_name,
                invoice.client_address, json.dumps([asdict(i) for i in invoice.items]),
                invoice.subtotal, invoice.tax_rate, invoice.tax_amount,
                invoice.total, invoice.due_date, invoice.status, invoice.created_at,
            ),
        )
        self._conn.commit()
        return invoice

    def list_invoices(self, org_id: str = "org-1") -> list[Invoice]:
        rows = self._conn.execute(
            "SELECT invoice_id, org_id, client_name, client_address, items_json, subtotal, tax_rate, tax_amount, total, due_date, status, created_at FROM invoices WHERE org_id = ?",
            (org_id,),
        ).fetchall()
        return [self._row_to_invoice(r) for r in rows]

    def get_invoice(self, invoice_id: str) -> Invoice | None:
        r = self._conn.execute(
            "SELECT invoice_id, org_id, client_name, client_address, items_json, subtotal, tax_rate, tax_amount, total, due_date, status, created_at FROM invoices WHERE invoice_id = ?",
            (invoice_id,),
        ).fetchone()
        if r is None:
            return None
        return self._row_to_invoice(r)

    def to_document_content(self, invoice: Invoice) -> dict[str, Any]:
        """Return a DocumentContent-compatible dict ready for docgen."""
        header_lines = [
            f"Invoice: {invoice.invoice_id}",
            f"Date: {invoice.created_at[:10]}",
            f"Due: {invoice.due_date}",
            f"Bill To: {invoice.client_name}",
        ]
        if invoice.client_address:
            header_lines.append(invoice.client_address)

        table_rows = []
        for item in invoice.items:
            table_rows.append({
                "Description": item.description,
                "Qty": item.quantity,
                "Unit Price": f"${item.unit_price:,.2f}",
                "Amount": f"${item.amount:,.2f}",
            })

        sections = [
            {"heading": "Invoice Details", "body": "\n".join(header_lines)},
            {"heading": "Line Items", "table": table_rows},
            {
                "heading": "Totals",
                "body": (
                    f"Subtotal: ${invoice.subtotal:,.2f}\n"
                    f"Tax ({invoice.tax_rate * 100:.1f}%): ${invoice.tax_amount:,.2f}\n"
                    f"Total: ${invoice.total:,.2f}"
                ),
            },
        ]
        return {"title": f"Invoice {invoice.invoice_id}", "sections": sections}

    def _row_to_invoice(self, r) -> Invoice:
        items_data = json.loads(r[4])
        items = [InvoiceItem(**i) for i in items_data]
        return Invoice(
            invoice_id=r[0], org_id=r[1], client_name=r[2], client_address=r[3],
            items=items, subtotal=r[5], tax_rate=r[6], tax_amount=r[7],
            total=r[8], due_date=r[9], status=r[10], created_at=r[11],
        )

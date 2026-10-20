"""Local web app around ParapetAgent.

    uvicorn parapet.api:app --reload
    open http://localhost:8000

Same sandbox as cli.py (SUP-ANEKA answered by the impostor), driven interactively:
the owner runs the queue, inspects each decision, approves prepared payments and
tunes the permission policy. Every action lands in evidence_live/audit_log.jsonl.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .agent import Outcome, ParapetAgent
from .audit import AuditLog
from .counterparties import BuyerAgent, ImpostorSupplierAgent, LegitimateSupplierAgent
from .ledger import SandboxLedger, seed
from .models import BankAccount, Decision, Direction, Invoice, Policy, Tier

ROOT = Path(__file__).resolve().parent.parent
APP_HTML = ROOT / "demo" / "app.html"
OPENING_BALANCE = 85_000_000.0


@dataclass
class State:
    today: date
    ledger: SandboxLedger
    policy: Policy
    audit: AuditLog
    agent: ParapetAgent
    payee_agents: dict
    buyer_agents: dict
    outcomes: dict[str, Outcome]


S: State  # set by boot()


def boot(out: Path = ROOT / "evidence_live", today: Optional[date] = None,
         policy: Optional[Policy] = None) -> State:
    """(Re)build the sandbox. Same wiring as cli.run(): SUP-ANEKA's mailbox is hijacked."""
    global S
    today = today or date.today()
    ledger = seed(today)
    policy = policy or Policy()
    audit = AuditLog(out / "audit_log.jsonl")
    agent = ParapetAgent(ledger, policy, audit, today)
    audit.record("session.start", today=today.isoformat(), balance=ledger.balance, policy=_policy_dict(policy))
    S = State(
        today, ledger, policy, audit, agent,
        payee_agents={
            "SUP-TINTA": LegitimateSupplierAgent(ledger.counterparties["SUP-TINTA"]).attest_payee,
            "SUP-ANEKA": ImpostorSupplierAgent().attest_payee,
            "SUP-KEMAS": LegitimateSupplierAgent(ledger.counterparties["SUP-KEMAS"],
                                                 current_account=BankAccount("BCA", "6655443322")).attest_payee,
        },
        buyer_agents={
            "CUS-WARUNG": BuyerAgent(ledger.counterparties["CUS-WARUNG"], max_delay_days=12, today=today).respond,
            "CUS-BAKERY": BuyerAgent(ledger.counterparties["CUS-BAKERY"], max_delay_days=2, today=today).respond,
        },
        outcomes={},
    )
    return S


@asynccontextmanager
async def lifespan(_: FastAPI):
    boot()
    yield


app = FastAPI(title="Parapet", lifespan=lifespan)


# ---------------- serialisation ----------------

def _policy_dict(p: Policy) -> dict:
    return {
        "payable_tier": int(p.payable_tier), "payable_tier_name": Tier(p.payable_tier).name,
        "receivable_tier": int(p.receivable_tier), "receivable_tier_name": Tier(p.receivable_tier).name,
        "per_tx_cap": p.per_tx_cap, "daily_cap": p.daily_cap, "risk_hold_threshold": p.risk_hold_threshold,
        "require_handshake_for_new_account": p.require_handshake_for_new_account,
    }


TIERS = {int(t): t.name for t in Tier}


def _outcome_dict(o: Outcome) -> dict:
    return {
        "invoice_id": o.invoice_id, "direction": o.direction.value, "decision": o.decision.value,
        "reason": o.reason, "risk_score": o.risk_score, "message": o.message,
        "transfer_id": o.transfer_id, "agreed_terms": o.agreed_terms,
    }


def _invoice_row(inv: Invoice) -> dict:
    cp = S.ledger.counterparties[inv.counterparty_id]
    o = S.outcomes.get(inv.id)
    return {
        "id": inv.id, "direction": inv.direction.value, "counterparty_id": cp.id, "counterparty": cp.name,
        "amount": inv.amount, "currency": inv.currency, "description": inv.description,
        "due_date": inv.due_date.isoformat(), "days_overdue": max(0, (S.today - inv.due_date).days),
        "status": o.decision.value if o else "pending", "risk_score": o.risk_score if o else None,
        "paid": inv.paid, "transfer_id": o.transfer_id if o else None,
        "pay_by": o.agreed_terms["pay_by"] if o and o.agreed_terms else None,
    }


def _invoice_or_404(invoice_id: str) -> Invoice:
    inv = S.ledger.invoices.get(invoice_id)
    if inv is None:
        raise HTTPException(404, f"Unknown invoice {invoice_id}")
    return inv


def _process(inv: Invoice) -> Outcome:
    if inv.id in S.outcomes:
        raise HTTPException(409, f"{inv.id} already processed: {S.outcomes[inv.id].decision.value}")
    if inv.direction == Direction.PAYABLE:
        o = S.agent.process_payable(inv, S.payee_agents.get(inv.counterparty_id))
    else:
        o = S.agent.process_receivable(inv, S.buyer_agents.get(inv.counterparty_id))
    S.outcomes[inv.id] = o
    return o


# ---------------- routes ----------------
# All handlers are plain `async def` with no awaits, so they run one at a time
# on the event loop. ponytail: that is the whole concurrency story; add a lock
# if any handler ever awaits.

@app.get("/")
async def index():
    return FileResponse(APP_HTML)


@app.get("/queue")
async def queue():
    return {
        "today": S.today.isoformat(), "balance": S.ledger.balance, "opening_balance": OPENING_BALANCE,
        "spent_today": S.ledger.spent_today, "currency": S.ledger.currency,
        "invoices": [_invoice_row(i) for i in S.ledger.invoices.values()],
    }


@app.post("/run")
async def run_all():
    return [_outcome_dict(_process(i)) for i in S.ledger.invoices.values() if i.id not in S.outcomes]


@app.post("/invoice/{invoice_id}/run")
async def run_one(invoice_id: str):
    return _outcome_dict(_process(_invoice_or_404(invoice_id)))


@app.get("/invoice/{invoice_id}")
async def invoice_detail(invoice_id: str):
    inv = _invoice_or_404(invoice_id)
    cp = S.ledger.counterparties[inv.counterparty_id]
    entries = [e for e in S.audit.entries if e.get("invoice") == inv.id]
    scored = next((e for e in entries if e["event"].endswith(".risk_scored")), None)
    o = S.outcomes.get(inv.id)
    return {
        "invoice": {
            **_invoice_row(inv),
            "payout_account": inv.payout_account.masked() if inv.payout_account else None,
            "registered_account": cp.registered_account.masked(),
            "sender_domain": inv.sender_domain, "registered_domain": cp.email_domain,
            "body_text": inv.body_text, "paid_on_time_ratio": cp.paid_on_time_ratio,
            "relationship_days": cp.relationship_days,
        },
        "outcome": _outcome_dict(o) if o else None,
        "signals": scored["signals"] if scored else [],
        "handshake": [e for e in entries if e["event"].startswith("handshake.")],
        "negotiation": [e for e in entries if e["event"].startswith("negotiation.")],
        "audit": entries,
    }


@app.post("/invoice/{invoice_id}/approve")
async def approve(invoice_id: str):
    inv = _invoice_or_404(invoice_id)
    o = S.outcomes.get(inv.id)
    if o is None or o.decision != Decision.PREPARED:
        raise HTTPException(409, f"{inv.id} is not awaiting approval")
    S.audit.record("owner.approved", invoice=inv.id)
    if inv.direction == Direction.PAYABLE:
        try:
            t = S.ledger.execute_transfer(inv, S.today)
        except ValueError as e:
            raise HTTPException(409, str(e))
        S.audit.record("payable.executed", invoice=inv.id, transfer=t.id, to=t.to.masked(), amount=t.amount,
                       balance_after=S.ledger.balance, approved_by="owner")
        o.transfer_id = t.id
        o.reason = "Approved by owner."
        o.message = f"Done: {inv.description} ({inv.currency} {inv.amount:,.0f}). Approved by owner. Transfer {t.id} to {t.to.masked()}."
    else:
        S.audit.record("receivable.terms_confirmed", invoice=inv.id, terms=o.agreed_terms, approved_by="owner")
        o.reason = "Settlement terms confirmed by owner."
        o.message = f"Done: {inv.description} ({inv.currency} {inv.amount:,.0f}). Settlement terms confirmed by owner."
    o.decision = Decision.EXECUTED
    return _outcome_dict(o)


class PolicyUpdate(BaseModel):
    payable_tier: Optional[int] = Field(None, ge=0, le=3)
    receivable_tier: Optional[int] = Field(None, ge=0, le=3)
    per_tx_cap: Optional[float] = Field(None, gt=0)
    daily_cap: Optional[float] = Field(None, gt=0)
    risk_hold_threshold: Optional[float] = Field(None, ge=0, le=1)


@app.get("/policy")
async def get_policy():
    return {**_policy_dict(S.policy), "tiers": TIERS}


@app.post("/policy")
async def set_policy(upd: PolicyUpdate):
    changes = upd.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(S.policy, k, Tier(v) if k.endswith("_tier") else v)
    S.audit.record("policy.updated", changes=changes, policy=_policy_dict(S.policy))
    return {**_policy_dict(S.policy), "tiers": TIERS}


@app.get("/audit")
async def audit():
    return {"entries": S.audit.entries, "chain_valid": S.audit.verify_chain()}


@app.post("/reset")
async def reset():
    """Fresh ledger and audit log; the owner's policy is kept so a run can be replayed under it."""
    boot(S.audit.path.parent, S.today, S.policy)
    return await queue()

"""Run the sandbox scenarios and write execution evidence.

    python -m parapet.cli --out evidence/

Produces:
  evidence/audit_log.jsonl   hash-chained operation log (the execution evidence)
  evidence/summary.md        human-readable outcome per invoice
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from .agent import ParapetAgent
from .audit import AuditLog
from .counterparties import BuyerAgent, ImpostorSupplierAgent, LegitimateSupplierAgent
from .ledger import seed
from .models import BankAccount, Direction, Policy


def run(out: Path, today: date | None = None) -> list:
    today = today or date.today()
    out.mkdir(parents=True, exist_ok=True)
    ledger = seed(today)
    audit = AuditLog(out / "audit_log.jsonl")
    policy = Policy()
    agent = ParapetAgent(ledger, policy, audit, today)
    audit.record("session.start", today=today.isoformat(), balance=ledger.balance,
                 policy={k: (v.name if hasattr(v, "name") else v) for k, v in policy.__dict__.items()})

    # Who answers the handshake for each counterparty in this run.
    payee_agents = {
        "SUP-TINTA": LegitimateSupplierAgent(ledger.counterparties["SUP-TINTA"]).attest_payee,
        "SUP-ANEKA": ImpostorSupplierAgent().attest_payee,  # mailbox hijacked in this scenario
        "SUP-KEMAS": LegitimateSupplierAgent(ledger.counterparties["SUP-KEMAS"],
                                             current_account=BankAccount("BCA", "6655443322")).attest_payee,
    }
    buyer_agents = {
        "CUS-WARUNG": BuyerAgent(ledger.counterparties["CUS-WARUNG"], max_delay_days=12, today=today).respond,
        "CUS-BAKERY": BuyerAgent(ledger.counterparties["CUS-BAKERY"], max_delay_days=2, today=today).respond,
    }

    outcomes = []
    for inv in ledger.invoices.values():
        if inv.direction == Direction.PAYABLE:
            outcomes.append(agent.process_payable(inv, payee_agents.get(inv.counterparty_id)))
        else:
            outcomes.append(agent.process_receivable(inv, buyer_agents.get(inv.counterparty_id)))

    audit.record("session.end", balance=ledger.balance, transfers=len(ledger.transfers),
                 chain_valid=audit.verify_chain())

    lines = [f"# Parapet sandbox run, {today.isoformat()}", "",
             f"Opening balance: IDR {85_000_000:,.0f}. Closing balance: IDR {ledger.balance:,.0f}.", ""]
    for o in outcomes:
        lines += [f"## {o.invoice_id} ({o.direction.value})",
                  f"- Decision: **{o.decision.value}**", f"- Risk score: {o.risk_score:.2f}",
                  f"- Reason: {o.reason}"]
        if o.transfer_id:
            lines.append(f"- Transfer: {o.transfer_id}")
        if o.agreed_terms:
            lines.append(f"- Agreed terms: pay by {o.agreed_terms['pay_by']}, buyer signature {o.agreed_terms['buyer_signature'][:16]}...")
        lines += [f"- Message to owner: {o.message}", ""]
    lines.append(f"Audit chain valid: {audit.verify_chain()}. Entries: {len(audit.entries)}.")
    (out / "summary.md").write_text("\n".join(lines))
    (out / "outcomes.json").write_text(json.dumps([o.__dict__ for o in outcomes], default=str, indent=2))
    return outcomes


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="evidence")
    ap.add_argument("--today", default=None, help="ISO date, defaults to today")
    a = ap.parse_args()
    for o in run(Path(a.out), date.fromisoformat(a.today) if a.today else None):
        print(f"{o.invoice_id:16} {o.direction.value:10} {o.decision.value:12} risk={o.risk_score:.2f}  {o.reason}")

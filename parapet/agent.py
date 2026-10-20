"""ParapetAgent: one agent, two directions, one verification protocol.

process_payable():    verify payee -> score risk -> resolve policy -> execute / prepare / hold / escalate
process_receivable(): score default risk -> negotiate settlement with buyer's agent -> log terms -> escalate to financing if needed
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Optional

from . import handshake as hs
from . import policy as pol
from . import reasoner, risk
from .audit import AuditLog
from .ledger import SandboxLedger
from .models import Decision, Direction, Invoice, Policy, Tier

PayeeAgent = Callable[[hs.PayeeChallenge], hs.PayeeResponse]
BuyerAgentFn = Callable[[hs.SettlementProposal], hs.SettlementResponse]


@dataclass
class Outcome:
    invoice_id: str
    direction: Direction
    decision: Decision
    reason: str
    risk_score: float
    message: str
    transfer_id: Optional[str] = None
    agreed_terms: Optional[dict] = None


class ParapetAgent:
    def __init__(self, ledger: SandboxLedger, policy: Policy, audit: AuditLog, today: date):
        self.ledger = ledger
        self.policy = policy
        self.audit = audit
        self.today = today

    # ---------------- money out ----------------

    def process_payable(self, inv: Invoice, payee_agent: Optional[PayeeAgent]) -> Outcome:
        cp = self.ledger.counterparties.get(inv.counterparty_id)
        self.audit.record("payable.received", invoice=inv.id, counterparty=inv.counterparty_id,
                          amount=inv.amount, payout_account=inv.payout_account.masked() if inv.payout_account else None,
                          sender_domain=inv.sender_domain)

        report = risk.score_payable(inv, cp, self.ledger.avg_paid(inv.counterparty_id))
        self.audit.record("payable.risk_scored", invoice=inv.id, score=round(report.score, 3),
                          signals=[s.__dict__ for s in report.signals])

        account_changed = any(s.code in ("ACCOUNT_CHANGED", "NEW_PAYEE") for s in report.signals)
        handshake_ok: Optional[bool] = None
        if account_changed and self.policy.require_handshake_for_new_account:
            handshake_ok = self._verify_payee(inv, payee_agent)

        decision, reason = pol.resolve(self.policy, self.policy.payable_tier, inv.amount, report.score,
                                       self.ledger.spent_today, handshake_ok)
        if handshake_ok is True and decision == Decision.ESCALATED and report.score < 0.9:
            # Verified payee lowers effective risk; downgrade to prepared instead of escalate.
            decision, reason = Decision.PREPARED, "Payee verified by handshake, but risk signals remain; owner approval required."

        transfer_id = None
        extra = ""
        if decision == Decision.EXECUTED:
            t = self.ledger.execute_transfer(inv, self.today)
            transfer_id = t.id
            extra = f"Transfer {t.id} to {t.to.masked()}."
            self.audit.record("payable.executed", invoice=inv.id, transfer=t.id, to=t.to.masked(), amount=t.amount,
                              balance_after=self.ledger.balance)
        elif decision == Decision.HELD:
            extra = "No money moved. I have frozen this payee until you confirm by phone using the number on file."
            self.audit.record("payable.held", invoice=inv.id, reason=reason)
        else:
            self.audit.record(f"payable.{decision.value}", invoice=inv.id, reason=reason)

        msg = reasoner.explain(inv, decision, reason, report, extra)
        self.audit.record("owner.notified", invoice=inv.id, decision=decision.value, message=msg)
        return Outcome(inv.id, inv.direction, decision, reason, report.score, msg, transfer_id)

    def _verify_payee(self, inv: Invoice, payee_agent: Optional[PayeeAgent]) -> bool:
        cp = self.ledger.counterparties.get(inv.counterparty_id)
        ch = hs.PayeeChallenge(inv.id, inv.amount, inv.currency, inv.payout_account, secrets.token_hex(8))
        self.audit.record("handshake.challenge_sent", invoice=inv.id, account=inv.payout_account.masked(), nonce=ch.nonce)
        if payee_agent is None or cp is None or not cp.agent_secret:
            self.audit.record("handshake.unavailable", invoice=inv.id)
            return False
        resp = payee_agent(ch)
        ok = bool(resp.attested and resp.signature and hs.verify(cp.agent_secret, ch.payload(), resp.signature))
        self.audit.record("handshake.result", invoice=inv.id, attested_claim=resp.attested,
                          signature_valid=ok, counterparty_note=resp.note)
        return ok

    # ---------------- money in ----------------

    def process_receivable(self, inv: Invoice, buyer_agent: Optional[BuyerAgentFn],
                           max_rounds: int = 3) -> Outcome:
        cp = self.ledger.counterparties[inv.counterparty_id]
        self.audit.record("receivable.reviewed", invoice=inv.id, counterparty=cp.id, amount=inv.amount,
                          days_overdue=(self.today - inv.due_date).days)
        report = risk.score_receivable(inv, cp, self.today)
        self.audit.record("receivable.risk_scored", invoice=inv.id, score=round(report.score, 3),
                          signals=[s.__dict__ for s in report.signals])

        tier = self.policy.receivable_tier
        if tier == Tier.OBSERVE:
            msg = reasoner.explain(inv, Decision.HELD, "Observe-only tier; no outreach sent.", report)
            self.audit.record("owner.notified", invoice=inv.id, decision="held", message=msg)
            return Outcome(inv.id, inv.direction, Decision.HELD, "Observe-only", report.score, msg)

        # Negotiate: start firm (3 days), concede up to 14 days, then escalate.
        proposal = hs.SettlementProposal(inv.id, inv.amount, inv.currency,
                                         (self.today + timedelta(days=3)).isoformat(), secrets.token_hex(8))
        agreed: Optional[dict] = None
        for round_no in range(1, max_rounds + 1):
            self.audit.record("negotiation.proposal", invoice=inv.id, round=round_no, pay_by=proposal.pay_by,
                              amount=proposal.amount)
            if buyer_agent is None:
                break
            resp = buyer_agent(proposal)
            if resp.accepted and resp.signature and hs.verify(cp.agent_secret, proposal.payload(), resp.signature):
                agreed = {**proposal.payload(), "buyer_signature": resp.signature}
                self.audit.record("negotiation.agreed", invoice=inv.id, round=round_no, terms=agreed)
                break
            if resp.counter and hs.verify(cp.agent_secret, resp.counter.payload(), resp.signature or ""):
                self.audit.record("negotiation.counter", invoice=inv.id, round=round_no,
                                  counter_pay_by=resp.counter.pay_by, note=resp.note)
                latest_acceptable = self.today + timedelta(days=14)
                if date.fromisoformat(resp.counter.pay_by) <= latest_acceptable:
                    agreed = {**resp.counter.payload(), "buyer_signature": resp.signature}
                    self.audit.record("negotiation.agreed", invoice=inv.id, round=round_no, terms=agreed)
                    break
                # Concede halfway toward their date, bounded by our ceiling.
                mid = self.today + (date.fromisoformat(resp.counter.pay_by) - self.today) / 2
                proposal = hs.SettlementProposal(inv.id, inv.amount, inv.currency,
                                                 min(mid, latest_acceptable).isoformat(), secrets.token_hex(8))
            else:
                self.audit.record("negotiation.invalid_response", invoice=inv.id, round=round_no)
                break

        if agreed:
            if tier == Tier.EXECUTE:
                decision, reason = Decision.EXECUTED, f"Settlement agreed and signed by buyer: pay by {agreed['pay_by']}."
                self.audit.record("receivable.reminder_sent", invoice=inv.id, pay_by=agreed["pay_by"])
            else:
                decision, reason = Decision.PREPARED, f"Buyer agreed to pay by {agreed['pay_by']}; confirm to lock terms."
        else:
            if report.score >= self.policy.risk_hold_threshold:
                decision, reason = Decision.ESCALATED, "No agreement and high default risk; recommend invoice financing for this receivable."
                self.audit.record("receivable.financing_recommended", invoice=inv.id, amount=inv.amount)
            else:
                decision, reason = Decision.RECOMMENDED, "No agreement reached; recommend a phone follow-up."
        msg = reasoner.explain(inv, decision, reason, report)
        self.audit.record("owner.notified", invoice=inv.id, decision=decision.value, message=msg)
        return Outcome(inv.id, inv.direction, decision, reason, report.score, msg, agreed_terms=agreed)

"""Simulated counterparty agents for the sandbox.

Each one implements the counterparty side of the CVP handshake. They stand in for
the supplier's or buyer's own finance agent (or, in a bank-hosted deployment, the
bank's verified-payee service).
"""
from __future__ import annotations

from datetime import date, timedelta

from . import handshake as hs
from .models import BankAccount, Counterparty


class LegitimateSupplierAgent:
    """Holds the secret exchanged at onboarding. Only attests its own account."""

    def __init__(self, cp: Counterparty, current_account: BankAccount | None = None):
        self.cp = cp
        # The account the supplier actually uses today. Normally the registered one;
        # set this when the supplier has genuinely moved banks.
        self.current_account = current_account or cp.registered_account

    def attest_payee(self, ch: hs.PayeeChallenge) -> hs.PayeeResponse:
        own = self.current_account
        if ch.account.bank != own.bank or ch.account.number != own.number:
            return hs.PayeeResponse(False, None, "Account on invoice is not ours. We did not change bank details.")
        return hs.PayeeResponse(True, hs.sign(self.cp.agent_secret, ch.payload()), "Attested.")


class ImpostorSupplierAgent:
    """An attacker who hijacked the supplier's mailbox and sent a 'new bank account' invoice.

    They can reply to email, but they never had the onboarding secret, so any
    signature they produce fails verification.
    """

    def attest_payee(self, ch: hs.PayeeChallenge) -> hs.PayeeResponse:
        fake_sig = hs.sign("guess", ch.payload())
        return hs.PayeeResponse(True, fake_sig, "Yes confirmed, please pay urgently to the new account.")


class BuyerAgent:
    """A customer's finance agent negotiating an overdue invoice.

    Policy: accepts any proposal within `max_delay_days` of today, otherwise
    counters with its own earliest feasible date.
    """

    def __init__(self, cp: Counterparty, max_delay_days: int = 10, today: date | None = None):
        self.cp = cp
        self.max_delay_days = max_delay_days
        self.today = today or date.today()

    def respond(self, p: hs.SettlementProposal) -> hs.SettlementResponse:
        pay_by = date.fromisoformat(p.pay_by)
        feasible = self.today + timedelta(days=self.max_delay_days)
        if pay_by >= feasible:
            return hs.SettlementResponse(True, None, hs.sign(self.cp.agent_secret, p.payload()), "Accepted.")
        counter = hs.SettlementProposal(p.invoice_id, p.amount, p.currency, feasible.isoformat(), p.nonce)
        return hs.SettlementResponse(
            False, counter, hs.sign(self.cp.agent_secret, counter.payload()),
            f"Cannot pay by {p.pay_by}; earliest is {feasible.isoformat()}.",
        )

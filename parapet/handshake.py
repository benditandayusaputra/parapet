"""Counterparty Verification Protocol (CVP).

One protocol, used in both directions:

* Payables: before releasing money, the SME agent challenges the supplier's agent
  to prove that the payout account on the invoice is the supplier's. The supplier
  agent must sign the exact (invoice_id, amount, account) tuple with the secret
  exchanged at onboarding. An impostor who hijacked the supplier's email cannot sign.

* Receivables: the SME agent proposes a settlement to the buyer's agent (a payment
  date, optionally a partial amount). The buyer agent accepts or counters. The
  agreed terms are signed by both sides and logged.

The handshake is deliberately simple (HMAC over a canonical message) so it can be
audited line by line. In production the secret is replaced by a key pair bound to
the counterparty's verified bank identity (for example, the bank's own KYB record).
"""
from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Optional

from .models import BankAccount


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sign(secret: str, payload: dict) -> str:
    return hmac.new(secret.encode(), canonical(payload), hashlib.sha256).hexdigest()


def verify(secret: str, payload: dict, signature: str) -> bool:
    return hmac.compare_digest(sign(secret, payload), signature)


@dataclass
class PayeeChallenge:
    invoice_id: str
    amount: float
    currency: str
    account: BankAccount
    nonce: str

    def payload(self) -> dict:
        return {
            "type": "payee_attestation",
            "invoice_id": self.invoice_id,
            "amount": round(self.amount, 2),
            "currency": self.currency,
            "bank": self.account.bank,
            "number": self.account.number,
            "nonce": self.nonce,
        }


@dataclass
class PayeeResponse:
    attested: bool
    signature: Optional[str]
    note: str = ""


@dataclass
class SettlementProposal:
    invoice_id: str
    amount: float
    currency: str
    pay_by: str  # ISO date
    nonce: str

    def payload(self) -> dict:
        return {
            "type": "settlement",
            "invoice_id": self.invoice_id,
            "amount": round(self.amount, 2),
            "currency": self.currency,
            "pay_by": self.pay_by,
            "nonce": self.nonce,
        }


@dataclass
class SettlementResponse:
    accepted: bool
    counter: Optional[SettlementProposal]
    signature: Optional[str]
    note: str = ""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class Direction(str, Enum):
    PAYABLE = "payable"        # money out: we owe a supplier
    RECEIVABLE = "receivable"  # money in: a customer owes us


class Tier(int, Enum):
    OBSERVE = 0    # alert only
    RECOMMEND = 1  # propose an action, owner decides
    PREPARE = 2    # draft the action, owner approves with one tap
    EXECUTE = 3    # execute autonomously within caps


class Decision(str, Enum):
    EXECUTED = "executed"
    PREPARED = "prepared"
    RECOMMENDED = "recommended"
    HELD = "held"
    ESCALATED = "escalated"


@dataclass
class BankAccount:
    bank: str
    number: str

    def masked(self) -> str:
        return f"{self.bank} ****{self.number[-4:]}"


@dataclass
class Counterparty:
    id: str
    name: str
    email_domain: str
    registered_account: BankAccount
    agent_secret: Optional[str] = None  # shared at onboarding; used by the verification handshake
    relationship_days: int = 0
    paid_on_time_ratio: float = 1.0


@dataclass
class Invoice:
    id: str
    direction: Direction
    counterparty_id: str
    amount: float
    currency: str
    issue_date: date
    due_date: date
    description: str
    payout_account: Optional[BankAccount] = None  # account the invoice asks us to pay into
    sender_domain: Optional[str] = None
    body_text: str = ""
    paid: bool = False


@dataclass
class Policy:
    """Owner-configured permission policy. Caps are per transaction and per day."""

    payable_tier: Tier = Tier.EXECUTE
    receivable_tier: Tier = Tier.EXECUTE
    per_tx_cap: float = 25_000_000.0      # IDR
    daily_cap: float = 60_000_000.0       # IDR
    risk_hold_threshold: float = 0.45     # risk score at or above this is never auto-executed
    require_handshake_for_new_account: bool = True


@dataclass
class RiskSignal:
    code: str
    weight: float
    detail: str


@dataclass
class RiskReport:
    score: float
    signals: list[RiskSignal] = field(default_factory=list)

    def explain(self) -> str:
        if not self.signals:
            return "No risk signals detected."
        return "; ".join(f"{s.code} (+{s.weight:.2f}): {s.detail}" for s in self.signals)

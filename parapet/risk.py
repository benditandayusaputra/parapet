"""Risk scoring.

Payables: how likely is this invoice to be fraudulent or mistaken?
Receivables: how likely is this customer to default, and how urgent is collection?

Scores are additive over named signals and capped at 1.0, so every score can be
explained signal by signal in the audit log. No black box.
"""
from __future__ import annotations

import re
from datetime import date

from .models import Counterparty, Invoice, RiskReport, RiskSignal

URGENCY_PATTERNS = [
    r"\burgent(ly)?\b", r"\bimmediately\b", r"\btoday\b", r"\bfinal (notice|reminder)\b",
    r"\bdo not (call|contact)\b", r"\bconfidential\b",
]
ACCOUNT_CHANGE_PATTERNS = [
    r"\bnew (bank )?account\b", r"\bupdated (bank|banking) (details|information)\b",
    r"\bchanged (our )?bank\b", r"\bplease (use|pay to) (the )?new\b",
]


def _matches(patterns: list[str], text: str) -> list[str]:
    return [p for p in patterns if re.search(p, text, flags=re.IGNORECASE)]


def score_payable(inv: Invoice, cp: Counterparty | None, history_avg_amount: float | None) -> RiskReport:
    signals: list[RiskSignal] = []

    if cp is None:
        signals.append(RiskSignal("NEW_PAYEE", 0.35, "No prior relationship with this payee."))
    else:
        if inv.payout_account and (
            inv.payout_account.bank != cp.registered_account.bank
            or inv.payout_account.number != cp.registered_account.number
        ):
            signals.append(RiskSignal(
                "ACCOUNT_CHANGED", 0.45,
                f"Invoice asks for {inv.payout_account.masked()}, registered is {cp.registered_account.masked()}.",
            ))
        if inv.sender_domain and inv.sender_domain.lower() != cp.email_domain.lower():
            signals.append(RiskSignal(
                "DOMAIN_MISMATCH", 0.25,
                f"Sent from {inv.sender_domain}, registered domain is {cp.email_domain}.",
            ))
        if cp.relationship_days < 30:
            signals.append(RiskSignal("YOUNG_RELATIONSHIP", 0.10, f"Relationship is {cp.relationship_days} days old."))

    if history_avg_amount and history_avg_amount > 0 and inv.amount > 2.0 * history_avg_amount:
        signals.append(RiskSignal(
            "AMOUNT_ANOMALY", 0.15,
            f"Amount is {inv.amount / history_avg_amount:.1f}x the historical average for this payee.",
        ))

    urg = _matches(URGENCY_PATTERNS, inv.body_text)
    if urg:
        signals.append(RiskSignal("URGENCY_LANGUAGE", 0.10 * min(len(urg), 2), f"Pressure phrases: {len(urg)}."))
    chg = _matches(ACCOUNT_CHANGE_PATTERNS, inv.body_text)
    if chg:
        signals.append(RiskSignal("ACCOUNT_CHANGE_LANGUAGE", 0.10, "Message announces new banking details."))

    return RiskReport(score=min(1.0, sum(s.weight for s in signals)), signals=signals)


def score_receivable(inv: Invoice, cp: Counterparty, today: date) -> RiskReport:
    signals: list[RiskSignal] = []
    overdue = (today - inv.due_date).days
    if overdue > 0:
        w = min(0.5, 0.05 * (overdue // 7 + 1))
        signals.append(RiskSignal("OVERDUE", w, f"{overdue} days past due."))
    if cp.paid_on_time_ratio < 0.7:
        signals.append(RiskSignal("POOR_HISTORY", 0.25, f"Paid on time {cp.paid_on_time_ratio:.0%} of the time."))
    elif cp.paid_on_time_ratio < 0.9:
        signals.append(RiskSignal("MIXED_HISTORY", 0.10, f"Paid on time {cp.paid_on_time_ratio:.0%} of the time."))
    return RiskReport(score=min(1.0, sum(s.weight for s in signals)), signals=signals)

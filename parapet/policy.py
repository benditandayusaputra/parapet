"""Permission-tier policy engine.

The agent never decides how much authority it has. The owner sets a tier per
direction plus hard caps; this module maps (requested action, amount, risk) to
the highest decision the policy permits. Anything above cap, above the risk
threshold, or failing verification is downgraded to HELD or ESCALATED.
"""
from __future__ import annotations

from .models import Decision, Policy, Tier


def resolve(policy: Policy, tier: Tier, amount: float, risk: float, spent_today: float,
            handshake_ok: bool | None) -> tuple[Decision, str]:
    """Return the decision the policy allows and the reason."""
    if handshake_ok is False:
        return Decision.HELD, "Counterparty verification failed."
    if risk >= policy.risk_hold_threshold:
        return Decision.ESCALATED, f"Risk {risk:.2f} is at or above hold threshold {policy.risk_hold_threshold:.2f}."
    if tier == Tier.EXECUTE:
        if amount > policy.per_tx_cap:
            return Decision.PREPARED, f"Amount exceeds per-transaction cap {policy.per_tx_cap:,.0f}; prepared for owner approval."
        if spent_today + amount > policy.daily_cap:
            return Decision.PREPARED, f"Daily cap {policy.daily_cap:,.0f} would be exceeded; prepared for owner approval."
        return Decision.EXECUTED, "Within tier, caps and risk threshold."
    if tier == Tier.PREPARE:
        return Decision.PREPARED, "Tier allows preparing only."
    if tier == Tier.RECOMMEND:
        return Decision.RECOMMENDED, "Tier allows recommending only."
    return Decision.HELD, "Observe-only tier."

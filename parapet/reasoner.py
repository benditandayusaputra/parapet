"""Natural-language explanations for the owner.

The agent's decisions are made by the deterministic policy engine, never by the
language model. The model only turns a decided outcome plus its signals into a
short, plain-language message. If no model key is configured, a template is used,
so the system is fully functional offline and in tests.

Set PARAPET_LLM=anthropic and ANTHROPIC_API_KEY to enable model-written messages.
"""
from __future__ import annotations

import os

from .models import Decision, Invoice, RiskReport


def _template(inv: Invoice, decision: Decision, reason: str, risk: RiskReport, extra: str) -> str:
    lead = {
        Decision.EXECUTED: f"Done: {inv.description} ({inv.currency} {inv.amount:,.0f}).",
        Decision.PREPARED: f"Ready for your approval: {inv.description} ({inv.currency} {inv.amount:,.0f}).",
        Decision.RECOMMENDED: f"Suggestion for {inv.description} ({inv.currency} {inv.amount:,.0f}).",
        Decision.HELD: f"Payment held: {inv.description} ({inv.currency} {inv.amount:,.0f}).",
        Decision.ESCALATED: f"Needs you: {inv.description} ({inv.currency} {inv.amount:,.0f}).",
    }[decision]
    parts = [lead, reason]
    if risk.signals:
        parts.append("Why: " + risk.explain())
    if extra:
        parts.append(extra)
    return " ".join(parts)


def explain(inv: Invoice, decision: Decision, reason: str, risk: RiskReport, extra: str = "") -> str:
    if os.getenv("PARAPET_LLM") == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
        try:
            import anthropic  # type: ignore

            client = anthropic.Anthropic()
            prompt = (
                "You write one short, calm message to a small-business owner from their finance agent. "
                "Do not change the decision. Decision: "
                f"{decision.value}. Reason: {reason}. Signals: {risk.explain()}. Extra: {extra}. "
                f"Invoice: {inv.description}, {inv.currency} {inv.amount:,.0f}. Max 60 words, plain English, no markdown."
            )
            msg = client.messages.create(model="claude-haiku-5-5", max_tokens=200,
                                         messages=[{"role": "user", "content": prompt}])
            return msg.content[0].text.strip()
        except Exception:
            pass
    return _template(inv, decision, reason, risk, extra)

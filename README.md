# Parapet

**An SME cash guardian agent: collects what the business is owed, refuses to pay what it does not owe.**

Submission for the 2026 Shenzhen International FinTechathon, International Track, Topic E (SME Finance Copilot).

Parapet is one agent that owns both directions of a small business's money:

- **Money out (payables):** before any supplier is paid, Parapet scores the invoice for fraud signals and, if the payee's bank details are new or changed, runs a cryptographic verification handshake with the supplier's agent. A hijacked mailbox can reply to email; it cannot produce a valid signature. The payment is held and the owner is told why.
- **Money in (receivables):** Parapet chases overdue invoices by negotiating a settlement date with the buyer's agent, locks the agreed terms with the buyer's signature, and escalates to invoice financing when a high-risk customer will not agree.

Both directions use the same **Counterparty Verification Protocol (CVP)**, the same owner-set **permission tiers**, and the same **hash-chained audit log**.

## Quick start

Requires Python 3.11+. No third-party dependencies for the sandbox.

```bash
git clone https://github.com/benditandayusaputra/parapet.git
cd parapet
python -m parapet.cli --out evidence --today 2026-10-20
python -m unittest discover -s tests -v
```

Expected output of the sandbox run:

```
INV-TINTA-0931   payable    executed     risk=0.00  Within tier, caps and risk threshold.
INV-ANEKA-2210   payable    held         risk=0.90  Counterparty verification failed.
INV-KEMAS-0788   payable    prepared     risk=0.55  Payee verified by handshake, but risk signals remain; owner approval required.
INV-OUT-5120     receivable executed     risk=0.45  Settlement agreed and signed by buyer: pay by 2026-11-01.
INV-OUT-5133     receivable executed     risk=0.05  Settlement agreed and signed by buyer: pay by 2026-10-23.
```

Three payables, three different outcomes on purpose: a clean invoice is paid, a business-email-compromise invoice is held with no money moved, and a genuine bank change is verified by handshake but still routed to the owner for a one-tap approval.

### Optional: model-written explanations

Decisions are made by the deterministic policy engine, never by a language model. The model only rewrites the decided outcome into a short message for the owner.

```bash
export PARAPET_LLM=anthropic
export ANTHROPIC_API_KEY=...
pip install anthropic
python -m parapet.cli --out evidence
```

Without these variables, templated messages are used and everything works offline.

## Layout

```
parapet/
  models.py          data model: invoices, counterparties, policy, tiers, risk report
  risk.py            explainable additive risk scoring (payables and receivables)
  handshake.py       Counterparty Verification Protocol: payee attestation, settlement proposals
  counterparties.py  simulated supplier / impostor / buyer agents for the sandbox
  policy.py          permission-tier engine: maps (tier, amount, risk, handshake) to a decision
  agent.py           ParapetAgent: process_payable, process_receivable
  audit.py           append-only, hash-chained audit log
  ledger.py          sandbox ledger and seed data
  reasoner.py        plain-language explanations (template or model)
  cli.py             runs the scenarios and writes evidence/
tests/
  test_parapet.py    12 tests covering fraud hold, caps, tiers, negotiation, audit tamper detection
evidence/
  audit_log.jsonl    execution evidence: every observation, decision, handshake and action
  summary.md         human-readable outcome per invoice
  outcomes.json      structured outcomes
  run_output.txt     console output of the run
  test_output.txt    console output of the test suite
docs/
  technical_documentation.md
  security_self_assessment.md
  demo_video_script.md
```

## Permission tiers

| Tier | Name | What the agent may do |
|---|---|---|
| 0 | Observe | Alert the owner only |
| 1 | Recommend | Propose an action with reasons |
| 2 | Prepare | Draft the action; owner approves with one tap |
| 3 | Execute | Act autonomously within per-transaction and daily caps and below the risk threshold |

Regardless of tier, a failed verification handshake always results in **Held**, and a risk score at or above the owner's threshold always results in **Escalated**. Tiers only ever lower the agent's authority, never raise it.

## Deployment notes

The sandbox ledger (`ledger.py`) is the only component that touches money. In a bank-hosted deployment it is replaced by the bank's core APIs (balance, transfer, payee registry, KYB) behind the same interface. The handshake secret becomes a key bound to the counterparty's verified business identity, ideally issued by the bank at onboarding, which turns the handshake into a bank-backed verified-payee check.

## License

MIT. Third-party components: none in the sandbox; `anthropic` SDK is optional (MIT).

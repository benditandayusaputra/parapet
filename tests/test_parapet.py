"""Run: python -m unittest discover -s tests -v"""
import unittest
from datetime import date

from parapet import handshake as hs
from parapet.agent import ParapetAgent
from parapet.audit import AuditLog
from parapet.counterparties import BuyerAgent, ImpostorSupplierAgent, LegitimateSupplierAgent
from parapet.ledger import seed
from parapet.models import BankAccount, Decision, Policy, Tier

TODAY = date(2026, 10, 20)


def make_agent(policy=None):
    ledger = seed(TODAY)
    return ParapetAgent(ledger, policy or Policy(), AuditLog(), TODAY), ledger


class PayableTests(unittest.TestCase):
    def test_clean_invoice_is_executed_within_caps(self):
        agent, L = make_agent()
        inv = L.invoices["INV-TINTA-0931"]
        out = agent.process_payable(inv, LegitimateSupplierAgent(L.counterparties["SUP-TINTA"]).attest_payee)
        self.assertEqual(out.decision, Decision.EXECUTED)
        self.assertTrue(inv.paid)
        self.assertEqual(L.balance, 85_000_000 - 4_250_000)

    def test_bec_invoice_is_held_and_no_money_moves(self):
        agent, L = make_agent()
        inv = L.invoices["INV-ANEKA-2210"]
        out = agent.process_payable(inv, ImpostorSupplierAgent().attest_payee)
        self.assertEqual(out.decision, Decision.HELD)
        self.assertFalse(inv.paid)
        self.assertEqual(L.balance, 85_000_000)
        self.assertGreaterEqual(out.risk_score, 0.45)
        codes = {s["code"] for e in agent.audit.entries if e["event"] == "payable.risk_scored"
                 for s in e["signals"] if e["invoice"] == inv.id}
        self.assertIn("ACCOUNT_CHANGED", codes)
        self.assertIn("URGENCY_LANGUAGE", codes)

    def test_impostor_signature_fails_verification(self):
        agent, L = make_agent()
        inv = L.invoices["INV-ANEKA-2210"]
        agent.process_payable(inv, ImpostorSupplierAgent().attest_payee)
        results = [e for e in agent.audit.entries if e["event"] == "handshake.result"]
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["attested_claim"])      # impostor claims yes
        self.assertFalse(results[0]["signature_valid"])    # but cannot prove it

    def test_legitimate_bank_change_is_prepared_not_held(self):
        agent, L = make_agent()
        inv = L.invoices["INV-KEMAS-0788"]
        legit = LegitimateSupplierAgent(L.counterparties["SUP-KEMAS"], current_account=BankAccount("BCA", "6655443322"))
        out = agent.process_payable(inv, legit.attest_payee)
        self.assertEqual(out.decision, Decision.PREPARED)
        self.assertFalse(inv.paid)

    def test_no_handshake_available_means_hold(self):
        agent, L = make_agent()
        inv = L.invoices["INV-KEMAS-0788"]
        out = agent.process_payable(inv, None)
        self.assertEqual(out.decision, Decision.HELD)

    def test_per_transaction_cap_downgrades_to_prepared(self):
        agent, L = make_agent(Policy(per_tx_cap=1_000_000))
        inv = L.invoices["INV-TINTA-0931"]
        out = agent.process_payable(inv, LegitimateSupplierAgent(L.counterparties["SUP-TINTA"]).attest_payee)
        self.assertEqual(out.decision, Decision.PREPARED)
        self.assertFalse(inv.paid)

    def test_daily_cap_is_enforced_across_invoices(self):
        agent, L = make_agent(Policy(daily_cap=5_000_000))
        L.spent_today = 2_000_000
        inv = L.invoices["INV-TINTA-0931"]  # 4.25M, would push to 6.25M
        out = agent.process_payable(inv, LegitimateSupplierAgent(L.counterparties["SUP-TINTA"]).attest_payee)
        self.assertEqual(out.decision, Decision.PREPARED)

    def test_observe_tier_never_executes(self):
        agent, L = make_agent(Policy(payable_tier=Tier.OBSERVE))
        inv = L.invoices["INV-TINTA-0931"]
        out = agent.process_payable(inv, LegitimateSupplierAgent(L.counterparties["SUP-TINTA"]).attest_payee)
        self.assertEqual(out.decision, Decision.HELD)
        self.assertEqual(L.balance, 85_000_000)


class ReceivableTests(unittest.TestCase):
    def test_negotiation_reaches_signed_agreement(self):
        agent, L = make_agent()
        inv = L.invoices["INV-OUT-5120"]
        buyer = BuyerAgent(L.counterparties["CUS-WARUNG"], max_delay_days=12, today=TODAY)
        out = agent.process_receivable(inv, buyer.respond)
        self.assertEqual(out.decision, Decision.EXECUTED)
        self.assertIsNotNone(out.agreed_terms)
        self.assertEqual(out.agreed_terms["pay_by"], "2026-11-01")
        self.assertTrue(hs.verify(L.counterparties["CUS-WARUNG"].agent_secret,
                                  {k: v for k, v in out.agreed_terms.items() if k != "buyer_signature"},
                                  out.agreed_terms["buyer_signature"]))

    def test_unreachable_buyer_with_high_risk_escalates_to_financing(self):
        agent, L = make_agent()
        inv = L.invoices["INV-OUT-5120"]
        out = agent.process_receivable(inv, None)
        self.assertEqual(out.decision, Decision.ESCALATED)
        self.assertTrue(any(e["event"] == "receivable.financing_recommended" for e in agent.audit.entries))

    def test_counter_beyond_ceiling_is_not_accepted(self):
        agent, L = make_agent()
        inv = L.invoices["INV-OUT-5133"]
        buyer = BuyerAgent(L.counterparties["CUS-BAKERY"], max_delay_days=40, today=TODAY)
        out = agent.process_receivable(inv, buyer.respond)
        self.assertIsNone(out.agreed_terms)
        self.assertIn(out.decision, (Decision.RECOMMENDED, Decision.ESCALATED))


class AuditTests(unittest.TestCase):
    def test_chain_is_valid_and_detects_tampering(self):
        agent, L = make_agent()
        for inv in L.invoices.values():
            if inv.direction.value == "payable":
                agent.process_payable(inv, None)
        self.assertTrue(agent.audit.verify_chain())
        agent.audit.entries[1]["amount"] = 1  # tamper
        self.assertFalse(agent.audit.verify_chain())


if __name__ == "__main__":
    unittest.main()

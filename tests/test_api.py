"""API tests. Run: python -m unittest discover -s tests -v  (needs fastapi + httpx, see requirements.txt)"""
import tempfile
import unittest
from datetime import date
from pathlib import Path

try:
    from fastapi.testclient import TestClient
    from parapet import api
except ImportError:  # fastapi not installed: keep the core suite runnable
    TestClient = None

TODAY = date(2026, 10, 20)


@unittest.skipUnless(TestClient, "fastapi/httpx not installed")
class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        api.boot(Path(self.tmp.name), TODAY)
        self.c = TestClient(api.app)

    def tearDown(self):
        self.tmp.cleanup()

    def test_queue_starts_pending(self):
        q = self.c.get("/queue").json()
        self.assertEqual(q["balance"], 85_000_000)
        self.assertEqual(len(q["invoices"]), 5)
        self.assertTrue(all(i["status"] == "pending" and i["risk_score"] is None for i in q["invoices"]))

    def test_run_all_matches_cli_outcomes(self):
        out = {o["invoice_id"]: o["decision"] for o in self.c.post("/run").json()}
        self.assertEqual(out, {"INV-TINTA-0931": "executed", "INV-ANEKA-2210": "held", "INV-KEMAS-0788": "prepared",
                               "INV-OUT-5120": "executed", "INV-OUT-5133": "executed"})
        q = self.c.get("/queue").json()
        self.assertEqual(q["balance"], 85_000_000 - 4_250_000)
        self.assertEqual(self.c.post("/run").json(), [])  # nothing left pending

    def test_detail_exposes_signals_and_handshake(self):
        self.c.post("/invoice/INV-ANEKA-2210/run")
        d = self.c.get("/invoice/INV-ANEKA-2210").json()
        self.assertEqual(d["outcome"]["decision"], "held")
        self.assertIn("ACCOUNT_CHANGED", {s["code"] for s in d["signals"]})
        res = [e for e in d["handshake"] if e["event"] == "handshake.result"]
        self.assertEqual(len(res), 1)
        self.assertFalse(res[0]["signature_valid"])
        self.assertEqual(self.c.post("/invoice/INV-ANEKA-2210/run").status_code, 409)
        self.assertEqual(self.c.get("/invoice/NOPE").status_code, 404)

    def test_approve_prepared_payable_moves_money(self):
        self.assertEqual(self.c.post("/invoice/INV-KEMAS-0788/run").json()["decision"], "prepared")
        self.assertEqual(self.c.post("/invoice/INV-ANEKA-2210/approve").status_code, 409)  # not prepared
        r = self.c.post("/invoice/INV-KEMAS-0788/approve").json()
        self.assertEqual(r["decision"], "executed")
        self.assertTrue(r["transfer_id"])
        self.assertEqual(self.c.get("/queue").json()["balance"], 85_000_000 - 7_100_000)
        self.assertEqual(self.c.post("/invoice/INV-KEMAS-0788/approve").status_code, 409)  # cannot pay twice

    def test_policy_update_changes_later_decisions(self):
        self.assertEqual(self.c.post("/policy", json={"payable_tier": 9}).status_code, 422)
        p = self.c.post("/policy", json={"payable_tier": 2}).json()
        self.assertEqual(p["payable_tier_name"], "PREPARE")
        self.assertEqual(self.c.get("/policy").json()["payable_tier"], 2)
        self.assertEqual(self.c.post("/invoice/INV-TINTA-0931/run").json()["decision"], "prepared")

    def test_audit_chain_valid_and_reset(self):
        self.c.post("/run")
        a = self.c.get("/audit").json()
        self.assertTrue(a["chain_valid"])
        self.assertTrue(any(e["event"] == "handshake.result" for e in a["entries"]))
        self.assertTrue((Path(self.tmp.name) / "audit_log.jsonl").stat().st_size > 0)
        self.c.post("/policy", json={"payable_tier": 2})
        q = self.c.post("/reset").json()
        self.assertTrue(all(i["status"] == "pending" for i in q["invoices"]))
        self.assertEqual(q["balance"], 85_000_000)
        self.assertEqual(self.c.get("/policy").json()["payable_tier"], 2)  # policy survives a reset

    def test_index_serves_app(self):
        r = self.c.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("<title>Parapet</title>", r.text)


if __name__ == "__main__":
    unittest.main()

# Parapet: Demo Video Script (target 4:30, max 5:00)

Format: screen recording of a terminal plus the evidence files, with voice-over. No slides needed except the title card. Record at 1080p, terminal font size 18 or larger. Keep the cursor still while talking.

Before recording: `rm -rf evidence` so the run is created live on camera. Open two terminal panes side by side: left for commands, right empty for `cat` output.

---

## 0:00 to 0:20. Title card

**On screen:** "Parapet. Collects what you are owed. Refuses to pay what you do not owe." Team name, Topic E.

**Voice:** "This is Parapet, an AI finance agent for small businesses. It does two things. It collects what the business is owed, and it refuses to pay what the business does not owe. Both use the same engine. Let me show you a real morning for a Jakarta packaging company."

## 0:20 to 0:50. The setup

**On screen:** `python -m parapet.cli --out evidence --today 2026-10-20` typed but not yet run. Then open `parapet/ledger.py` briefly at the seed function, scroll to the five invoices.

**Voice:** "The sandbox has five invoices waiting. Three supplier bills to pay, two customer invoices that are overdue. One of the supplier bills is a trap: the supplier's mailbox was hijacked, and the attacker sent an invoice with new bank details and a lot of urgency. The owner has set the agent to tier three, execute, with a twenty-five million rupiah cap per transaction."

## 0:50 to 1:30. Run it

**On screen:** Press enter. The five result lines appear.

**Voice:** "One command. Five invoices, five decisions, in under a second. The honest ink supplier invoice: executed, paid. The hijacked carton invoice: held, risk zero point nine, counterparty verification failed. A third supplier that genuinely moved banks: prepared, waiting for the owner's one tap. And both overdue customers: settlement agreed and signed by the buyer. Let me show you why each of those happened."

## 1:30 to 2:30. The fraud, line by line

**On screen:** `cat evidence/summary.md`, scroll to INV-ANEKA-2210. Highlight the four signals.

**Voice:** "Here is the trap. The agent found four signals before it even talked to anyone. The bank account on the invoice is not the registered one. The amount is two point one times what this supplier normally bills. The message uses four pressure phrases: urgent, today, do not call. And it announces new bank details. That already puts the risk at zero point nine."

**On screen:** `grep handshake evidence/audit_log.jsonl | python -m json.tool` (or open the log and find the three handshake entries).

**Voice:** "But the score is not what stopped the payment. This is. Because the account changed, the agent challenged the supplier's agent to sign the exact payment details: invoice number, amount, bank, account number, plus a random nonce. The attacker replied 'yes, confirmed, pay urgently.' You can see it in the log, attested claim true. But the signature does not verify. They control the mailbox. They never had the key. So the payment is held, no money moved, and the owner is told to phone the supplier on the number already on file. Not the number in the email."

## 2:30 to 3:00. The legitimate change

**On screen:** Scroll summary to INV-KEMAS-0788.

**Voice:** "This is the part that makes it usable instead of annoying. Kemas Lestari really did move to a new bank. Same signals fire, account changed. But their agent signed the challenge correctly. So instead of a hold, the agent prepares the payment and asks the owner for one tap. Verified, but still a human decision, because the risk signals are still there. A blocker that cries wolf gets switched off. Parapet is built to earn the tier it is given."

## 3:00 to 3:50. The other direction

**On screen:** Scroll summary to INV-OUT-5120. Then `grep negotiation evidence/audit_log.jsonl` to show the proposal, counter, agreed entries.

**Voice:** "Now money in. Warung Kopi Sejahtera is twenty-four days late and pays on time only sixty percent of the time. The agent opened with 'pay within three days.' Their agent countered with November first. That is inside the owner's fourteen-day ceiling, so the agent accepted and locked it. Look at the agreed entry: the buyer's signature over those exact terms. Same protocol as the fraud check, pointed the other way. If they had refused, the agent would have escalated this specific invoice for financing, because the risk score crossed the threshold."

## 3:50 to 4:15. The audit trail

**On screen:** `tail -n 1 evidence/audit_log.jsonl | python -m json.tool`, show `chain_valid: true`. Then `python -m unittest discover -s tests` output, 12 tests OK.

**Voice:** "Every observation, every handshake, every decision is in a hash-chained log. Change one field and the chain breaks; there is a test for that. Twelve tests cover the fraud hold, the caps, the tiers, the negotiation, and the tamper detection. And the language model never makes a decision. It only explains one that the policy engine already made."

## 4:15 to 4:30. Close

**On screen:** Title card again, with the one-line summary and the repository link.

**Voice:** "Parapet. One agent, both directions of cash, one verification protocol, and an audit trail a bank can read. Thank you."

---

## Recording checklist

- [ ] Fresh clone, delete `evidence/` before recording
- [ ] Terminal font 18+, dark theme, no transparency
- [ ] Pre-type each command so there is no typing on camera
- [ ] Voice-over recorded separately and laid over the screen capture
- [ ] Export 1080p MP4, under 5:00, file name `Parapet_Demo.mp4`

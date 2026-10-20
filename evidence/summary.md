# Parapet sandbox run, 2026-10-20

Opening balance: IDR 85,000,000. Closing balance: IDR 80,750,000.

## INV-TINTA-0931 (payable)
- Decision: **executed**
- Risk score: 0.00
- Reason: Within tier, caps and risk threshold.
- Transfer: TX-0001
- Message to owner: Done: Ink cartridges, October (IDR 4,250,000). Within tier, caps and risk threshold. Transfer TX-0001 to Mandiri ****8765.

## INV-ANEKA-2210 (payable)
- Decision: **held**
- Risk score: 0.90
- Reason: Counterparty verification failed.
- Message to owner: Payment held: Carton stock, October (IDR 24,600,000). Counterparty verification failed. Why: ACCOUNT_CHANGED (+0.45): Invoice asks for CIMB ****9988, registered is BCA ****1234.; AMOUNT_ANOMALY (+0.15): Amount is 2.1x the historical average for this payee.; URGENCY_LANGUAGE (+0.20): Pressure phrases: 4.; ACCOUNT_CHANGE_LANGUAGE (+0.10): Message announces new banking details. No money moved. I have frozen this payee until you confirm by phone using the number on file.

## INV-KEMAS-0788 (payable)
- Decision: **prepared**
- Risk score: 0.55
- Reason: Payee verified by handshake, but risk signals remain; owner approval required.
- Message to owner: Ready for your approval: Plastic film, October (IDR 7,100,000). Payee verified by handshake, but risk signals remain; owner approval required. Why: ACCOUNT_CHANGED (+0.45): Invoice asks for BCA ****3322, registered is Permata ****9876.; ACCOUNT_CHANGE_LANGUAGE (+0.10): Message announces new banking details.

## INV-OUT-5120 (receivable)
- Decision: **executed**
- Risk score: 0.45
- Reason: Settlement agreed and signed by buyer: pay by 2026-11-01.
- Agreed terms: pay by 2026-11-01, buyer signature 8ac53a9823c0f680...
- Message to owner: Done: Cup sleeves and boxes, September (IDR 9,800,000). Settlement agreed and signed by buyer: pay by 2026-11-01. Why: OVERDUE (+0.20): 24 days past due.; POOR_HISTORY (+0.25): Paid on time 60% of the time.

## INV-OUT-5133 (receivable)
- Decision: **executed**
- Risk score: 0.05
- Reason: Settlement agreed and signed by buyer: pay by 2026-10-23.
- Agreed terms: pay by 2026-10-23, buyer signature 993efcc0e7310bfa...
- Message to owner: Done: Bread bags, September (IDR 6,400,000). Settlement agreed and signed by buyer: pay by 2026-10-23. Why: OVERDUE (+0.05): 5 days past due.

Audit chain valid: True. Entries: 31.
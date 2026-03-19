# Chase Bank

Access your Chase accounts, balances, and transaction history.

## Accounts

```
account.list
→ [
    { accountId: 123456789, name: "TOTAL CHECKING", type: "checking", last4: "1234",
      balance: 1000.00, available: 1000.00 },
    { accountId: 987654321, name: "Sapphire Preferred", type: "credit", last4: "5678",
      balance: 250.00, available: 4750.00, cardType: "CHASE_SAPPHIRE_PREFERRED" }
  ]
```

## Transactions

```
transaction.list { account_id: "123456789", limit: 10 }
→ [
    { date: "20260304", description: "EXAMPLE MERCHANT", amount: -42.00,
      balance: 958.00, category: "Shopping", pending: false },
    ...
  ]
```

## Notes
- Transactions only work for DDA accounts (checking/savings). Credit card transactions TBD.
- Session expires after ~8 hours. Re-login in the browser/provider you want to use when you get 401 errors.
- The `amount` field is signed: negative = money out, positive = money in.

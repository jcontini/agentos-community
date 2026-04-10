---
id: chase
name: Chase Bank
description: "Chase Bank accounts, balances, and transactions — checking, savings, and credit cards"
color: "#117ACA"
website: "https://www.chase.com"

connections:
  web:
    auth:
      type: cookies
      domain: .chase.com
      names:
      - AMSESSION
      - sessioncacheid
      - auth-guid
      - dps-pod-id
      - x-auth-activity-info
      - akaalb_secure_chase_com
      - auth-site-info
      account:
        check: check_session
      login:
        account_prompt: What is your Chase username?
        phases:
        - name: navigate_to_login
          steps:
          - action: goto
            url: https://secure.chase.com/web/auth/dashboard#/dashboard/overview
          returns_to_agent: 'The Chase login page is open in the browser.

            Ask the user to log in (username, password, MFA). Tell them to let you know when they can see their accounts dashboard.

            '
        - name: complete_login
          steps:
          - action: wait
            url_contains: /dashboard
          returns_to_agent: 'Login confirmed. Cookie provider matchmaking can extract `.chase.com`

            cookies on the next API call. If multiple cookie providers are

            installed, ask the user which browser/provider to use.

            '

test:
  check_session:
    skip: true
---

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

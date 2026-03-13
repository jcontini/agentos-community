---
id: chase
name: Chase Bank
description: Chase Bank accounts, balances, and transactions — checking, savings, and credit cards
icon: icon.png
color: "#117ACA"
platforms: [macos]

website: https://www.chase.com

auth:
  cookies:
    domain: ".chase.com"
    names: ["AMSESSION", "sessioncacheid", "auth-guid", "dps-pod-id", "x-auth-activity-info", "akaalb_secure_chase_com", "auth-site-info"]
    session_duration: "8h"
    login:
      account_prompt: "What is your Chase username?"
      phases:
        - name: navigate_to_login
          steps:
            - { action: goto, url: "https://secure.chase.com/web/auth/dashboard#/dashboard/overview" }
          returns_to_agent: |
            The Chase login page is open in the browser.
            Ask the user to log in (username, password, MFA). Tell them to let you know when they can see their accounts dashboard.

        - name: complete_login
          steps:
            - { action: wait, url_contains: "/dashboard" }
          returns_to_agent: |
            Login confirmed. Extract cookies via playwright cookies utility for domain .chase.com.

instructions: |
  Chase Bank — personal checking, savings, and credit card accounts.

  ## Auth
  Requires a full cookie jar from an active Chase browser session.
  The key session cookies are AMSESSION + sessioncacheid + auth-guid.
  Sessions expire in ~10 minutes so cookies are short-lived.

  ## Recommended login flow (fully automatable)
    1. Playwright navigates to Chase login, fills username + password (from agentOS secrets)
    2. Chase sends OTP via SMS
    3. Read the OTP from iMessage skill (same pattern as Claude skill reading email invite links)
    4. Playwright submits OTP, lands on dashboard
    5. Extract full cookie jar via playwright cookies utility
    6. Use cookies for fast direct API calls
    7. On 401 → repeat from step 1 automatically

  This makes Chase fully hands-free. The iMessage skill already handles step 3.
  TODO: build the Playwright login utility for this skill (see chaseinvest-api session.py for reference).

  ## Endpoints (confirmed 2026-03-12)
  - Accounts+balances: POST /svc/rl/accounts/l4/v1/app/data/list (empty body)
  - Transactions: GET /svc/rr/accounts/secure/gateway/deposit-account/transactions/
      inquiry-maintenance/etu-dda-transactions/v3/transactions?digital-account-identifier=<id>&...
  - Extra header needed for transactions: network-channel-group-code: DIGITAL

  ## Account types
  - DDA = checking or savings (accountTileDetailType: CHK or SAV)
  - CARD = credit card (cardType: FREEDOM_UNLIMITED, CHASE_SAPPHIRE_PREFERRED, etc.)

transformers:
  account:
    terminology: Account
    mapping:
      id: .accountId
      name: .name
      description: '(.type + " •••• " + .last4)'
      data.account_type: .type
      data.last4: .last4
      data.balance: .balance
      data.available: .available
      data.card_type: .cardType

# ==============================================================================
# OPERATIONS
# ==============================================================================

operations:
  account.list:
    description: >
      List all Chase accounts with current balances.
      Returns checking, savings, and credit card accounts.
      Balance = current balance. Available = available to spend/credit available.
    returns: account[]
    command:
      binary: python3
      args: ["skills/chase/chase-api.py", "accounts", "--cookies", ".auth.cookies"]
      timeout: 20

  transaction.list:
    description: >
      List recent transactions for a Chase checking or savings account (DDA accounts only).
      Returns transactions with date, description, signed amount (negative=debit), running balance, and category.
      Credit card transactions require a different endpoint (not yet implemented).
    params:
      account_id:
        type: string
        required: true
        description: "The accountId from account.list (e.g. 123456789)"
      limit:
        type: integer
        description: "Number of transactions to return (default: 30, max: 100)"
    returns: transaction[]
    command:
      binary: python3
      args: ["skills/chase/chase-api.py", "transactions", "--cookies", ".auth.cookies", "--account-id", ".params.account_id", "--limit", ".params.limit // 30"]
      timeout: 20

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
- Session expires after ~8 hours. Re-login via Playwright when you get 401 errors.
- The `amount` field is signed: negative = money out, positive = money in.

---
id: copilot-money
name: Copilot Money
description: Read accounts, transactions, and balance history from Copilot Money, a personal finance app for macOS/iOS
color: "#6366F1"

website: https://copilot.money
privacy_url: https://copilot.money/privacy

auth: none
platforms: [macos]
connects_to: copilot-money

seed:
  - id: copilot-money-app
    types: [software]
    name: Copilot Money
    data:
      software_type: app
      url: https://copilot.money
      platforms: [macos, ios]
      pricing: paid
      notes: Personal finance app. Syncs via Plaid. Stores accounts and transactions locally in SQLite and widget JSON files.

instructions: |
  Copilot Money stores financial data locally in two places:
  - Accounts: widget JSON files per account (name, balance, mask, institution)
  - Transactions: CopilotDB.sqlite (Transactions table, ~5k rows)
  - Balance history: CopilotDB.sqlite (accountDailyBalance table)

  Institution IDs map to: ins_56=Chase, ins_10=AmericanExpress, ins_11=Schwab, ins_116794=Mercury, coinbase=Coinbase

  Common workflows:
  - "Show me my accounts" → account.list
  - "What's my net worth?" → account.list, sum all balances
  - "Show me recent transactions" → transaction.list
  - "Find transactions at a merchant" → transaction.search with query

database: "~/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"

# ==============================================================================
# TRANSFORMERS
# ==============================================================================

transformers:
  account:
    terminology: Financial Account
    mapping:
      id: .id
      name: .name
      handle: .mask
      platform: '"copilot-money"'
      description: '.name + if .mask then " (••••" + .mask + ")" else "" end'
      data.balance: .balance
      data.limit: .limit
      data.institution_id: .institution_id
      data.color: .color

      # Auto-create tag entities and link via tagged_with
      # Python script emits tags like ["financial", "credit", "taxable"]
      tags:
        tag[]:
          _source: '.tags'
          name: .

  transaction:
    terminology: Transaction
    mapping:
      id: '.id | tostring'
      name: '.merchant_name // "Unknown"'
      description: '(.merchant_name // "Unknown") + " — $" + ((.amount // 0) | tostring)'
      data.amount: .amount
      data.date: .date
      data.account_id: .account_id
      data.category_id: .category_id
      data.pending: '.pending == 1 or .pending == true'
      data.recurring: '.recurring == 1 or .recurring == true'
      data.notes: .notes
      data.type: .type

      # Transaction type as tags: recurring, internal-transfer
      type_tags:
        tag[]:
          _source: '([if (.type == "recurring" or .recurring == 1 or .recurring == true) then "recurring" else empty end] + [if .type == "internal_transfer" then "internal-transfer" else empty end])'
          name: .

# ==============================================================================
# OPERATIONS
# ==============================================================================

operations:
  account.list:
    description: List all financial accounts with balances and institution info
    returns: account[]
    command:
      binary: python3
      args:
        - "~/dev/agentos-community/skills/copilot-money/copilot-accounts.py"

  transaction.list:
    description: List recent transactions, optionally filtered by account
    returns: transaction[]
    params:
      account_id: { type: string, description: "Filter by account ID" }
      limit: { type: integer }
    sql:
      query: |
        SELECT
          t.id,
          t.name as merchant_name,
          t.amount,
          date(t.date, 'localtime') as date,
          t.account_id,
          t.category_id,
          t.type,
          t.recurring,
          t.pending,
          t.user_note as notes
        FROM Transactions t
        WHERE (:account_id IS NULL OR t.account_id = :account_id)
          AND t.user_deleted = 0
        ORDER BY t.date DESC
        LIMIT :limit
      params:
        account_id: .params.account_id
        limit: '.params.limit // 100'

  transaction.search:
    description: Search transactions by merchant name, category, or notes
    returns: transaction[]
    params:
      query: { type: string, required: true }
      limit: { type: integer }
    sql:
      query: |
        SELECT
          t.id,
          t.name as merchant_name,
          t.amount,
          date(t.date, 'localtime') as date,
          t.account_id,
          t.category_id,
          t.type,
          t.recurring,
          t.pending,
          t.user_note as notes
        FROM Transactions t
        WHERE t.user_deleted = 0
          AND (
            t.name LIKE '%' || :query || '%'
            OR t.original_name LIKE '%' || :query || '%'
            OR t.user_note LIKE '%' || :query || '%'
          )
        ORDER BY t.date DESC
        LIMIT :limit
      params:
        query: .params.query
        limit: '.params.limit // 100'

---

# Copilot Money

Read accounts, transactions, and balance history from [Copilot Money](https://copilot.money/).

## Requirements

- **macOS only** — reads from Copilot's local SQLite database and widget JSON files
- **Copilot installed and synced** — the app must be installed, logged in, and have synced at least once
- **Full Disk Access** — System Settings > Privacy & Security > Full Disk Access (for the agentOS server process)

## Data Sources

| Data | Source |
|------|--------|
| Accounts | `~/Library/Group Containers/group.com.copilot.production/widget-data/widgets-account-account_*.json` |
| Transactions | `CopilotDB.sqlite` → `Transactions` table |
| Balance history | `CopilotDB.sqlite` → `accountDailyBalance` table |

## Capabilities

```
OPERATION              ENTITY TYPE    DESCRIPTION
---------------------  -------------  ----------------------------------------
account.list           account        All accounts with balances and institution
transaction.list       transaction    Recent transactions with optional filters
transaction.search     transaction    Search by merchant, category, or notes
```

## Notes

- This skill is **read-only**
- Data reflects what Copilot has synced from Plaid — real-time balances may lag slightly
- Accounts are tagged `financial` on the graph and linked to institution organizations

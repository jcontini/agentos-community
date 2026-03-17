---
id: copilot-money
name: Copilot Money
description: Read accounts, transactions, and balance history from Copilot Money, a personal finance app for macOS/iOS
icon: icon.svg
color: "#6366F1"

website: https://copilot.money
privacy_url: https://copilot.money/privacy

auth: none
database: "~/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"

# ==============================================================================
# TRANSFORMERS
# ==============================================================================

adapters:
  account:
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

    # Tags: recurring, internal-transfer, and Copilot spending category (with emoji + color)
    # Python script emits tags as [{name, emoji?, color?}]
    tags:
      tag[]:
        _source: '.tags'
        name: .name
        emoji: .emoji
        color: .color

# ==============================================================================
# OPERATIONS
# ==============================================================================

operations:
  list_accounts:
    description: List all financial accounts with balances and institution info
    returns: account[]
    python:
      module: ./copilot-accounts.py
      function: load_accounts

  list_transactions:
    description: List recent transactions, optionally filtered by account, with category tags (emoji + color)
    returns: transaction[]
    params:
      account_id: { type: string, description: "Filter by account ID" }
      limit: { type: integer }
    python:
      module: ./copilot-transactions.py
      function: fetch_transactions
      args:
        account_id: .params.account_id
        limit: '.params.limit // 100'

  search_transactions:
    description: Search transactions by merchant name or notes, with category tags (emoji + color)
    returns: transaction[]
    params:
      query: { type: string, required: true }
      limit: { type: integer }
    python:
      module: ./copilot-transactions.py
      function: fetch_transactions
      args:
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

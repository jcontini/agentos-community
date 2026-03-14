---
id: copilot-money
name: Copilot Money
description: Read accounts, transactions, and balance history from Copilot Money, a personal finance app for macOS/iOS
color: "#6366F1"

website: https://copilot.money
privacy_url: https://copilot.money/privacy

auth: none
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
  account.list:
    description: List all financial accounts with balances and institution info
    returns: account[]
    command:
      binary: python3
      args:
        - "~/dev/agentos-community/skills/copilot-money/copilot-accounts.py"

  transaction.list:
    description: List recent transactions, optionally filtered by account, with category tags (emoji + color)
    returns: transaction[]
    params:
      account_id: { type: string, description: "Filter by account ID" }
      limit: { type: integer }
    command:
      binary: python3
      args:
        - "~/dev/agentos-community/skills/copilot-money/copilot-transactions.py"
        - '{account_id: .params.account_id, limit: (.params.limit // 100), query: null} | tojson'

  transaction.search:
    description: Search transactions by merchant name or notes, with category tags (emoji + color)
    returns: transaction[]
    params:
      query: { type: string, required: true }
      limit: { type: integer }
    command:
      binary: python3
      args:
        - "~/dev/agentos-community/skills/copilot-money/copilot-transactions.py"
        - '{account_id: null, limit: (.params.limit // 100), query: .params.query} | tojson'

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

---
id: copilot
name: Copilot Money
description: Manage finances in Copilot Money - transactions, categories, and organization
icon: icon.png
color: "#00C853"

website: https://copilot.money
privacy_url: https://copilot.money/privacy
terms_url: https://copilot.money/terms

platform: macos

database: "~/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"

instructions: |
  Copilot Money stores data locally in SQLite. The database is at:
  ~/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite
  
  Transaction types:
  - regular: Normal spending/income
  - internal_transfer: Money moved between accounts
  - income: Deposits and income
  
  Amount conventions:
  - Negative = expense/spending
  - Positive = income/refund
---

# Copilot Money

Connect to [Copilot Money](https://copilot.money) to manage your finances through AI.

## Requirements

- macOS only
- Copilot Money app installed and synced

## Features

- View and search transactions
- Analyze spending by month, merchant, or category
- Categorize and review transactions
- Check account balances

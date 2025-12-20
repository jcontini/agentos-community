---
id: copilot
name: Copilot Money
description: Manage finances in Copilot Money - transactions, categories, and organization
icon: https://cdn.jim-nielsen.com/ios/512/copilot-track-budget-money-2025-10-31.png
color: "#00C853"

website: https://copilot.money
privacy_url: https://copilot.money/privacy
terms_url: https://copilot.money/terms

tags: [finances, transactions, budget]
platform: macos

requires:
  - sqlite3  # Pre-installed on macOS
  - jq       # For JSON parsing

actions:
  # ============================================
  # READ OPERATIONS
  # ============================================
  
  get_transactions:
    readonly: true
    description: List recent transactions
    params:
      limit:
        type: number
        default: 30
        description: Number of transactions to return
      days:
        type: number
        description: Only transactions from last N days
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      require_file "$DB"
      
      DAYS_FILTER=""
      if [ -n "$PARAM_DAYS" ]; then
        DAYS_FILTER="AND date >= date('now', '-$PARAM_DAYS days')"
      fi
      
      sqlite3 "$DB" -json "
        SELECT 
          id,
          name as merchant,
          amount,
          date(date) as date,
          category_id,
          pending,
          recurring,
          user_reviewed as reviewed,
          user_note as note
        FROM Transactions 
        WHERE user_deleted = 0 OR user_deleted IS NULL
        $DAYS_FILTER
        ORDER BY date DESC 
        LIMIT ${PARAM_LIMIT:-30};
      "

  get_transaction:
    readonly: true
    description: Get full details of a specific transaction
    params:
      id:
        type: string
        required: true
        description: Transaction ID
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      CATEGORIES="$HOME/Library/Group Containers/group.com.copilot.production/widget-data/widgets-category-categories.json"
      require_file "$DB"
      
      CATS=$(cat "$CATEGORIES" 2>/dev/null || echo '[]')
      
      sqlite3 "$DB" -json "
        SELECT 
          id,
          name as merchant,
          original_name,
          name_override,
          amount,
          date(date) as date,
          category_id,
          plaid_category_strings,
          type,
          pending,
          recurring,
          recurring_id,
          user_reviewed as reviewed,
          user_note as note,
          user_deleted as hidden
        FROM Transactions 
        WHERE id = '$PARAM_ID';
      " | jq --argjson cats "$CATS" '
        ($cats | map({(.id): .name}) | add // {}) as $catMap |
        .[0] | . + {category_name: ($catMap[.category_id] // "Unknown")}
      '

  search:
    readonly: true
    description: Search transactions by merchant name
    params:
      query:
        type: string
        required: true
        description: Merchant name to search for
      limit:
        type: number
        default: 30
        description: Max results to return
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      require_file "$DB"
      
      sqlite3 "$DB" -json "
        SELECT 
          id,
          name as merchant,
          amount,
          date(date) as date,
          category_id,
          user_reviewed as reviewed
        FROM Transactions 
        WHERE name LIKE '%$PARAM_QUERY%'
          AND (user_deleted = 0 OR user_deleted IS NULL)
        ORDER BY date DESC 
        LIMIT ${PARAM_LIMIT:-30};
      "

  unreviewed:
    readonly: true
    description: List transactions needing review (not yet categorized by user)
    params:
      limit:
        type: number
        default: 50
        description: Max transactions to return
      days:
        type: number
        default: 30
        description: Only transactions from last N days
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      CATEGORIES="$HOME/Library/Group Containers/group.com.copilot.production/widget-data/widgets-category-categories.json"
      require_file "$DB"
      
      CATS=$(cat "$CATEGORIES" 2>/dev/null || echo '[]')
      
      sqlite3 "$DB" -json "
        SELECT 
          id,
          name as merchant,
          amount,
          date(date) as date,
          category_id,
          plaid_category_strings
        FROM Transactions 
        WHERE (user_reviewed = 0 OR user_reviewed IS NULL)
          AND (user_deleted = 0 OR user_deleted IS NULL)
          AND date >= date('now', '-${PARAM_DAYS:-30} days')
          AND type = 'regular'
        ORDER BY date DESC 
        LIMIT ${PARAM_LIMIT:-50};
      " | jq --argjson cats "$CATS" '
        ($cats | map({(.id): .name}) | add // {}) as $catMap |
        [.[] | . + {category_name: ($catMap[.category_id] // "Uncategorized")}]
      '

  get_categories:
    readonly: true
    description: List all available categories with IDs (for recategorization)
    run: |
      CATEGORIES="$HOME/Library/Group Containers/group.com.copilot.production/widget-data/widgets-category-categories.json"
      require_file "$CATEGORIES"
      
      cat "$CATEGORIES" | jq '[.[] | {id: .id, name: .name, excluded: .excluded}]'

  spending_by_month:
    readonly: true
    description: Get monthly spending totals (excludes payments/transfers)
    params:
      months:
        type: number
        default: 3
        description: Number of months to include
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      require_file "$DB"
      
      sqlite3 "$DB" -json "
        SELECT 
          strftime('%Y-%m', date) as month,
          COUNT(*) as transaction_count,
          ROUND(ABS(SUM(amount)), 2) as total_spending
        FROM Transactions 
        WHERE amount < 0 
          AND date >= date('now', '-${PARAM_MONTHS:-3} months')
          AND type = 'regular'
          AND (user_deleted = 0 OR user_deleted IS NULL)
        GROUP BY month 
        ORDER BY month DESC;
      "

  spending_by_merchant:
    readonly: true
    description: Get spending grouped by merchant (excludes payments/transfers)
    params:
      months:
        type: number
        default: 3
        description: Number of months to include
      limit:
        type: number
        default: 25
        description: Max merchants to return (sorted by spend)
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      require_file "$DB"
      
      sqlite3 "$DB" -json "
        SELECT 
          name as merchant,
          ROUND(ABS(SUM(amount)), 2) as total_spending,
          COUNT(*) as transaction_count,
          date(MIN(date)) as first_seen,
          date(MAX(date)) as last_seen
        FROM Transactions 
        WHERE amount < 0 
          AND date >= date('now', '-${PARAM_MONTHS:-3} months')
          AND type = 'regular'
          AND (user_deleted = 0 OR user_deleted IS NULL)
        GROUP BY name 
        ORDER BY total_spending DESC
        LIMIT ${PARAM_LIMIT:-25};
      "

  spending_by_category:
    readonly: true
    description: Get spending grouped by category
    params:
      months:
        type: number
        default: 3
        description: Number of months to include
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      CATEGORIES="$HOME/Library/Group Containers/group.com.copilot.production/widget-data/widgets-category-categories.json"
      require_file "$DB"
      
      CATS=$(cat "$CATEGORIES" 2>/dev/null || echo '[]')
      
      sqlite3 "$DB" -json "
        SELECT 
          category_id,
          ROUND(ABS(SUM(amount)), 2) as total_spending,
          COUNT(*) as transaction_count
        FROM Transactions 
        WHERE amount < 0 
          AND date >= date('now', '-${PARAM_MONTHS:-3} months')
          AND type = 'regular'
          AND (user_deleted = 0 OR user_deleted IS NULL)
        GROUP BY category_id 
        ORDER BY total_spending DESC;
      " | jq --argjson cats "$CATS" '
        ($cats | map({(.id): .name}) | add // {}) as $catMap |
        [.[] | . + {category_name: ($catMap[.category_id] // "Uncategorized")}]
      '

  balances:
    readonly: true
    description: Get latest account balances
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      ACCOUNTS_DIR="$HOME/Library/Group Containers/group.com.copilot.production/widget-data"
      require_file "$DB"
      require_dir "$ACCOUNTS_DIR"
      
      CREDIT=$(cat "$ACCOUNTS_DIR/widgets-account-credit_accounts.json")
      OTHER=$(cat "$ACCOUNTS_DIR/widgets-account-other_accounts.json")
      ALL_ACCOUNTS=$(echo "$CREDIT $OTHER" | jq -s 'add')
      
      sqlite3 "$DB" -json "
        SELECT 
          account_id, 
          date, 
          current_balance, 
          available_balance,
          \"limit\" as credit_limit
        FROM accountDailyBalance 
        WHERE date = (
          SELECT MAX(date) 
          FROM accountDailyBalance adb2 
          WHERE adb2.account_id = accountDailyBalance.account_id
        );
      " | jq --argjson accounts "$ALL_ACCOUNTS" '
        ($accounts | map({(.id): .name}) | add) as $nameMap |
        [.[] | . + {account_name: ($nameMap[.account_id] // "Unknown")}]
        | sort_by(.account_name)
      '

  net_worth:
    readonly: true
    description: Calculate net worth with account breakdown
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      ACCOUNTS_DIR="$HOME/Library/Group Containers/group.com.copilot.production/widget-data"
      require_file "$DB"
      require_dir "$ACCOUNTS_DIR"
      
      CREDIT=$(cat "$ACCOUNTS_DIR/widgets-account-credit_accounts.json")
      OTHER=$(cat "$ACCOUNTS_DIR/widgets-account-other_accounts.json")
      ALL_ACCOUNTS=$(echo "$CREDIT $OTHER" | jq -s 'add')
      
      sqlite3 "$DB" -json "
        SELECT 
          account_id, 
          date, 
          current_balance, 
          available_balance, 
          \"limit\" as credit_limit
        FROM accountDailyBalance 
        WHERE date = (
          SELECT MAX(date) 
          FROM accountDailyBalance adb2 
          WHERE adb2.account_id = accountDailyBalance.account_id
        );
      " | jq --argjson creditAccounts "$CREDIT" --argjson allAccounts "$ALL_ACCOUNTS" '
        ($allAccounts | map({(.id): .name}) | add) as $nameMap |
        ($creditAccounts | map(.id)) as $creditIds |
        [.[] | .account_id as $aid | . + {
          account_name: ($nameMap[$aid] // "Unknown"),
          account_type: (if ($creditIds | index($aid)) != null then "credit" else "asset" end)
        }]
        | map({
            account_name: .account_name,
            current_balance: (.current_balance // 0),
            account_type: .account_type
          })
        | sort_by(.account_name)
        | . as $accounts |
        {
          accounts: $accounts,
          summary: {
            assets: ($accounts | map(select(.account_type == "asset") | .current_balance) | add // 0),
            liabilities: ($accounts | map(select(.account_type == "credit") | .current_balance) | add // 0),
            net_worth: (($accounts | map(select(.account_type == "asset") | .current_balance) | add // 0) - ($accounts | map(select(.account_type == "credit") | .current_balance) | add // 0))
          }
        }
      '

  recurring:
    readonly: true
    description: List recurring transactions
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      require_file "$DB"
      
      sqlite3 "$DB" -json "
        SELECT 
          name as merchant,
          ROUND(ABS(AVG(amount)), 2) as avg_amount,
          COUNT(*) as occurrence_count,
          date(MIN(date)) as first_seen,
          date(MAX(date)) as last_seen
        FROM Transactions 
        WHERE recurring = 1
          AND amount < 0
          AND (user_deleted = 0 OR user_deleted IS NULL)
        GROUP BY name, recurring_id
        ORDER BY avg_amount DESC;
      "

  hidden:
    readonly: true
    description: List hidden/deleted transactions
    params:
      limit:
        type: number
        default: 50
        description: Max transactions to return
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      require_file "$DB"
      
      sqlite3 "$DB" -json "
        SELECT 
          id,
          name as merchant,
          amount,
          date(date) as date,
          category_id
        FROM Transactions 
        WHERE user_deleted = 1
        ORDER BY date DESC 
        LIMIT ${PARAM_LIMIT:-50};
      "

  # ============================================
  # WRITE OPERATIONS
  # ============================================

  recategorize:
    description: Change category on a single transaction
    params:
      id:
        type: string
        required: true
        description: Transaction ID
      category_id:
        type: string
        required: true
        description: New category ID (use get_categories to get IDs)
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      require_file "$DB"
      
      sqlite3 "$DB" "
        UPDATE Transactions 
        SET category_id = '$PARAM_CATEGORY_ID', 
            user_reviewed = 1 
        WHERE id = '$PARAM_ID';
      "
      
      # Return updated transaction
      sqlite3 "$DB" -json "
        SELECT id, name as merchant, category_id, user_reviewed as reviewed 
        FROM Transactions WHERE id = '$PARAM_ID';
      "

  recategorize_merchant:
    description: Recategorize ALL transactions from a merchant (bulk operation)
    params:
      merchant:
        type: string
        required: true
        description: Merchant name (exact match)
      category_id:
        type: string
        required: true
        description: New category ID
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      require_file "$DB"
      
      # Count before
      COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM Transactions WHERE name = '$PARAM_MERCHANT';")
      
      sqlite3 "$DB" "
        UPDATE Transactions 
        SET category_id = '$PARAM_CATEGORY_ID', 
            user_reviewed = 1 
        WHERE name = '$PARAM_MERCHANT';
      "
      
      echo "{\"updated\": $COUNT, \"merchant\": \"$PARAM_MERCHANT\", \"category_id\": \"$PARAM_CATEGORY_ID\"}"

  add_note:
    description: Add or update note on a transaction
    params:
      id:
        type: string
        required: true
        description: Transaction ID
      note:
        type: string
        required: true
        description: Note text
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      require_file "$DB"
      
      # Escape single quotes in note
      ESCAPED_NOTE=$(echo "$PARAM_NOTE" | sed "s/'/''/g")
      
      sqlite3 "$DB" "
        UPDATE Transactions 
        SET user_note = '$ESCAPED_NOTE'
        WHERE id = '$PARAM_ID';
      "
      
      sqlite3 "$DB" -json "
        SELECT id, name as merchant, user_note as note 
        FROM Transactions WHERE id = '$PARAM_ID';
      "

  rename:
    description: Set custom merchant name override
    params:
      id:
        type: string
        required: true
        description: Transaction ID
      name:
        type: string
        required: true
        description: Custom merchant name
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      require_file "$DB"
      
      ESCAPED_NAME=$(echo "$PARAM_NAME" | sed "s/'/''/g")
      
      sqlite3 "$DB" "
        UPDATE Transactions 
        SET name_override = '$ESCAPED_NAME'
        WHERE id = '$PARAM_ID';
      "
      
      sqlite3 "$DB" -json "
        SELECT id, name as merchant, name_override, original_name 
        FROM Transactions WHERE id = '$PARAM_ID';
      "

  change_type:
    description: Change transaction type (regular, internal_transfer, income)
    params:
      id:
        type: string
        required: true
        description: Transaction ID
      type:
        type: string
        required: true
        description: "New type: regular, internal_transfer, or income"
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      require_file "$DB"
      
      # Validate type
      if [ "$PARAM_TYPE" != "regular" ] && [ "$PARAM_TYPE" != "internal_transfer" ] && [ "$PARAM_TYPE" != "income" ]; then
        echo '{"error": "Invalid type. Must be: regular, internal_transfer, or income"}'
        exit 1
      fi
      
      sqlite3 "$DB" "
        UPDATE Transactions 
        SET type = '$PARAM_TYPE', 
            user_changed_type = 1 
        WHERE id = '$PARAM_ID';
      "
      
      sqlite3 "$DB" -json "
        SELECT id, name as merchant, type, user_changed_type 
        FROM Transactions WHERE id = '$PARAM_ID';
      "

  hide:
    description: Hide/delete a transaction (soft delete - excludes from reports)
    params:
      id:
        type: string
        required: true
        description: Transaction ID
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      require_file "$DB"
      
      sqlite3 "$DB" "
        UPDATE Transactions 
        SET user_deleted = 1 
        WHERE id = '$PARAM_ID';
      "
      
      sqlite3 "$DB" -json "
        SELECT id, name as merchant, user_deleted as hidden 
        FROM Transactions WHERE id = '$PARAM_ID';
      "

  unhide:
    description: Restore a hidden transaction
    params:
      id:
        type: string
        required: true
        description: Transaction ID
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      require_file "$DB"
      
      sqlite3 "$DB" "
        UPDATE Transactions 
        SET user_deleted = 0 
        WHERE id = '$PARAM_ID';
      "
      
      sqlite3 "$DB" -json "
        SELECT id, name as merchant, user_deleted as hidden 
        FROM Transactions WHERE id = '$PARAM_ID';
      "

  mark_reviewed:
    description: Mark transaction as reviewed (without changing category)
    params:
      id:
        type: string
        required: true
        description: Transaction ID
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      require_file "$DB"
      
      sqlite3 "$DB" "
        UPDATE Transactions 
        SET user_reviewed = 1 
        WHERE id = '$PARAM_ID';
      "
      
      sqlite3 "$DB" -json "
        SELECT id, name as merchant, user_reviewed as reviewed 
        FROM Transactions WHERE id = '$PARAM_ID';
      "

  mark_all_reviewed:
    description: Mark all unreviewed transactions as reviewed (bulk operation)
    params:
      days:
        type: number
        default: 30
        description: Only transactions from last N days
    run: |
      DB="$HOME/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite"
      require_file "$DB"
      
      COUNT=$(sqlite3 "$DB" "
        SELECT COUNT(*) FROM Transactions 
        WHERE (user_reviewed = 0 OR user_reviewed IS NULL)
          AND date >= date('now', '-${PARAM_DAYS:-30} days');
      ")
      
      sqlite3 "$DB" "
        UPDATE Transactions 
        SET user_reviewed = 1 
        WHERE (user_reviewed = 0 OR user_reviewed IS NULL)
          AND date >= date('now', '-${PARAM_DAYS:-30} days');
      "
      
      echo "{\"marked_reviewed\": $COUNT}"
---

# Copilot Money

Manage your finances in [Copilot Money](https://copilot.money) directly through AI. Full read/write access to transactions, categories, and organization.

## Requirements

- **macOS only** - Reads/writes to local Copilot database
- **Copilot Money app** - Must be installed and synced
- **jq** - For JSON processing (`brew install jq`)

## Read Tools

| Tool | Description |
|------|-------------|
| `get_transactions` | List recent transactions |
| `get_transaction` | Get full details of a specific transaction |
| `search` | Search transactions by merchant name |
| `unreviewed` | List transactions needing review |
| `get_categories` | List available categories with IDs |
| `spending_by_month` | Monthly spending totals |
| `spending_by_merchant` | Spending grouped by merchant |
| `spending_by_category` | Spending grouped by category |
| `balances` | Current account balances |
| `net_worth` | Net worth with account breakdown |
| `recurring` | List recurring transactions |
| `hidden` | List hidden/deleted transactions |

## Write Tools

| Tool | Description |
|------|-------------|
| `recategorize` | Change category on a transaction |
| `recategorize_merchant` | Bulk recategorize all transactions from a merchant |
| `add_note` | Add/update note on a transaction |
| `rename` | Set custom merchant name |
| `change_type` | Change type (regular/transfer/income) |
| `hide` | Hide transaction from reports |
| `unhide` | Restore hidden transaction |
| `mark_reviewed` | Mark transaction as reviewed |
| `mark_all_reviewed` | Bulk mark all as reviewed |

## Common Workflows

### Review and categorize transactions
```
# 1. Get unreviewed transactions
unreviewed(days: 7)

# 2. Get available categories
get_categories()

# 3. Recategorize a transaction
recategorize(id: "abc123", category_id: "4P0OGwQa757X8J9N5ZA2")

# 4. Or bulk recategorize all from a merchant
recategorize_merchant(merchant: "TRADER JOE'S", category_id: "y2xtHJ2HbGucRPsm4eXv")
```

### Add notes and organize
```
# Add context to a transaction
add_note(id: "abc123", note: "Business dinner with client")

# Rename confusing merchant
rename(id: "abc123", name: "Costco Gas")

# Mark as transfer instead of spending
change_type(id: "abc123", type: "internal_transfer")
```

### Hide unwanted transactions
```
# Hide a transaction
hide(id: "abc123")

# View hidden transactions
hidden()

# Restore if needed
unhide(id: "abc123")
```

## Notes

- **Sync behavior**: User changes (category, notes, type) persist across Plaid syncs
- **Amount signs**: Negative = spending, positive = income/refunds
- **Categories**: Use `get_categories` to get valid category IDs before recategorizing
- **Bulk ops**: Use `recategorize_merchant` to set up "merchant rules" - all past and future transactions from that merchant will keep your category
- **What's NOT writable locally**: Budget amounts, tag definitions, and account settings are stored in Copilot's cloud (Firestore) and can't be modified locally

## Database Details

- **Database**: `~/Library/Group Containers/group.com.copilot.production/database/CopilotDB.sqlite`
- **Categories**: `~/Library/Group Containers/group.com.copilot.production/widget-data/widgets-category-categories.json`
- **Journal mode**: WAL (safe concurrent access)

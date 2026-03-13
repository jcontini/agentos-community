#!/usr/bin/env python3
"""
Copilot Money — account list
Reads per-account widget JSON files from the Copilot app container.
No auth needed — local files only.
"""

import json
import glob
import sys
import os

WIDGET_DIR = os.path.expanduser(
    "~/Library/Group Containers/group.com.copilot.production/widget-data"
)

def load_accounts():
    pattern = os.path.join(WIDGET_DIR, "widgets-account-account_*.json")
    accounts = []
    for path in sorted(glob.glob(pattern)):
        try:
            with open(path) as f:
                data = json.load(f)
            # Skip placeholder accounts with no name or zero balance and no mask
            if not data.get("name") or data.get("name") == "Account name":
                continue
            accounts.append({
                "id": data.get("id"),
                "name": data.get("name"),
                "mask": data.get("mask"),
                "balance": data.get("balance"),
                "limit": data.get("limit") or None,
                "institution_id": data.get("institutionId"),
                "color": data.get("color"),
            })
        except Exception as e:
            print(f"Warning: could not read {path}: {e}", file=sys.stderr)

    return accounts

if __name__ == "__main__":
    accounts = load_accounts()
    print(json.dumps(accounts, indent=2))

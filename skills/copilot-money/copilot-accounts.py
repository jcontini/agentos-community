#!/usr/bin/env python3
"""
Copilot Money — account list
Reads per-account widget JSON files and Copilot's own credit/other classification.
No auth needed — local files only.
"""

import json
import glob
import sys
import os

WIDGET_DIR = os.path.expanduser(
    "~/Library/Group Containers/group.com.copilot.production/widget-data"
)


def load_credit_ids():
    """Load the set of account IDs that Copilot classifies as credit accounts."""
    path = os.path.join(WIDGET_DIR, "widgets-account-credit_accounts.json")
    try:
        with open(path) as f:
            return {a["id"] for a in json.load(f)}
    except Exception:
        return set()


def classify_account(data, credit_ids):
    """
    Classify an account into tags based on Copilot's own groupings
    and lightweight heuristics. Returns a list of tag names.
    """
    tags = ["financial"]
    account_id = data.get("id")
    name = data.get("name", "")
    institution_id = data.get("institutionId", "")

    # Credit classification from Copilot's own credit_accounts.json
    if account_id in credit_ids:
        tags.append("credit")
    # Crypto
    elif institution_id == "coinbase":
        tags.append("crypto")
    # Name-based heuristics for the rest
    elif any(kw in name.lower() for kw in ("ira", "roth", "401k", "401(k)")):
        tags.append("retirement")
        tags.append("brokerage")
    elif "hsa" in name.lower():
        tags.append("hsa")
        tags.append("brokerage")
    elif "savings" in name.lower():
        tags.append("savings")
    elif "checking" in name.lower():
        tags.append("checking")
    else:
        tags.append("brokerage")

    # Tax treatment
    if any(t in tags for t in ("retirement", "hsa")):
        tags.append("tax-free")
    else:
        tags.append("taxable")

    return tags


def load_accounts():
    credit_ids = load_credit_ids()
    pattern = os.path.join(WIDGET_DIR, "widgets-account-account_*.json")
    accounts = []
    for path in sorted(glob.glob(pattern)):
        try:
            with open(path) as f:
                data = json.load(f)
            # Skip placeholder accounts
            if not data.get("name") or data.get("name") == "Account name":
                continue

            tags = classify_account(data, credit_ids)

            accounts.append({
                "id": data.get("id"),
                "name": data.get("name"),
                "mask": data.get("mask"),
                "balance": data.get("balance"),
                "limit": data.get("limit") or None,
                "institutionId": data.get("institutionId"),
                "color": data.get("color"),
                "tags": tags,
            })
        except Exception as e:
            print(f"Warning: could not read {path}: {e}", file=sys.stderr)

    return accounts


if __name__ == "__main__":
    accounts = load_accounts()
    print(json.dumps(accounts, indent=2))

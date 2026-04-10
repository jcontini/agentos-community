#!/usr/bin/env python3
"""
chase-api.py — Chase Bank internal API client

Confirmed endpoints (reverse-engineered 2026-03-12):

  ACCOUNTS + BALANCES (all accounts in one call):
    POST /svc/rl/accounts/l4/v1/app/data/list  (empty body)
    Response: .cache[] → find url containing "tiles/list" → .response.accountTiles[]
    Fields: accountId, nickname, mask, accountTileType (DDA/CARD),
            tileDetail.currentBalance, tileDetail.availableBalance

  CHECKING/SAVINGS DETAIL:
    POST /svc/rr/accounts/secure/v2/account/detail/dda/list
    Body: accountId=<id>
    Response: .detail.available, .detail.presentBalance

  TRANSACTIONS (checking/savings — DDA accounts):
    GET /svc/rr/accounts/secure/gateway/deposit-account/transactions/
        inquiry-maintenance/etu-dda-transactions/v3/transactions
        ?digital-account-identifier=<accountId>
        &channel-entry-point-identifier=WEB
        &requested-record-count=<n>
        &generic-enrichment-nudge-indicator=true
    Extra header: network-channel-group-code: DIGITAL
    Response: .transactions[] with transactionDate, transactionAmount,
              creditDebitCode (CR/DR), transactionDescription,
              transactionPostDate, runningLedgerBalanceAmount,
              etuStdExpenseCategoryName, pendingTransactionIndicator

Required cookies: AMSESSION, sessioncacheid, auth-guid, dps-pod-id,
                  x-auth-activity-info, akaalb_secure_chase_com
Required headers: x-jpmc-csrf-token: NONE, x-jpmc-channel: id=C30
"""

import json
import sys

from agentos import http, connection, returns, timeout, require_cookies

BASE = "https://secure.chase.com"

EXTRA_HEADERS = {
    "origin": BASE,
    "referer": f"{BASE}/web/auth/dashboard",
    "x-jpmc-channel": "id=C30",
    "x-jpmc-csrf-token": "NONE",
}


def _client(cookie_header: str):
    """HTTP session with Chase-specific headers."""
    return http.client(
        cookies=cookie_header,
        **http.headers(waf="cf", accept="json", extra=EXTRA_HEADERS),
    )




@returns("account")
@connection("web")
@timeout(20)
async def check_session(**params) -> dict:
    """Verify Chase session and identify the account holder."""
    cookie_header = (params.get("auth") or {}).get("cookies", "")
    if not cookie_header:
        return {"authenticated": False, "error": "no cookies"}

    async with _client(cookie_header) as client:
        resp = await client.post(f"{BASE}/svc/rl/accounts/l4/v1/app/data/list")
        if resp["status"] != 200:
            return {"authenticated": False, "error": f"HTTP {resp['status']}"}
        data = resp["json"]

    for entry in data.get("cache", []):
        if not isinstance(entry, dict):
            continue
        if "tiles/list" in entry.get("url", ""):
            tiles = entry.get("response", {}).get("accountTiles", [])
            if tiles:
                first = tiles[0]
                return {
                    "authenticated": True,
                    "domain": "chase.com",
                    "identifier": first.get("accountId", ""),
                    "display": first.get("nickname", ""),
                }

    return {"authenticated": False, "error": "no account tiles"}


@returns("account[]")
@timeout(20)
async def get_accounts(**params) -> list | dict:
    """List all Chase accounts with current balances. Returns checking, savings, and credit card accounts. Balance = current balance. Available = available to spend/credit available."""
    cookie_header = require_cookies(params, "list_accounts")

    async with _client(cookie_header) as client:
        resp = await client.post(f"{BASE}/svc/rl/accounts/l4/v1/app/data/list")
        if resp["status"] in (401, 403):
            raise RuntimeError(f"SESSION_EXPIRED: Chase returned HTTP {resp['status']}")
        if resp["status"] != 200:
            return {"error": f"HTTP {resp['status']}"}
        data = resp["json"]

    tiles: list = []
    for entry in data.get("cache", []):
        if not isinstance(entry, dict):
            continue
        if "tiles/list" in entry.get("url", ""):
            resp_body = entry.get("response", {})
            if isinstance(resp_body, dict):
                tiles = resp_body.get("accountTiles", [])
            break

    if not tiles:
        cache_urls = [e.get("url", "") for e in data.get("cache", []) if isinstance(e, dict)]
        return {"error": "No accountTiles in response", "_cacheUrls": cache_urls}

    return [_normalize_account(t) for t in tiles]


def _normalize_account(t: dict) -> dict:
    detail = t.get("tileDetail", {})
    tile_type = t.get("accountTileType", "")

    if tile_type == "DDA":
        acct_type = "savings" if t.get("accountTileDetailType") == "SAV" else "checking"
    elif tile_type == "CARD":
        acct_type = "credit"
    else:
        acct_type = tile_type.lower() or "unknown"

    acct_id = t.get("accountId", "")
    result: dict = {
        "id": acct_id,
        "issuer": "chase.com",
        "identifier": acct_id,
        "accountId": acct_id,
        "name": t.get("nickname") or f"Chase {acct_type}",
        "accountType": acct_type,
        "last4": t.get("mask"),
        "balance": detail.get("currentBalance"),
        "available": detail.get("availableBalance"),
    }

    if tile_type == "CARD":
        result["cardType"] = t.get("cardType", "")
        result["creditLimit"] = detail.get("creditLimit")
        result["minimumPayment"] = detail.get("minimumPaymentDue")
        result["paymentDueDate"] = detail.get("paymentDueDate")

    return result


@returns("transaction[]")
@timeout(20)
async def get_transactions(*, account_id, limit=30, **params) -> list | dict:
    """List recent transactions for a Chase checking or savings account (DDA accounts only). Returns transactions with date, description, signed amount (negative=debit), running balance, and category. Credit card transactions require a different endpoint (not yet implemented).

        Args:
            account_id: The accountId from account.list (e.g. 123456789)
            limit: Number of transactions to return (default: 30, max: 100)
        """
    cookie_header = require_cookies(params, "list_transactions")
    limit = int(limit)

    url = (
        f"{BASE}/svc/rr/accounts/secure/gateway/deposit-account/transactions"
        f"/inquiry-maintenance/etu-dda-transactions/v3/transactions"
    )
    query_params = {
        "digital-account-identifier": account_id,
        "channel-entry-point-identifier": "WEB",
        "requested-record-count": limit,
        "generic-enrichment-nudge-indicator": "true",
    }

    async with _client(cookie_header) as client:
        resp = await client.get(
            url,
            params=query_params,
            headers={"network-channel-group-code": "DIGITAL"},
        )
        if resp["status"] in (401, 403):
            raise RuntimeError(f"SESSION_EXPIRED: Chase returned HTTP {resp['status']}")
        if resp["status"] != 200:
            return {"error": f"HTTP {resp['status']}"}
        data = resp["json"]

    return [_normalize_transaction(t) for t in data.get("transactions", [])]


def _normalize_transaction(t: dict) -> dict:
    amount = t.get("transactionAmount", 0)
    is_credit = t.get("creditDebitCode", "DR") == "CR"
    signed_amount = amount if is_credit else -amount

    return {
        "date": t.get("transactionDate"),
        "postDate": t.get("transactionPostDate"),
        "description": t.get("transactionDescription"),
        "amount": signed_amount,
        "balance": t.get("runningLedgerBalanceAmount"),
        "category": t.get("etuStdExpenseCategoryName"),
        "type": t.get("etuStdTransactionGroupName"),
        "pending": t.get("pendingTransactionIndicator", False),
        "transactionId": t.get("transactionIdentifier"),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Chase Bank API client")
    parser.add_argument("op", choices=["accounts", "transactions"])
    parser.add_argument("--cookies", required=True, help="Full cookie string from browser session")
    parser.add_argument("--account-id", help="Account ID (required for transactions)")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    auth = {"cookies": args.cookies}

    if args.op == "accounts":
        result = get_accounts(auth=auth)
    else:
        result = get_transactions(account_id=args.account_id, limit=args.limit, auth=auth)

    print(json.dumps(result, indent=2))

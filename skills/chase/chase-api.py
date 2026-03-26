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

Usage:
  chase-api.py accounts --cookies "AMSESSION=...; ..."
  chase-api.py transactions --cookies "..." --account-id 123456789 [--limit 30]
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://secure.chase.com"

BASE_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "origin": BASE,
    "referer": f"{BASE}/web/auth/dashboard",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "x-jpmc-channel": "id=C30",
    "x-jpmc-csrf-token": "NONE",
}


def request(method: str, path: str, cookies: str, body: bytes = b"", extra_headers: dict | None = None) -> dict:
    url = path if path.startswith("http") else f"{BASE}{path}"
    req = urllib.request.Request(url, data=body or None, method=method)
    for k, v in BASE_HEADERS.items():
        req.add_header(k, v)
    if extra_headers:
        for k, v in extra_headers.items():
            req.add_header(k, v)
    req.add_header("cookie", cookies)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:300]
        return {"error": f"HTTP {e.code}", "detail": detail}


def check_session(params: dict | None = None) -> dict:
    """Verify Chase session and identify the account holder."""
    params = params or {}
    cookie_header = (params.get("auth") or {}).get("cookies", "")
    if not cookie_header:
        return {"authenticated": False, "error": "no cookies"}

    data = request("POST", "/svc/rl/accounts/l4/v1/app/data/list", cookie_header)
    if "error" in data:
        return {"authenticated": False, "error": data.get("error")}

    # Find account tiles
    for entry in data.get("cache", []):
        if not isinstance(entry, dict):
            continue
        if "tiles/list" in entry.get("url", ""):
            tiles = entry.get("response", {}).get("accountTiles", [])
            if tiles:
                first = tiles[0]
                return {
                    "authenticated": True,
                    "issuer": "chase.com",
                    "identifier": first.get("accountId", ""),
                    "display": first.get("nickname", ""),
                }

    return {"authenticated": False, "error": "no account tiles"}


def get_accounts(cookies: str) -> list | dict:
    data = request("POST", "/svc/rl/accounts/l4/v1/app/data/list", cookies)
    if "error" in data:
        return data

    tiles: list = []
    for entry in data.get("cache", []):
        if not isinstance(entry, dict):
            continue
        if "tiles/list" in entry.get("url", ""):
            resp = entry.get("response", {})
            if isinstance(resp, dict):
                tiles = resp.get("accountTiles", [])
            break

    if not tiles:
        cache_urls = [e.get("url", "") for e in data.get("cache", []) if isinstance(e, dict)]
        return {"error": "No accountTiles in response", "cache_urls": cache_urls}

    return [normalize_account(t) for t in tiles]


def normalize_account(t: dict) -> dict:
    detail = t.get("tileDetail", {})
    tile_type = t.get("accountTileType", "")

    if tile_type == "DDA":
        acct_type = "savings" if t.get("accountTileDetailType") == "SAV" else "checking"
    elif tile_type == "CARD":
        acct_type = "credit"
    else:
        acct_type = tile_type.lower() or "unknown"

    result: dict = {
        "accountId": t.get("accountId"),
        "name": t.get("nickname"),
        "type": acct_type,
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


def get_transactions(cookies: str, account_id: str, limit: int = 30) -> list | dict:
    params = urllib.parse.urlencode({
        "digital-account-identifier": account_id,
        "channel-entry-point-identifier": "WEB",
        "requested-record-count": limit,
        "generic-enrichment-nudge-indicator": "true",
    })
    path = (
        "/svc/rr/accounts/secure/gateway/deposit-account/transactions"
        "/inquiry-maintenance/etu-dda-transactions/v3/transactions"
        f"?{params}"
    )
    data = request("GET", path, cookies, extra_headers={"network-channel-group-code": "DIGITAL"})

    if "error" in data:
        return data

    return [normalize_transaction(t) for t in data.get("transactions", [])]


def normalize_transaction(t: dict) -> dict:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Chase Bank API client")
    parser.add_argument("op", choices=["accounts", "transactions"])
    parser.add_argument("--cookies", required=True, help="Full cookie string from browser session")
    parser.add_argument("--account-id", help="Account ID (required for transactions)")
    parser.add_argument("--limit", type=int, default=30, help="Number of transactions to fetch (default: 30)")
    args = parser.parse_args()

    result: list | dict
    if args.op == "accounts":
        result = get_accounts(args.cookies)
    elif args.op == "transactions":
        if not args.account_id:
            result = {"error": "--account-id required for transactions"}
        else:
            result = get_transactions(args.cookies, args.account_id, args.limit)
    else:
        result = {"error": f"unknown op: {args.op}"}

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

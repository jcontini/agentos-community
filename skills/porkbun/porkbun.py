"""Porkbun — domain and DNS management via the Porkbun API."""

from agentos import http, connection, returns

API_BASE = "https://api.porkbun.com/api/json/v3"


def _auth(params: dict) -> tuple[str, str]:
    """Split 'apikey:secretapikey' credential."""
    key = params.get("auth", {}).get("key", "")
    parts = key.split(":", 1)
    return (parts[0], parts[1] if len(parts) > 1 else "")


def _map_domain(d: dict) -> dict:
    domain = d.get("domain", "")
    return {
        "id": domain,
        "url": f"https://{domain}" if domain else None,
        "status": d.get("status"),
        "registrar": "porkbun",
        "expiresAt": d.get("expireDate"),
        "autoRenew": d.get("autoRenew") == "yes",
        "createdAt": d.get("createDate"),
    }


def _map_dns_record(r: dict, domain: str = "") -> dict:
    rid = r.get("id", "")
    name = r.get("name", "")
    full_name = f"{name}.{domain}" if name and domain else (domain or name)
    ttl = r.get("ttl")
    return {
        "id": f"{domain}:{rid}" if domain else str(rid),
        "name": full_name,
        "content": f"{r.get('type', '')} {r.get('content', '')}",
        "recordId": str(rid),
        "domain": domain,
        "type": r.get("type"),
        "content": r.get("content"),
        "ttl": int(ttl) if ttl is not None else None,
        "priority": r.get("prio") or None,
    }


@returns("domain[]")
@connection("api")
def list_domains(**params) -> list[dict]:
    """List all domains in your Porkbun account"""
    api_key, secret_key = _auth(params)
    resp = http.post(f"{API_BASE}/domain/listAll",
                     json={"apikey": api_key, "secretapikey": secret_key},
                     **http.headers(accept="json"))
    return [_map_domain(d) for d in (resp["json"] or {}).get("domains", [])]


@returns("dns_record[]")
@connection("api")
def list_dns_records(*, domain: str, **params) -> list[dict]:
    """List all DNS records for a domain

        Args:
            domain: Domain name, for example example.com
        """
    api_key, secret_key = _auth(params)
    resp = http.post(f"{API_BASE}/dns/retrieve/{domain}",
                     json={"apikey": api_key, "secretapikey": secret_key},
                     **http.headers(accept="json"))
    return [_map_dns_record(r, domain) for r in (resp["json"] or {}).get("records", [])]


@returns("void")
@connection("api")
def create_dns_record(*, domain: str, type: str, content: str, name: str = "", ttl: int = 600, prio: int = None, **params) -> dict:
    """Create a new DNS record for a domain

        Args:
            domain: Domain name
            name: Subdomain, omit or empty string for the apex
            type: A, AAAA, CNAME, MX, TXT, NS, or SRV
            content: Record value
            ttl: TTL in seconds
            prio: Priority, used for MX records
        """
    api_key, secret_key = _auth(params)
    body: dict = {
        "apikey": api_key, "secretapikey": secret_key,
        "name": name or "", "type": type, "content": content,
        "ttl": str(ttl or 600),
    }
    if prio is not None:
        body["prio"] = prio
    resp = http.post(f"{API_BASE}/dns/create/{domain}", json=body, **http.headers(accept="json"))
    return resp["json"]


@returns("void")
@connection("api")
def update_dns_record(*, domain: str, id: str, type: str, content: str, name: str = "", ttl: int = 600, prio: int = None, **params) -> dict:
    """Update an existing DNS record

        Args:
            domain: Domain name
            id: Porkbun DNS record ID
            name: Subdomain, omit or empty string for the apex
            type: Record type
            content: Record value
            ttl: TTL in seconds
            prio: Priority, used for MX records
        """
    api_key, secret_key = _auth(params)
    body: dict = {
        "apikey": api_key, "secretapikey": secret_key,
        "name": name or "", "type": type, "content": content,
        "ttl": str(ttl or 600),
    }
    if prio is not None:
        body["prio"] = prio
    resp = http.post(f"{API_BASE}/dns/edit/{domain}/{id}", json=body, **http.headers(accept="json"))
    return resp["json"]


@returns("void")
@connection("api")
def delete_dns_record(*, domain: str, id: str, **params) -> dict:
    """Delete a DNS record from a domain

        Args:
            domain: Domain name
            id: Porkbun DNS record ID
        """
    api_key, secret_key = _auth(params)
    resp = http.post(f"{API_BASE}/dns/delete/{domain}/{id}",
                     json={"apikey": api_key, "secretapikey": secret_key},
                     **http.headers(accept="json"))
    return resp["json"]

"""Gandi — domain and DNS management via the Gandi API."""

from agentos import http

GANDI_BASE = "https://api.gandi.net/v5"


def _auth_header(params: dict) -> dict:
    key = params.get("auth", {}).get("key", "")
    return {"Authorization": f"Bearer {key}"}


def _map_domain(d: dict) -> dict:
    dates = d.get("dates") or {}
    nameserver = d.get("nameserver") or {}
    fqdn = d.get("fqdn", "")
    return {
        "id": fqdn,
        "url": f"https://{fqdn}" if fqdn else None,
        "status": d.get("status"),
        "registrar": "gandi",
        "expires_at": dates.get("registry_ends_at"),
        "auto_renew": d.get("autorenew"),
        "nameservers": nameserver.get("current"),
    }


def _map_dns_record(r: dict, domain: str = "") -> dict:
    rr_name = r.get("rrset_name", "")
    if not rr_name or rr_name == "@":
        name = domain
    else:
        name = f"{rr_name}.{domain}" if domain else rr_name
    return {
        "id": f"{domain}:{rr_name}:{r.get('rrset_type', '')}",
        "name": name,
        "text": f"{r.get('rrset_type', '')} {', '.join(r.get('rrset_values') or [])}",
        "domain": domain,
        "record_name": rr_name,
        "record_type": r.get("rrset_type"),
        "ttl": r.get("rrset_ttl"),
        "values": r.get("rrset_values"),
    }


def list_domains(**params) -> list[dict]:
    resp = http.get(f"{GANDI_BASE}/domain/domains", **http.headers(accept="json", extra=_auth_header(params)))
    return [_map_domain(d) for d in (resp["json"] or [])]


def get_domain(*, domain: str, **params) -> dict:
    resp = http.get(f"{GANDI_BASE}/domain/domains/{domain}", **http.headers(accept="json", extra=_auth_header(params)))
    return _map_domain(resp["json"])


def list_dns_records(*, domain: str, **params) -> list[dict]:
    resp = http.get(
        f"{GANDI_BASE}/livedns/domains/{domain}/records",
        **http.headers(accept="json", extra=_auth_header(params)),
    )
    return [_map_dns_record(r, domain) for r in (resp["json"] or [])]


def get_dns_record(*, domain: str, name: str, type: str, **params) -> dict:
    resp = http.get(
        f"{GANDI_BASE}/livedns/domains/{domain}/records/{name}/{type}",
        **http.headers(accept="json", extra=_auth_header(params)),
    )
    return _map_dns_record(resp["json"], domain)


def upsert_dns_record(*, domain: str, name: str, type: str, values: list, ttl: int = 3600, **params) -> dict:
    resp = http.put(
        f"{GANDI_BASE}/livedns/domains/{domain}/records/{name}/{type}",
        json={"rrset_ttl": ttl or 3600, "rrset_values": values},
        **http.headers(accept="json", extra=_auth_header(params)),
    )
    return resp["json"] or {"success": True}


def delete_dns_record(*, domain: str, name: str, type: str, **params) -> None:
    http.delete(
        f"{GANDI_BASE}/livedns/domains/{domain}/records/{name}/{type}",
        **http.headers(accept="json", extra=_auth_header(params)),
    )

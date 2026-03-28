CDN = "https://img.logo.dev"


def _base_url(path: str, token: str, size: int, format: str) -> str:
    return f"{CDN}/{path}?token={token}&size={size}&format={format}"


def logo_url(*, domain: str, size: int = 128, format: str = "png",
             theme: str = "auto", **params) -> dict:
    token = params.get("auth", {}).get("key", "")
    url = _base_url(domain, token, size, format) + f"&theme={theme}"
    return {"url": url}


def ticker_url(*, ticker: str, size: int = 128, format: str = "png",
               **params) -> dict:
    token = params.get("auth", {}).get("key", "")
    return {"url": _base_url(f"ticker:{ticker}", token, size, format)}


def name_url(*, name: str, size: int = 128, format: str = "png",
             **params) -> dict:
    from urllib.parse import quote
    token = params.get("auth", {}).get("key", "")
    return {"url": _base_url(f"name:{quote(name)}", token, size, format)}


def crypto_url(*, symbol: str, size: int = 128, format: str = "png",
               **params) -> dict:
    token = params.get("auth", {}).get("key", "")
    return {"url": _base_url(f"crypto:{symbol}", token, size, format)}

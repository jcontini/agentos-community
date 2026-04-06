CDN = "https://img.logo.dev"


def _base_url(path: str, token: str, size: int, format: str) -> str:
    return f"{CDN}/{path}?token={token}&size={size}&format={format}"


@returns({"url": "string"})
@connection("api")
@timeout(5)
def logo_url(*, domain: str, size: int = 128, format: str = "png",
    """Return CDN URL for a company logo by domain

        Args:
            domain: Domain (e.g., shopify.com)
            size: Size in pixels (16-800)
            format: Image format (jpg, png, webp)
            theme: Theme (auto, light, dark)
        """
             theme: str = "auto", **params) -> dict:
    token = params.get("auth", {}).get("key", "")
    url = _base_url(domain, token, size, format) + f"&theme={theme}"
    return {"url": url}


@returns({"url": "string"})
@connection("api")
@timeout(5)
def ticker_url(*, ticker: str, size: int = 128, format: str = "png",
    """Return CDN URL for a company logo by stock ticker

        Args:
            ticker: Stock ticker (e.g., AAPL)
            size: Size in pixels
            format: Image format
        """
               **params) -> dict:
    token = params.get("auth", {}).get("key", "")
    return {"url": _base_url(f"ticker:{ticker}", token, size, format)}


@returns({"url": "string"})
@connection("api")
@timeout(5)
def name_url(*, name: str, size: int = 128, format: str = "png",
    """Return CDN URL for a company logo by name

        Args:
            name: Company name (e.g., Shopify)
            size: Size in pixels
            format: Image format
        """
             **params) -> dict:
    from urllib.parse import quote
from agentos import connection, returns, timeout
    token = params.get("auth", {}).get("key", "")
    return {"url": _base_url(f"name:{quote(name)}", token, size, format)}


@returns({"url": "string"})
@connection("api")
@timeout(5)
def crypto_url(*, symbol: str, size: int = 128, format: str = "png",
    """Return CDN URL for a cryptocurrency logo

        Args:
            symbol: Crypto symbol (e.g., BTC, ETH)
            size: Size in pixels
            format: Image format
        """
               **params) -> dict:
    token = params.get("auth", {}).get("key", "")
    return {"url": _base_url(f"crypto:{symbol}", token, size, format)}

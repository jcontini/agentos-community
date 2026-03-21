# Amazon (retail search) — requirements

## Goals

- **Public search**: Hit the normal Amazon retail SERP (`/s?k=…`) with no credentials, same as a logged-out browser.
- **Session search**: Optionally send the user’s Amazon cookies (from an installed cookie provider) for the same URLs — personalized offers, shipping hints, etc.
- **Dynamic `web_search` hook**: Register URL patterns so `web_search` routes to this skill when the caller passes an `url` under `amazon.*` (see `provides:` in `skill.yaml`).

## APIs and constraints

| Surface | Notes |
|--------|--------|
| **Retail HTML** | No stable public JSON for “search products”. HTML layout changes; parser targets organic `role="listitem"` + `data-component-type="s-search-result"` blocks and skips `AdHolder` sponsored rows. |
| **Product Advertising API (PA-API 5)** | Official catalog access; requires AWS access keys, Associate tag, request signing, and program enrollment. Out of scope for this skill — use scraping + optional cookies instead. |
| **Other “Amazon APIs”** | Selling Partner, etc., are seller/developer programs, not consumer product browse. |

## Transport

- Use **httpx** with **`http2=True`** and browser-like headers (see `CONTRIBUTING.md` and `skills/austin-boulder-project/abp.py`). Plain `urllib` often gets **503** from Amazon’s edge.

## Multi-connection model

- **`public`**: `base_url` only — no auth. Default for `search`.
- **`web`**: Same `base_url` + `.amazon.com` cookies, `optional: true` so the skill still loads without a browser provider.
- Python receives runtime `connection` (name + `base_url`) and dispatches the same parser for both; only the `Cookie` header differs.

## Entity shape

- Adapter **`product`**: `asin` as stable id, canonical `name`/`text`/`url`/`image`, `data.price` / `data.rating` when parsed.

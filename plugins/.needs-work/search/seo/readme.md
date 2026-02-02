---
id: seo
name: SEO Scraper
description: Crawl websites and extract SEO meta tags (title, description, keywords)
icon: icon.svg
display: browser

website: https://example.com
privacy_url: 
terms_url: 

instructions: |
  SEO Scraper notes:
  - Crawls sitemaps to find all pages
  - Extracts meta tags from HTML
  - Uses Googlebot user agent to simulate search engine crawler
  - Outputs structured SEO data

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  webpage:
    terminology: Page
    mapping:
      url: .url
      title: .title
      description: .description
      keywords: .keywords
      status_code: .status_code

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  webpage.crawl_sitemap:
    description: Crawl a website's sitemap and extract SEO meta tags from all pages
    returns: webpage[]
    params:
      url: { type: string, required: true, description: "Base URL or sitemap URL" }
      limit: { type: integer, default: 100, description: "Max pages to crawl" }
    # TODO: Implement using command executor or Python script
    # Based on skills/seo/SEOcrawler.py and sitemap_seo_crawler.py

  webpage.get_meta:
    description: Extract SEO meta tags from a single page
    returns: webpage
    params:
      url: { type: string, required: true, description: "URL to extract meta tags from" }
    # TODO: Implement using curl + HTML parsing
    # Extract: title, description, keywords, og:tags, etc.

---

# SEO Scraper

Crawl websites and extract SEO meta tags (title, description, keywords) using Googlebot user agent simulation.

## Features

- Finds sitemap from `/sitemap.xml` or `robots.txt`
- Crawls all URLs in sitemap
- Extracts SEO meta tags (title, description, keywords)
- Uses Googlebot user agent to simulate search engine crawler
- Outputs structured data

## How It Works

1. **Find sitemap** - Check `/sitemap.xml` or parse `robots.txt`
2. **Extract URLs** - Parse sitemap XML to get all page URLs
3. **Crawl pages** - Fetch each URL with Googlebot user agent
4. **Extract meta tags** - Parse HTML for `<title>`, `<meta name="description">`, `<meta name="keywords">`
5. **Return structured data** - JSON with URL, title, description, keywords, status code

## User Agent

Uses Googlebot user agent to simulate search engine crawler:
```
Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)
```

## Implementation Notes

- Based on `skills/seo/SEOcrawler.py` and `skills/seo/sitemap_seo_crawler.py`
- Can use Python script with `requests` and `beautifulsoup4`
- Or use command executor with curl + HTML parsing
- Consider rate limiting to avoid overwhelming target sites
- Output format: CSV or JSON array

## Examples

```bash
# Crawl entire sitemap
POST /api/plugins/seo/webpage.crawl_sitemap
{"url": "https://example.com", "limit": 50}
# → [{url: "...", title: "...", description: "...", keywords: "..."}, ...]

# Get meta tags for single page
POST /api/plugins/seo/webpage.get_meta
{"url": "https://example.com/page"}
# → {url: "...", title: "...", description: "...", keywords: "..."}
```

## Future Extensions

- Extract Open Graph tags (`og:title`, `og:description`, `og:image`)
- Extract Twitter Card tags
- Extract structured data (JSON-LD, microdata)
- Check canonical URLs
- Validate meta tag formats

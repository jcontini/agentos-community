"""Standard tool constants — the vocabulary of capabilities skills can provide.

Import these for @provides decorators. Using constants instead of strings gives:
- IDE autocomplete
- Typo detection (@provides(web_serach) → NameError at import time)
- Discoverability (agent-sdk tools)
- One definition, everywhere

Usage:
    from agentos import provides, web_search, web_read

    @provides(web_search)
    def search(query: str, **params) -> list[dict]:
        ...
"""

# Discovery & retrieval
web_search = "web_search"
web_read = "web_read"

# People
email_lookup = "email_lookup"

# Travel
flight_search = "flight_search"
geocoding = "geocoding"
map_tiles = "map_tiles"

# Files
file_list = "file_list"
file_read = "file_read"
file_info = "file_info"

# Auth provision (browser cookie providers, OAuth providers)
cookie_auth = "cookie_auth"

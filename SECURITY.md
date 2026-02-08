# Security Policy

## Supported Versions

We actively support security updates for the current version of the AgentOS community integrations.

## Reporting a Vulnerability

**Do not open a public issue** for security vulnerabilities.

Instead, please email security concerns to: **agentos@contini.co**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We'll respond within 48 hours and work with you to address the issue before public disclosure.

## Security Considerations

### Adapter Credentials

Adapters handle API credentials through AgentOS's credential management system. **Never**:

- Hardcode credentials in adapter YAML
- Use `$AUTH_TOKEN` or `${AUTH_TOKEN}` patterns
- Include `curl`/`wget` commands with authorization headers
- Interpolate Bearer tokens directly (`Bearer $token`)

**Pre-commit hooks automatically block** these patterns. Use AgentOS executors (`rest:`, `graphql:`, `sql:`) which handle auth automatically.

### Adapter Validation

All adapters are validated before commit:
- Schema validation prevents malformed YAML
- Security checks block credential exposure patterns
- Test coverage ensures operations work as expected

### Network Security (Content Security Policy)

AgentOS uses Content Security Policy (CSP) to control which external resources adapters can load. This prevents malicious content injection and limits data exfiltration.

**How it works:**

1. Adapters declare external sources they need in their config:
   ```yaml
   sources:
     images:
       - "https://i.ytimg.com/*"    # YouTube thumbnails
     api:
       - "https://api.service.com/*"
   ```

2. Server collects sources from all **enabled** adapters at startup
3. CSP header is built dynamically from collected sources
4. Browser blocks any resources not in the allowlist

**Source categories:**

| Category | CSP Directive | Purpose |
|----------|---------------|---------|
| `images` | `img-src` | Thumbnails, avatars, media |
| `api` | `connect-src` | API calls, WebSocket |
| `scripts` | `script-src` | External JavaScript |
| `styles` | `style-src` | External CSS |
| `fonts` | `font-src` | Web fonts |

**Security benefits:**

- **Least privilege** — adapters only get access to sources they declare
- **Dynamic allowlist** — disabling a adapter removes its sources
- **Transparent** — sources are visible in adapter YAML
- **Defense in depth** — even if adapter code is compromised, it can't load arbitrary external resources

**Best practices for adapter authors:**

- Declare only the sources you actually need
- Use specific domains, not wildcards when possible
- Prefer `images` and `api` over `scripts` (external scripts are higher risk)
- Document why each source is needed (comments in YAML)

### Best Practices

When contributing adapters:

1. **Use AgentOS auth system** — credentials are stored securely, not in adapter files
2. **Validate inputs** — use schema validation for parameters
3. **Handle errors gracefully** — don't expose sensitive info in error messages
4. **Test securely** — use test credentials, never production keys
5. **Review before commit** — pre-commit hooks catch common issues
6. **Declare external sources** — use `sources:` for any external resources (see Network Security above)

## Scope

**In scope:**
- Vulnerabilities in adapter YAML configurations
- Credential exposure in adapter files
- Security issues in test files
- Schema validation bypasses
- Vulnerabilities in AgentOS core (we'll route internally)

**Out of scope:**
- Vulnerabilities in third-party services (report to service provider)
- Feature requests or general questions (use regular issues)

## Disclosure Policy

We follow responsible disclosure:
1. Report privately via email
2. We'll acknowledge within 48 hours
3. We'll work together to fix the issue
4. Public disclosure after fix is released (with your permission)

Thank you for helping keep the AgentOS community secure.

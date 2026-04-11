---
id: greptile
name: Greptile
description: AI code review and codebase search — organization and member management via dashboard session
color: "#16B364"
website: "https://greptile.com"
privacy_url: "https://www.greptile.com/privacy"
terms_url: "https://www.greptile.com/terms"

connections:
  dashboard:
    base_url: https://app.greptile.com
    domain: app.greptile.com
    auth:
      type: cookies
      domain: app.greptile.com
      names:
        - __Secure-authjs.session-token
      account:
        check: check_session
    label: Dashboard session
    help_url: https://app.greptile.com/settings/organization/people

product:
  name: Greptile
  website: https://greptile.com
  developer: Greptile, Inc.

test:
  check_session:
    expect:
      authenticated: true
  list_members:
    expect_count_at_least: 1
---

# Greptile

AI code review and codebase search. This skill manages **organization membership** via the dashboard session — listing members, sending invites, generating invite links, updating roles, and removing members.

## Setup

1. Log into https://app.greptile.com in Brave.
2. The engine auto-resolves cookies from Brave for `app.greptile.com`.
3. `run({skill:"greptile", tool:"check_session"})` should return `{authenticated: true, ...}`.

## Auth architecture

Greptile uses **Auth.js v5** (the rebrand of NextAuth) on `app.greptile.com`.

| Cookie | Domain | Purpose |
|--------|--------|---------|
| `__Host-authjs.csrf-token` | app.greptile.com | CSRF double-submit (value is `token%7Chash`) |
| `__Secure-authjs.callback-url` | app.greptile.com | Post-auth redirect target |
| `__Secure-authjs.session-token` | app.greptile.com | **The session JWT (JWE)** — the one that matters |
| `greptile_logged_in` | .greptile.com | Marketing-side flag |

For authenticated dashboard API calls you only need `__Secure-authjs.session-token`.

## People / Org API (reverse-engineered)

The organization settings page is a Next.js SPA at `/settings/organization/people`. It uses **tRPC** under the hood — every mutation/query goes through `/api/trpc/<procedure>` on `app.greptile.com`.

- GET (queries): `/api/trpc/<procedure>?input=<urlencoded {"json":<args>}>`
- POST (mutations): `/api/trpc/<procedure>` with body `{"json":<args>}`
- Envelope (responses): `{"result":{"data":{"json":<payload>}}}` on success, `{"error":{"json":{"message":...,"code":...}}}` on failure

All procedures take `tenantExternalId` from the session's `currentTenantExternalId`. Arg shapes captured from call sites in the minified page bundle (chunk `164-*.js`).

| Operation | tRPC procedure | Method | Args |
|---|---|---|---|
| Session / identity | `/api/auth/session` (Auth.js) | GET | — |
| List members + invites | `organization.searchPeople` | GET | `{tenantExternalId, query, roles?, page, pageSize}` |
| Send email invite | `invitation.create` | POST | `{tenantExternalId, email, role}` |
| Get invite link | `invitation.getOrganizationInviteLink` | GET | `{tenantExternalId}` |
| Create/rotate invite link | `invitation.createOrganizationInviteLink` | POST | `{tenantExternalId, defaultRole}` |
| Revoke invite link | `invitation.revokeOrganizationInviteLink` | POST | `{tenantExternalId}` |
| Revoke pending invite | `invitation.revoke` | POST | `{email, tenantExternalId}` |
| Update member role | `organization.setMemberRole` | POST | `{tenantExternalId, email, role}` |
| Remove member | `organization.removeMember` | POST | `{email, tenantExternalId}` |

**Invite link format:** `https://app.greptile.com/invitation?token=<token>` — assembled in the "Copy Invite Link" button's onClick: `` `${appUrl}/invitation?token=${token}` ``.

**Roles:** `ADMIN` or `MEMBER` (enum `n.X` in the bundle). Accepted case-insensitively by the skill.

**Namespace vs. organization:** the bundle also uses `namespace.*` procedures (`namespace.removeMember`, `namespace.updateMemberRole`, `namespace.addMember`) for **per-repo** access control. This skill intentionally only wires the org-level procedures — remove from the org, not from a namespace.

There is also a separate backend at `https://api.greptile.com` (Express, Bearer JWT from `greptileToken` in the session). Not used by this skill — member management lives entirely on the dashboard's tRPC route.

## Tools

- `check_session` — validate dashboard cookies, return identity.
- `list_members` — list all org members + pending invites (returns `account[]`).
- `send_invite` — send an email invite (`invitation.create`).
- `get_invite_link` — fetch the shareable org invite link (URL + token).
- `create_invite_link` — create or rotate the shareable link; `defaultRole` arg.
- `revoke_invite_link` — revoke the shareable org invite link entirely.
- `revoke_invite` — revoke a single pending email invite.
- `update_role` — change a member's role (ADMIN / MEMBER).
- `remove_member` — remove a member from the org.
- `probe`, `backend_probe`, `grep_bundle`, `grep_page_chunks`, `inspect_auth` — reverse-engineering helpers. Leave in place while the API is still being mapped; don't ship them in a "stable" skill.

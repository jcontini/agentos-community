---
priority: high
---

# Skill Signup Utility

A standard `signup` utility pattern that lets agents programmatically onboard users to a service — sending a magic link, walking through OAuth, or guiding API key creation — directly from within a skill.

## Problem

Skills declare how to *use* credentials (`auth:`) but have no way to help users *get* them. Today, the flow is: "go to the service website, find the API keys page, copy the key, paste it here." That's slow and breaks agent flow.

Some services (here.now, Linear, Notion) support agent-assisted onboarding: the agent sends a magic link or initiates OAuth, the user clicks once, and credentials are ready. We should make this a first-class skill capability.

## Proposed Pattern

A new `signup` utility in skills that guides credential acquisition:

```yaml
utilities:
  signup:
    description: |
      Send a magic link to the user's email. They click it, land on the
      dashboard, copy their API key, and paste it into AgentOS credentials.
    params:
      email:
        type: string
        required: true
        description: User's email address
    returns:
      sent: boolean
      message: string
    rest:
      method: POST
      url: https://api.myservice.com/auth/magic-link
      body:
        email: .params.email
      response:
        mapping:
          sent: 'true'
          message: '"Check your inbox for a sign-in link. Once you\'re in, copy your API key and add it to AgentOS."'
```

## Signup Modes

| Mode | How it works | Services |
|------|-------------|----------|
| Magic link | Agent posts email → user clicks link → gets API key | here.now, Linear |
| OAuth | Agent opens browser URL → user authorizes → token returned | GitHub, Google, Spotify |
| Self-serve key | Agent links to API keys page, user copies | Most REST APIs |
| Direct creation | Agent calls API to create key on user's behalf | Rare (admin tokens) |

## Credential Storage After Signup

After the user provides the key, the agent stores it:

```bash
POST /api/settings/credentials
{ "skill": "here-now", "key": "sk-..." }
```

The `signup` utility's `message` field should tell the user exactly what to do next and what endpoint to use.

## here.now as Reference Implementation

here.now already supports this via `POST /api/auth/login`. The here.now skill should add a `signup` utility as the reference implementation for this pattern.

## Broader Implications

- Should `auth:` config support a `signup_utility: signup` pointer so the UI knows to show an "Add account" flow?
- Should the Settings connectors page call `signup` when a user hasn't configured credentials?
- Could this unify with OAuth2 flows — where the browser-open dance is just another signup mode?

This is the missing piece between "skill is installed" and "skill has credentials." Closing that gap makes skill onboarding feel native rather than bolted on.

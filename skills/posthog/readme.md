---
id: posthog
name: PostHog
description: Product analytics — events, persons, and session recordings
icon: icon.svg
color: "#1D4AFF"

website: https://posthog.com
privacy_url: https://posthog.com/privacy
terms_url: https://posthog.com/terms

auth:
  header:
    Authorization: "Bearer {token}"
  label: Personal API Key
  help_url: https://us.posthog.com/settings/user-api-keys

connects_to: posthog

seed:
  - id: posthog
    types: [software]
    name: PostHog
    data:
      software_type: api
      url: https://posthog.com
      launched: "2020"
      platforms: [web, api]
      pricing: freemium
    relationships:
      - role: offered_by
        to: posthog-inc

  - id: posthog-inc
    types: [organization]
    name: PostHog Inc.
    data:
      type: company
      url: https://posthog.com
      founded: "2020"

instructions: |
  PostHog project ID is required for all API calls. It appears in the URL path.
  Ask the user for their project ID if not known, or call the get_projects utility.

  The events API is deprecated. For querying events, use the query utility which
  sends HogQL queries to the /query endpoint. For listing recent events by name,
  the deprecated events endpoint still works but is limited to 24h without date params.

  Persons can be searched by email via the ?search= query parameter.

  Session recordings list returns metadata only, not replay data.

  Rate limits: 240/min and 1200/hour for analytics endpoints.

# ═══════════════════════════════════════════════════════════════════════════════
# TRANSFORMERS
# ═══════════════════════════════════════════════════════════════════════════════

transformers:
  person:
    terminology: Person
    mapping:
      id: .uuid
      name: '(.properties.name // .properties.email // .distinct_ids[0] // "Unknown")'
      email: .properties.email
      created_at: .created_at
      data.distinct_ids: .distinct_ids
      data.last_seen_at: .last_seen_at
      data.browser: .properties."$browser"
      data.os: .properties."$os"
      data.initial_referrer: .properties."$initial_referrer"
      data.initial_utm_source: .properties."$initial_utm_source"
      data.posthog_uuid: .uuid

  event:
    terminology: Event
    mapping:
      id: .id
      title: .event
      start: .timestamp
      description: '(.properties | keys | join(", "))'
      data.event_name: .event
      data.distinct_id: .distinct_id
      data.properties: .properties
      data.timestamp: .timestamp
      data.current_url: .properties."$current_url"
      data.person: .person

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  person.list:
    description: List persons in a project
    returns: person[]
    params:
      project_id: { type: string, required: true, description: "PostHog project ID" }
      search: { type: string, description: "Search by email or name" }
      limit: { type: integer }
      offset: { type: integer }
    rest:
      method: GET
      url: '"https://us.posthog.com/api/projects/" + .params.project_id + "/persons/"'
      query:
        search: .params.search
        limit: '.params.limit | if . then tostring else null end'
        offset: '.params.offset | if . then tostring else null end'
      response:
        root: /results

  person.get:
    description: Get a person by UUID
    returns: person
    params:
      project_id: { type: string, required: true, description: "PostHog project ID" }
      id: { type: string, required: true, description: "Person UUID" }
    rest:
      method: GET
      url: '"https://us.posthog.com/api/projects/" + .params.project_id + "/persons/" + .params.id + "/"'

  person.search:
    description: Search persons by email or name
    returns: person[]
    params:
      project_id: { type: string, required: true, description: "PostHog project ID" }
      query: { type: string, required: true, description: "Email or name to search for" }
      limit: { type: integer }
    rest:
      method: GET
      url: '"https://us.posthog.com/api/projects/" + .params.project_id + "/persons/"'
      query:
        search: .params.query
        limit: '.params.limit | if . then tostring else null end'
      response:
        root: /results

  event.list:
    description: List recent events (deprecated API — use query utility for complex queries)
    returns: event[]
    params:
      project_id: { type: string, required: true, description: "PostHog project ID" }
      event: { type: string, description: "Filter by event name" }
      limit: { type: integer }
      after: { type: string, description: "ISO datetime — only events after this time" }
      before: { type: string, description: "ISO datetime — only events before this time" }
    rest:
      method: GET
      url: '"https://us.posthog.com/api/projects/" + .params.project_id + "/events/"'
      query:
        event: .params.event
        limit: '.params.limit | if . then tostring else null end'
        after: .params.after
        before: .params.before
      response:
        root: /results

  event.get:
    description: Get a single event by ID
    returns: event
    params:
      project_id: { type: string, required: true, description: "PostHog project ID" }
      id: { type: string, required: true, description: "Event ID" }
    rest:
      method: GET
      url: '"https://us.posthog.com/api/projects/" + .params.project_id + "/events/" + .params.id + "/"'

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

utilities:
  get_projects:
    description: List all projects the authenticated user has access to
    returns:
      id: integer
      uuid: string
      name: string
      api_token: string
    rest:
      method: GET
      url: https://us.posthog.com/api/projects/
      response:
        root: /results

  query:
    description: Run a HogQL query against the events table (recommended over events API)
    params:
      project_id: { type: string, required: true, description: "PostHog project ID" }
      hogql: { type: string, required: true, description: "HogQL query string" }
    returns:
      columns: array
      results: array
      types: array
    rest:
      method: POST
      url: '"https://us.posthog.com/api/projects/" + .params.project_id + "/query/"'
      body:
        query: { kind: '"HogQLQuery"', query: .params.hogql }

  get_event_definitions:
    description: List all event names defined in a project
    params:
      project_id: { type: string, required: true, description: "PostHog project ID" }
      limit: { type: integer }
    returns:
      id: string
      name: string
      volume_30_day: integer
      query_usage_30_day: integer
    rest:
      method: GET
      url: '"https://us.posthog.com/api/projects/" + .params.project_id + "/event_definitions/"'
      query:
        limit: '.params.limit | if . then tostring else null end'
      response:
        root: /results

  list_recordings:
    description: List session recordings for a project
    params:
      project_id: { type: string, required: true, description: "PostHog project ID" }
      limit: { type: integer }
      offset: { type: integer }
    returns:
      id: string
      distinct_id: string
      start_time: string
      end_time: string
      recording_duration: number
      active_seconds: number
      click_count: integer
      keypress_count: integer
      start_url: string
      viewed: boolean
    rest:
      method: GET
      url: '"https://us.posthog.com/api/projects/" + .params.project_id + "/session_recordings/"'
      query:
        limit: '.params.limit | if . then tostring else null end'
        offset: '.params.offset | if . then tostring else null end'
      response:
        root: /results
---

# PostHog

Product analytics — events, persons, and session recordings.

## Setup

1. Go to [Personal API Keys](https://us.posthog.com/settings/user-api-keys) in PostHog
2. Create a key with scopes: `person:read`, `query:read`, `session_recording:read`
3. Add the key to AgentOS credentials

## Finding your project ID

Call the `get_projects` utility — it returns all projects you have access to. The `id` field (numeric) is the project ID needed for all other operations.

## Operations

### person.list / person.search / person.get

Query PostHog persons. Search works by email or name. Persons map to the AgentOS `person` entity type.

### event.list / event.get

List recent events. The events API is deprecated by PostHog — for complex queries, use the `query` utility with HogQL instead.

**Note:** Without `after`/`before` params, event.list only returns the last 24 hours.

## Utilities

### query

The recommended way to query event data. Accepts a HogQL query string:

```
query({ project_id: "70599", hogql: "SELECT event, count() FROM events WHERE timestamp > now() - interval 7 day GROUP BY event ORDER BY count() DESC LIMIT 20" })
```

### get_event_definitions

Lists all event names with 30-day volume — useful for discovering what's being tracked.

### list_recordings

Session recording metadata. Returns start/end times, duration, clicks, keypresses, and start URL.

## Rate Limits

- Analytics endpoints: 240/minute, 1200/hour
- Query endpoint: 2400/hour

# PostHog

Product analytics — events, persons, and session recordings.

## Setup

1. Go to [Personal API Keys](https://us.posthog.com/settings/user-api-keys) in PostHog
2. Create a key with scopes: `person:read`, `query:read`, `session_recording:read`
3. Add the key to AgentOS credentials

## Finding your project ID

Call the `get_projects` utility — it returns all projects you have access to. The `id` field (numeric) is the project ID needed for all other operations.

## Usage

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

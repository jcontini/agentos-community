---
id: posthog
name: PostHog
description: Access PostHog analytics, user data, and session recordings
icon: icon.svg
display: browser

website: https://posthog.com
privacy_url: https://posthog.com/privacy
terms_url: https://posthog.com/terms

auth:
  type: api_key
  header: Authorization
  label: Personal API Key
  help_url: https://posthog.com/docs/api/personal-api-keys

instructions: |
  PostHog-specific notes:
  - Requires Personal API Key (not project API key)
  - Project ID required for all API calls
  - Supports US Cloud, EU Cloud, and self-hosted instances
  - Focus areas: user identification, session recordings, person management

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

transformers:
  # Person adapter - maps PostHog person data
  person:
    terminology: Person
    mapping:
      id: .id
      uuid: .uuid
      distinct_ids: .distinct_ids
      email: .properties.email
      name: .properties.name
      created_at: .created_at
      last_seen: .last_seen

  # Session recording adapter
  recording:
    terminology: Recording
    mapping:
      id: .id
      distinct_id: .distinct_id
      start_time: .start_time
      end_time: .end_time
      duration: .recording_duration
      click_count: .click_count
      keypress_count: .keypress_count
      start_url: .start_url

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  person.list:
    description: List persons (users) from PostHog
    returns: person[]
    params:
      limit: { type: integer, default: 50, description: "Number of results" }
      email: { type: string, description: "Filter by email address" }
      created_after: { type: string, description: "Filter by creation date (YYYY-MM-DD)" }
    # TODO: Implement using REST executor
    # GET /api/projects/{project_id}/persons/
    # Based on skills/posthog/posthog.sh

  person.get:
    description: Get a specific person by ID or UUID
    returns: person
    params:
      id: { type: string, required: true, description: "Person ID or UUID" }
    # TODO: Implement using REST executor
    # GET /api/projects/{project_id}/persons/{id}/

  person.search:
    description: Search for persons by email address
    returns: person[]
    params:
      email: { type: string, required: true, description: "Email address to search for" }
    # TODO: Implement using REST executor
    # GET /api/projects/{project_id}/persons/?search={email}

  recording.list:
    description: List session recordings
    returns: recording[]
    params:
      limit: { type: integer, default: 50, description: "Number of results" }
      person_id: { type: string, description: "Filter by person ID" }
      distinct_id: { type: string, description: "Filter by distinct_id" }
    # TODO: Implement using REST executor
    # GET /api/projects/{project_id}/session_recordings/

  recording.get:
    description: Get a specific session recording
    returns: recording
    params:
      id: { type: string, required: true, description: "Recording ID" }
    # TODO: Implement using REST executor
    # GET /api/projects/{project_id}/session_recordings/{id}/

---

# PostHog

Access PostHog analytics, user data, and session recordings.

## Focus Areas

- **User Identification** - Find users by email, track new users
- **Session Recordings** - Access replays and link them to identified users
- **Person Management** - Query person profiles, properties, and activity

## Authentication

Requires:
- **Personal API Key** (not project API key) - Get from Settings → Personal API Keys
- **Project ID** (numeric) - Required for all API calls
- **API Host** (optional) - Defaults to US Cloud (`https://us.posthog.com`)

## Key Endpoints

All endpoints require project ID in the path:
- **Persons**: `GET /api/projects/:project_id/persons/`
- **Person**: `GET /api/projects/:project_id/persons/:id/`
- **Recordings**: `GET /api/projects/:project_id/session_recordings/`
- **Recording**: `GET /api/projects/:project_id/session_recordings/:id/`

## Implementation Notes

- Based on `skills/posthog/posthog.sh` script
- Use REST executor with Bearer token authentication
- Project ID must be included in URL path (not query param)
- API responses are paginated - use `next` field for pagination
- Session recordings API doesn't reliably support filtering by person_id UUIDs - may need client-side filtering

## Examples

```bash
# List recent users
POST /api/adapters/posthog/person.list
{"limit": 50}
# → [{id: 12345, email: "user@example.com", ...}, ...]

# Find user by email
POST /api/adapters/posthog/person.search
{"email": "user@example.com"}
# → [{id: 12345, email: "user@example.com", ...}]

# Get user's session recordings
POST /api/adapters/posthog/recording.list
{"distinct_id": "user@example.com", "limit": 10}
# → [{id: "...", start_time: "...", duration: 900, ...}, ...]
```

## Use Cases

- Debug your own product usage
- Review user sessions to understand behavior
- Track new users and identify them by email
- Analyze user activity patterns

## References

- Based on `skills/posthog/README.md` and `skills/posthog/posthog.sh`
- PostHog API docs: https://posthog.com/docs/api

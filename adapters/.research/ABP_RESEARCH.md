# ABP (Austin Bouldering Project) Adapter Research

## Architecture Overview

### The Stack

```
Austin Bouldering Project (Gym)
         ↓
Approach.app (Frontend Portal)
         ↓
Tilefive API (Backend Infrastructure)
```

### Companies & Relationships

**Tile Five** (Parent Company)
- Kansas City-based company
- Raised $1.5M seed funding in 2021
- Owns and operates Approach platform
- Provides cloud infrastructure (`widgets.api.prod.tilefive.com`)

**Approach.app** (Product/Platform)
- Climbing gym management software (SaaS)
- Handles: POS, CRM, memberships, scheduling, waivers, inventory
- Web-based portal for gyms and customers
- Used by 200+ climbing gyms worldwide
- Multi-location support built-in

**Austin Bouldering Project** (Customer)
- Uses Approach.app for gym management
- Portal URL: `boulderingproject.portal.approach.app`
- Multiple locations (Springdale = locationId: 6)

---

## API Analysis

### Current Implementation

From the existing script:

```bash
URL="https://widgets.api.prod.tilefive.com/cal"
Headers:
  - Authorization: boulderingproject
  - X-Api-Key: OQ2z4Q3jSU1BW3y9dyfEW5FlEFu1ozIj7jE27qjy
  - Origin: https://boulderingproject.portal.approach.app
  - Referer: https://boulderingproject.portal.approach.app/
```

### API Testing Results

✅ **API requires valid credentials**
- Invalid auth → `403 Forbidden`
- Valid credentials work

❌ **Current API key is gym-specific**
- `Authorization: boulderingproject` = gym identifier
- `X-Api-Key` = specific to Bouldering Project
- Not a generic Approach.app API

---

## Adapter Design Options

### Option 1: Generic Approach.app Adapter (Ideal)

**Pros:**
- Works for ANY gym using Approach.app
- Users configure their gym's portal subdomain
- Proper authentication flow
- Scalable to other gyms

**Cons:**
- Need to reverse-engineer Approach.app auth
- May require user login credentials
- Unknown if Tilefive provides public API access

**Configuration:**
```yaml
auth:
  type: oauth2  # or api_key
  credentials:
    - name: gym_subdomain
      description: Your gym's Approach portal subdomain (e.g., "boulderingproject")
    - name: api_key
      description: Your Approach API key
    - name: location_id
      description: Location ID for multi-gym setups
```

### Option 2: ABP-Specific Adapter (Pragmatic)

**Pros:**
- Works immediately
- No auth complexity
- Specific to your use case

**Cons:**
- Only works for Austin Bouldering Project
- Hardcoded credentials
- Not reusable by others

**Configuration:**
```yaml
auth:
  type: none  # Hardcoded in adapter
```

### Option 3: Hybrid Approach (Recommended)

**Pros:**
- Start with ABP-specific
- Design for future genericization
- Works now, scales later

**Cons:**
- Some duplicate work when genericizing

**Implementation:**
1. Create `adapters/abp/` with hardcoded credentials
2. Add `instructions:` noting it's ABP-specific
3. Design entity mapping to work for any gym
4. Later: Extract to `adapters/approach/` when auth is figured out

---

## Recommended Adapter Structure

### Adapter: `adapters/abp/`

**Entity:** `event` (fitness classes are events)

**Operations:**
- `event.list` - List upcoming classes
- `event.get` - Get class details
- `event.create` - Book a class (creates booking)
- `event.delete` - Cancel a booking

**Configuration:**

```yaml
id: abp
name: Austin Bouldering Project
description: Class schedules and booking for Austin Bouldering Project Springdale
icon: icon.svg
color: "#FF6B35"
tags: [fitness, climbing, classes, austin]

website: https://austinboulderingproject.com
privacy_url: https://austinboulderingproject.com/privacy

# Hardcoded for now, but designed to be extractable
auth:
  type: custom
  instructions: |
    This adapter is currently hardcoded for Austin Bouldering Project.
    To use with other Approach.app gyms, you'll need to:
    1. Find your gym's portal subdomain (e.g., yourg gym.portal.approach.app)
    2. Extract the API key from browser network requests
    3. Find your location ID from the schedule URL

adapters:
  event:
    terminology: Class
    mapping:
      id: .id
      title: .name
      description: .event.activitys[0].name
      start_time: .startDT | fromdateiso8601
      end_time: .endDT | fromdateiso8601
      location:
        name: '"Austin Bouldering Project - Springdale"'
        id: '"6"'
      category: .event.activitys[0].name
      url: '"https://boulderingproject.portal.approach.app/schedule?locationIds=6&date=" + .occurrenceDate'
      metadata:
        activity_id: .event.activitys[0].id
        occurrence_date: .occurrenceDate

operations:
  event.list:
    description: List upcoming fitness classes at ABP Springdale
    returns: event[]
    web_url: '"https://boulderingproject.portal.approach.app/schedule?locationIds=6"'
    rest:
      method: GET
      url: https://widgets.api.prod.tilefive.com/cal
      query:
        startDT: '(.params.start_date // now | todate)'
        endDT: '(.params.end_date // (now + 604800) | todate)'  # Default 7 days
        locationId: '"6"'
        page: '"1"'
        pageSize: '"50"'
      headers:
        Authorization: '"boulderingproject"'
        X-Api-Key: '"OQ2z4Q3jSU1BW3y9dyfEW5FlEFu1ozIj7jE27qjy"'
        Origin: '"https://boulderingproject.portal.approach.app"'
        Referer: '"https://boulderingproject.portal.approach.app/"'
      response:
        root: /bookings
        # Filter out youth programs (1), camps (7), group booking (12), 
        # affinity groups (14), personal coaching (16)
        transform: |
          map(select(.event.activitys[0].id as $id | 
            $id != null and 
            ([$id] | inside([1,7,12,14,16]) | not)))

  event.get:
    description: Get details for a specific class
    returns: event
    rest:
      method: GET
      url: '"https://widgets.api.prod.tilefive.com/bookings/" + (.params.id | tostring)'
      headers:
        Authorization: '"boulderingproject"'
        X-Api-Key: '"OQ2z4Q3jSU1BW3y9dyfEW5FlEFu1ozIj7jE27qjy"'

  event.create:
    description: Book a class (requires booking ID from event.list)
    returns: void
    rest:
      method: POST
      url: '"https://widgets.api.prod.tilefive.com/bookings/" + (.params.id | tostring)'
      headers:
        Authorization: '"boulderingproject"'
        X-Api-Key: '"OQ2z4Q3jSU1BW3y9dyfEW5FlEFu1ozIj7jE27qjy"'
        Content-Type: '"application/json"'
      body:
        # Body structure TBD - need to test booking flow

  event.delete:
    description: Cancel a class booking
    returns: void
    rest:
      method: DELETE
      url: '"https://widgets.api.prod.tilefive.com/bookings/" + (.params.id | tostring)'
      headers:
        Authorization: '"boulderingproject"'
        X-Api-Key: '"OQ2z4Q3jSU1BW3y9dyfEW5FlEFu1ozIj7jE27qjy"'

instructions: |
  This adapter is specific to Austin Bouldering Project (Springdale location).
  
  Classes are filtered to exclude:
  - Youth Programs
  - Camps
  - Group Bookings
  - Affinity Groups
  - Personal Coaching
  
  Times are returned in UTC and should be converted to local timezone for display.
  
  To book a class:
  1. Call event.list to get available classes
  2. Use the class ID with event.create to book
  3. Booking confirmation will be sent to user's email on file
```

---

## Migration Path

### Phase 1: ABP-Specific (Now)
1. Create `adapters/abp/` with hardcoded credentials
2. Test with your actual usage
3. Get it working end-to-end

### Phase 2: Research Approach.app Auth (Later)
1. Contact Tilefive/Approach.app for API access
2. Reverse-engineer auth flow from browser
3. Document findings

### Phase 3: Genericize (Future)
1. Create `adapters/approach/` 
2. Add proper auth configuration
3. Support multiple gyms/locations
4. Deprecate ABP-specific adapter (or keep as example)

---

## Next Steps

1. **Create adapter structure**
   ```bash
   mkdir -p adapters/abp/tests
   touch adapters/abp/readme.md
   touch adapters/abp/icon.svg
   ```

2. **Test booking flow**
   - Need to capture actual booking POST request
   - Test cancel flow
   - Document request/response shapes

3. **Create tests**
   - Test event.list with date ranges
   - Test filtering logic
   - Mock booking/cancel operations

4. **Icon design**
   - Use ABP brand colors
   - Rock climbing/bouldering theme

---

## Open Questions

1. **Booking authentication**: Does booking require user credentials beyond the API key?
2. **User identification**: How does the API know which user is booking?
3. **Booking limits**: Are there rate limits or booking restrictions?
4. **Multi-location**: Can one API key access multiple ABP locations?
5. **Approach.app API**: Does Tilefive offer official API access to gym customers?

---

## Resources

- Approach.app: https://www.approach.app/
- ABP Portal: https://boulderingproject.portal.approach.app/
- Tilefive API: https://widgets.api.prod.tilefive.com/
- Funding announcement: https://www.startlandnews.com/2021/10/tile-five-approach-climbing-crux/

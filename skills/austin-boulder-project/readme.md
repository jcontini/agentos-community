---
id: austin-boulder-project
name: Austin Boulder Project
description: Class schedules and bookings for the Austin Bouldering Project gym
icon: icon.svg
color: "#1e3a2f"
website: https://boulderingproject.portal.approach.app

auth:
  header:
    Authorization: .auth.key
  label: "ABP credentials — enter as email:password"
  help_url: https://boulderingproject.portal.approach.app/login
  optional: true

adapters:
  class:
    id: '.id | tostring'
    name: .name
    text: .text
    datePublished: .startDT
    url: '"https://boulderingproject.portal.approach.app/schedule"'
    data.endDT: .endDT
    data.status: .status
    data.ticketsRemaining: .ticketsRemaining
    data.capacity: .capacity
    data.locationName: .locationName
    data.locationId: .locationId
    data.activityName: .activityName
    data.isFull: .isFull

operations:
  get_schedule:
    description: Get today's class schedule at Austin Bouldering Project — no login needed
    auth: none
    returns: class[]
    params:
      date:
        type: string
        required: false
        description: "Date in YYYY-MM-DD format (default: today in Austin time)"
      location_id:
        type: integer
        required: false
        default: 6
        description: "Location ID: 6 = Austin Springdale, 5 = Austin Westgate"
      activity_ids:
        type: string
        required: false
        description: "Comma-separated activity IDs (default: 4,5,6 = Climbing, Yoga, Fitness)"
    command:
      binary: python3
      args:
        - ./abp.py
        - get_schedule
      stdin: .params | tojson
      working_dir: .
      timeout: 30
    test:
      mode: read
      fixtures: {}

  book_class:
    description: Book a class at Austin Bouldering Project (requires stored credentials)
    returns:
      ok: boolean
      message: string
    params:
      booking_instance_id:
        type: integer
        required: true
        description: "Class instance ID from get_schedule (the id field)"
      num_guests:
        type: integer
        required: false
        default: 0
        description: "Number of additional guests to bring"
    command:
      binary: python3
      args:
        - ./abp.py
        - book_class
      stdin: '{ "credentials": .auth.key, "params": .params }'
      working_dir: .
      timeout: 30
    test:
      mode: write

  cancel_booking:
    description: Cancel a class reservation at Austin Bouldering Project
    returns:
      ok: boolean
      message: string
    params:
      booking_instance_id:
        type: integer
        required: true
        description: "Class instance ID"
      reservation_id:
        type: integer
        required: true
        description: "Reservation ID returned when the class was booked"
    command:
      binary: python3
      args:
        - ./abp.py
        - cancel_booking
      stdin: '{ "credentials": .auth.key, "params": .params }'
      working_dir: .
      timeout: 30
    test:
      mode: write

  get_my_memberships:
    description: List active memberships for the logged-in ABP account
    returns: array
    params: {}
    command:
      binary: python3
      args:
        - ./abp.py
        - get_my_memberships
      stdin: '{ "credentials": .auth.key }'
      working_dir: .
      timeout: 30
    test:
      mode: read

  get_my_passes:
    description: List active class passes for the logged-in ABP account
    returns: array
    params: {}
    command:
      binary: python3
      args:
        - ./abp.py
        - get_my_passes
      stdin: '{ "credentials": .auth.key }'
      working_dir: .
      timeout: 30
    test:
      mode: read
---

# Austin Boulder Project

Class schedules and booking for the [Austin Bouldering Project](https://austinboulderingproject.com) — Texas's premier bouldering and fitness gym with locations in Springdale and Westgate.

Built on the **Tilefive** platform (`approach.app`), authenticated via **AWS Cognito**.

## Setup

No credentials needed to view the schedule — `get_schedule` is fully public.

To book classes, add your ABP portal credentials in agentOS skill settings:

- **Format:** `your@email.com:yourpassword`
- **Where to get them:** [boulderingproject.portal.approach.app/login](https://boulderingproject.portal.approach.app/login)

## Locations

| Name | ID |
|---|---|
| Austin Springdale | `6` (default) |
| Austin Westgate | `5` |

## Activity IDs

| Activity | ID |
|---|---|
| Climbing Classes | `4` |
| Yoga | `5` |
| Fitness | `6` |

## Examples

```js
// Today's classes at Springdale (default)
run({ skill: "austin-boulder-project", tool: "get_schedule" })

// Tomorrow's yoga classes at Westgate
run({ skill: "austin-boulder-project", tool: "get_schedule", params: {
  date: "2026-03-18",
  location_id: 5,
  activity_ids: "5"
}})

// Book a class (use id from get_schedule)
run({ skill: "austin-boulder-project", tool: "book_class", params: {
  booking_instance_id: 826115
}})
```

## Technical Notes

See `requirements.md` for full reverse-engineering notes on the Tilefive API.

Key discoveries:
- `Authorization` header on the widgets API is the namespace string (`boulderingproject`), not a JWT
- `httpx` with `http2=True` is required — CloudFront WAF uses JA4 TLS fingerprinting that blocks urllib/requests
- Cognito auth uses `IdToken` (not `AccessToken`) for portal API calls

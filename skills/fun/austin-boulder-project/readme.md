---
id: austin-boulder-project
name: Austin Boulder Project
description: Class schedules and bookings for the Austin Bouldering Project gym
color: "#1e3a2f"
website: "https://boulderingproject.portal.approach.app"

connections:
  api:
    auth:
      type: api_key
      header:
        Authorization: .auth.key
    label: ABP credentials — enter as email:password
    help_url: https://boulderingproject.portal.approach.app/login
    optional: true
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

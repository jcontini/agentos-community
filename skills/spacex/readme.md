---
id: spacex
name: SpaceX
description: SpaceX launch data — upcoming, past, and individual launch details
color: "#005288"
website: https://www.spacex.com

test:
  list_upcoming: {}
  list_past: { params: { limit: 5 } }
  get_launch: { params: { id: "5eb87d46ffd86e000604b388" } }
---

# SpaceX

Launch data from the [SpaceX API](https://github.com/r-spacex/SpaceX-API). Lists upcoming and past launches, with details including mission name, date, rocket, launchpad, webcast link, success status, and more.

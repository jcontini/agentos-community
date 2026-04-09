"""SpaceX — launch data from the public SpaceX API."""

from agentos import http, returns

BASE = "https://api.spacexdata.com/v4/launches"


def _format_launch(launch: dict) -> dict:
    """Convert a raw API launch object to an event shape."""
    links = launch.get("links") or {}
    patch = links.get("patch") or {}
    cores = launch.get("cores") or []

    landing_outcomes = []
    reused_boosters = 0
    for core in cores:
        if core.get("landing_success") is True:
            landing_outcomes.append("success")
        elif core.get("landing_success") is False:
            landing_outcomes.append("failure")
        if core.get("reused"):
            reused_boosters += 1

    webcast = links.get("webcast")
    article = links.get("article")
    wikipedia = links.get("wikipedia")

    return {
        "id": launch["id"],
        "name": launch.get("name", ""),
        "url": wikipedia or webcast or f"https://www.spacex.com",
        "image": patch.get("small"),
        "startDate": launch.get("date_utc"),
        "status": "success" if launch.get("success") is True
                  else "failure" if launch.get("success") is False
                  else "upcoming" if launch.get("upcoming")
                  else "unknown",
        "eventType": "launch",
        "content": launch.get("details"),
        "flightNumber": launch.get("flight_number"),
        "rocketId": launch.get("rocket"),
        "launchpadId": launch.get("launchpad"),
        "webcastUrl": webcast,
        "articleUrl": article,
        "wikipediaUrl": wikipedia,
        "patchImage": patch.get("large"),
        "reusedBoosters": reused_boosters,
        "landingOutcomes": landing_outcomes if landing_outcomes else None,
        "crewIds": launch.get("crew") or None,
    }


@returns("event[]")
async def list_upcoming(limit: int = 10, **params) -> list[dict]:
    """List upcoming SpaceX launches.

    Args:
        limit: Maximum number of launches to return (default 10)
    """
    resp = await http.get(f"{BASE}/upcoming")
    launches = resp["json"]
    return [_format_launch(l) for l in launches[:limit]]


@returns("event[]")
async def list_past(limit: int = 10, **params) -> list[dict]:
    """List recent past SpaceX launches, newest first.

    Args:
        limit: Maximum number of launches to return (default 10)
    """
    resp = await http.get(f"{BASE}/past")
    launches = resp["json"]
    launches.reverse()
    return [_format_launch(l) for l in launches[:limit]]


@returns("event")
async def get_launch(id: str, **params) -> dict:
    """Get details for a specific SpaceX launch by ID.

    Args:
        id: The launch ID (e.g. 5eb87d46ffd86e000604b388)
    """
    resp = await http.get(f"{BASE}/{id}")
    return _format_launch(resp["json"])

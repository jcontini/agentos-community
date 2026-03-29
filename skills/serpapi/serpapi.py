"""SerpAPI — Google Flights search via the SerpAPI proxy."""

from agentos import http

SEARCH_URL = "https://serpapi.com/search"


def _auth_params(params: dict) -> dict:
    key = params.get("auth", {}).get("key", "")
    return {"api_key": key} if key else {}


def _map_offer(r: dict) -> dict:
    """Map a SerpAPI flight result to shape-native offer fields."""
    flights = r.get("flights") or []
    layovers = r.get("layovers") or []
    first = flights[0] if flights else {}
    last = flights[-1] if flights else {}

    dep = (first.get("departure_airport") or {})
    arr = (last.get("arrival_airport") or {})
    dep_id = dep.get("id", "")
    arr_id = arr.get("id", "")
    dep_time = dep.get("time", "")
    dep_date = dep_time.split(" ")[0] if dep_time else ""
    flight_num = first.get("flight_number", "").replace(" ", "-")
    price = r.get("price", 0)
    airline = first.get("airline") or "Unknown"
    stops = len(flights) - 1
    stop_str = "nonstop" if stops == 0 else f"+{stops} stop{'s' if stops > 1 else ''}"

    duration = r.get("total_duration") or 0
    hrs, mins = duration // 60, duration % 60

    lines = [
        f"{dep_id} → {arr_id}",
        f"Price: ${price} {r.get('type', '')}".rstrip(),
        f"Duration: {hrs}h {mins}m",
        f"Airline: {airline}",
        f"Flight: {first.get('flight_number') or 'Unknown'}",
        f"Class: {first.get('travel_class') or 'Economy'}",
        f"Aircraft: {first.get('airplane') or 'Unknown'}",
    ]
    if stops > 0:
        layover_str = ", ".join(
            f"{lv.get('name', '')} ({(lv.get('duration') or 0) // 60}h {(lv.get('duration') or 0) % 60}m)"
            for lv in layovers
        )
        lines.append(f"Stops: {stops} ({layover_str})")
    else:
        lines.append("Nonstop")
    lines.append(f"Depart: {dep_time} from {dep.get('name', '')}")
    lines.append(f"Arrive: {arr.get('time', '')} at {arr.get('name', '')}")
    carbon = r.get("carbon_emissions") or {}
    if carbon.get("this_flight"):
        lines.append(f"Carbon: {carbon['this_flight'] // 1000} kg CO₂")

    return {
        "id": f"{dep_id}-{arr_id}-{dep_date}-{flight_num}",
        "name": f"{dep_id} → {arr_id} · {airline} {stop_str} · ${price}",
        "price": price,
        "currency": "USD",
        "offer_type": "flight",
        "trip_type": r.get("type"),
        "total_duration": r.get("total_duration"),
        "flights": flights,
        "layovers": layovers,
        "carbon_emissions": r.get("carbon_emissions"),
        "airline_logo": r.get("airline_logo"),
        "extensions": r.get("extensions"),
        "departure_token": r.get("departure_token"),
        "booking_token": r.get("booking_token"),
        "content": "\n".join(lines),
    }


def _flight_get(query: dict, **params) -> dict:
    q = {**_auth_params(params), **{k: v for k, v in query.items() if v is not None}}
    resp = http.get(SEARCH_URL, params=q, profile="api")
    return resp["json"]


def search_offers(*, departure_id: str, arrival_id: str, outbound_date: str, return_date: str = None, type: int = 1, travel_class: int = 1, adults: int = 1, children: int = None, stops: int = None, max_price: int = None, sort_by: int = None, include_airlines: str = None, exclude_airlines: str = None, currency: str = "USD", hl: str = "en", gl: str = None, deep_search: bool = None, **params) -> list[dict]:
    q: dict = {
        "engine": "google_flights",
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": outbound_date,
        "return_date": return_date,
        "type": str(type) if type else None,
        "travel_class": str(travel_class) if travel_class else None,
        "adults": str(adults) if adults else None,
        "children": str(children) if children is not None else None,
        "stops": str(stops) if stops is not None else None,
        "max_price": str(max_price) if max_price is not None else None,
        "sort_by": str(sort_by) if sort_by is not None else None,
        "include_airlines": include_airlines,
        "exclude_airlines": exclude_airlines,
        "currency": currency,
        "hl": hl,
        "gl": gl,
        "deep_search": str(deep_search).lower() if deep_search is not None else None,
    }
    data = _flight_get(q, **params)
    return [_map_offer(r) for r in (data.get("other_flights") or [])]


def list_offers(*, departure_id: str, arrival_id: str, outbound_date: str, return_date: str = None, type: int = 1, travel_class: int = 1, currency: str = "USD", hl: str = "en", **params) -> list[dict]:
    q: dict = {
        "engine": "google_flights",
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": outbound_date,
        "return_date": return_date,
        "type": str(type),
        "travel_class": str(travel_class),
        "currency": currency,
        "hl": hl,
    }
    data = _flight_get(q, **params)
    return [_map_offer(r) for r in (data.get("best_flights") or [])]


def get_offer(*, departure_token: str, currency: str = "USD", hl: str = "en", **params) -> list[dict]:
    q = {
        "engine": "google_flights",
        "departure_token": departure_token,
        "currency": currency,
        "hl": hl,
    }
    data = _flight_get(q, **params)
    return [_map_offer(r) for r in (data.get("other_flights") or [])]


def get_booking_options(*, booking_token: str, currency: str = "USD", hl: str = "en", **params) -> dict:
    q = {
        "engine": "google_flights",
        "booking_token": booking_token,
        "currency": currency,
        "hl": hl,
    }
    data = _flight_get(q, **params)
    return {
        "booking_options": data.get("booking_options", []),
        "price": data.get("price"),
    }


def get_price_insights(*, departure_id: str, arrival_id: str, outbound_date: str, return_date: str = None, type: int = 1, currency: str = "USD", **params) -> dict:
    q: dict = {
        "engine": "google_flights",
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": outbound_date,
        "return_date": return_date,
        "type": str(type),
        "currency": currency,
    }
    data = _flight_get(q, **params)
    insights = data.get("price_insights") or {}
    return insights

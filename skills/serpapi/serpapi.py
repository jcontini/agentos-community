"""SerpAPI — Google Flights search via the SerpAPI proxy."""

from agentos import http, connection, provides, returns, flight_search

SEARCH_URL = "https://serpapi.com/search"


def _auth_params(params: dict) -> dict:
    key = params.get("auth", {}).get("key", "")
    return {"apiKey": key} if key else {}


def _map_offer(r: dict) -> dict:
    """Map a SerpAPI flight result to an offer with trip→leg[] shape."""
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

    # Build legs from SerpAPI flights[] array
    legs = []
    for i, f in enumerate(flights):
        f_dep = f.get("departure_airport") or {}
        f_arr = f.get("arrival_airport") or {}
        layover_min = layovers[i].get("duration") if i < len(layovers) else None

        legs.append({
            "leg": {
                "sequence": i + 1,
                "departureTime": f_dep.get("time"),
                "arrivalTime": f_arr.get("time"),
                "durationMinutes": f.get("duration"),
                "flightNumber": f.get("flight_number"),
                "cabinClass": f.get("travel_class"),
                "vehicleType": f.get("airplane"),
                "layoverMinutes": layover_min,
                "carbonEmissions": f.get("extensions"),
                "origin": {
                    "name": f_dep.get("name"),
                    "id": f_dep.get("id"),
                    "featureType": "poi",
                },
                "destination": {
                    "name": f_arr.get("name"),
                    "id": f_arr.get("id"),
                    "featureType": "poi",
                },
                "carrier": {"name": f.get("airline", "")} if f.get("airline") else None,
            }
        })

    # Build trip (one direction of travel)
    trip = {
        "tripType": "flight",
        "departureTime": dep.get("time"),
        "arrivalTime": (last.get("arrival_airport") or {}).get("time"),
        "duration": f"{hrs}h {mins}m",
        "durationMinutes": duration,
        "stops": stops,
        "cabinClass": first.get("travel_class"),
        "carbonEmissions": r.get("carbon_emissions"),
        "origin": {"name": dep.get("name"), "id": dep_id, "featureType": "poi"},
        "destination": {"name": arr.get("name"), "id": arr_id, "featureType": "poi"},
        "carrier": {"name": airline},
        "legs": legs if legs else None,
    }

    # Summary content
    lines = [
        f"{dep_id} → {arr_id}",
        f"Price: ${price} {r.get('type', '')}".rstrip(),
        f"Duration: {hrs}h {mins}m",
        f"Airline: {airline}",
        f"Flight: {first.get('flight_number') or 'Unknown'}",
        f"Class: {first.get('travel_class') or 'Economy'}",
    ]
    if stops > 0:
        layover_str = ", ".join(
            f"{lv.get('name', '')} ({(lv.get('duration') or 0) // 60}h {(lv.get('duration') or 0) % 60}m)"
            for lv in layovers
        )
        lines.append(f"Stops: {stops} ({layover_str})")
    else:
        lines.append("Nonstop")

    return {
        "id": f"{dep_id}-{arr_id}-{dep_date}-{flight_num}",
        "name": f"{dep_id} → {arr_id} · {airline} {stop_str} · ${price}",
        "price": price,
        "currency": "USD",
        "offerType": "flight",
        "image": r.get("airline_logo"),
        "departureToken": r.get("departure_token"),
        "bookingToken": r.get("booking_token"),
        "content": "\n".join(lines),
        # Typed reference: offer → trip
        "trips": [trip],
    }


def _flight_get(query: dict, **params) -> dict:
    q = {**_auth_params(params), **{k: v for k, v in query.items() if v is not None}}
    resp = http.get(SEARCH_URL, params=q, **http.headers(accept="json"))
    return resp["json"]


@returns("offer[]")
@provides(flight_search)
@connection("api")
def search_offers(*, departure_id: str, arrival_id: str, outbound_date: str, return_date: str = None, type: int = 1, travel_class: int = 1, adults: int = 1, children: int = None, stops: int = None, max_price: int = None, sort_by: int = None, include_airlines: str = None, exclude_airlines: str = None, currency: str = "USD", hl: str = "en", gl: str = None, deep_search: bool = None, **params) -> list[dict]:
    """Search Google Flights for flight offers between airports

        Args:
            departure_id: Departure airport IATA code(s), comma-separated (e.g. 'AUS' or 'CDG,ORY')
            arrival_id: Arrival airport IATA code(s), comma-separated (e.g. 'JFK' or 'LHR,LGW')
            outbound_date: Outbound date (YYYY-MM-DD)
            return_date: Return date (YYYY-MM-DD). Required for round trip.
            type: Flight type: 1=Round trip (default), 2=One way, 3=Multi-city
            travel_class: 1=Economy (default), 2=Premium economy, 3=Business, 4=First
            adults: Number of adult passengers
            children: Number of children
            stops: 0=Any (default), 1=Nonstop, 2=1 stop or fewer, 3=2 stops or fewer
            max_price: Maximum ticket price in USD
            sort_by: 1=Top flights (default), 2=Price, 3=Departure, 4=Arrival, 5=Duration, 6=Emissions
            include_airlines: Airline IATA codes to include, comma-separated (e.g. 'UA,AA')
            exclude_airlines: Airline IATA codes to exclude, comma-separated
            currency: Currency code (ISO 4217)
            hl: Language code
            gl: Country code for localization (e.g. 'us', 'uk')
            deep_search: true for browser-identical results (slower)
        """
    q: dict = {
        "engine": "google_flights",
        "departureId": departure_id,
        "arrivalId": arrival_id,
        "outboundDate": outbound_date,
        "returnDate": return_date,
        "type": str(type) if type else None,
        "travelClass": str(travel_class) if travel_class else None,
        "adults": str(adults) if adults else None,
        "children": str(children) if children is not None else None,
        "stops": str(stops) if stops is not None else None,
        "maxPrice": str(max_price) if max_price is not None else None,
        "sortBy": str(sort_by) if sort_by is not None else None,
        "includeAirlines": include_airlines,
        "excludeAirlines": exclude_airlines,
        "currency": currency,
        "hl": hl,
        "gl": gl,
        "deepSearch": str(deep_search).lower() if deep_search is not None else None,
    }
    data = _flight_get(q, **params)
    return [_map_offer(r) for r in (data.get("other_flights") or [])]


@returns("offer[]")
@connection("api")
def list_offers(*, departure_id: str, arrival_id: str, outbound_date: str, return_date: str = None, type: int = 1, travel_class: int = 1, currency: str = "USD", hl: str = "en", **params) -> list[dict]:
    """Get the best/recommended flight offers (may not always be available)

        Args:
            departure_id: Departure airport IATA code(s)
            arrival_id: Arrival airport IATA code(s)
            outbound_date: Outbound date (YYYY-MM-DD)
            return_date: Return date (YYYY-MM-DD)
            type: 1=Round trip, 2=One way
            travel_class: 1=Economy, 2=Premium economy, 3=Business, 4=First
            currency: Currency code
            hl: Language code
        """
    q: dict = {
        "engine": "google_flights",
        "departureId": departure_id,
        "arrivalId": arrival_id,
        "outboundDate": outbound_date,
        "returnDate": return_date,
        "type": str(type),
        "travelClass": str(travel_class),
        "currency": currency,
        "hl": hl,
    }
    data = _flight_get(q, **params)
    return [_map_offer(r) for r in (data.get("best_flights") or [])]


@returns("offer[]")
@connection("api")
def get_offer(*, departure_token: str, currency: str = "USD", hl: str = "en", **params) -> list[dict]:
    """Get return flight offers using a departure token from a previous search

        Args:
            departure_token: Departure token from a flight offer search result
            currency: Currency code
            hl: Language code
        """
    q = {
        "engine": "google_flights",
        "departureToken": departure_token,
        "currency": currency,
        "hl": hl,
    }
    data = _flight_get(q, **params)
    return [_map_offer(r) for r in (data.get("other_flights") or [])]


@returns({"bookingOptions": "array", "price": "number"})
@connection("api")
def get_booking_options(*, booking_token: str, currency: str = "USD", hl: str = "en", **params) -> dict:
    """Get booking options for selected flights using a booking token

        Args:
            booking_token: Booking token from a flight offer result
            currency: Currency code
            hl: Language code
        """
    q = {
        "engine": "google_flights",
        "bookingToken": booking_token,
        "currency": currency,
        "hl": hl,
    }
    data = _flight_get(q, **params)
    return {
        "bookingOptions": data.get("booking_options", []),
        "price": data.get("price"),
    }


@returns({"lowestPrice": "number", "priceLevel": "string", "typicalPriceRange": "array", "priceHistory": "array"})
@connection("api")
def get_price_insights(*, departure_id: str, arrival_id: str, outbound_date: str, return_date: str = None, type: int = 1, currency: str = "USD", **params) -> dict:
    """Get price insights for a flight route (typical price range, price level, history)

        Args:
            departure_id: Departure airport IATA code
            arrival_id: Arrival airport IATA code
            outbound_date: Outbound date (YYYY-MM-DD)
            return_date: Return date (YYYY-MM-DD)
            type: 1=Round trip, 2=One way
            currency: Currency code
        """
    q: dict = {
        "engine": "google_flights",
        "departureId": departure_id,
        "arrivalId": arrival_id,
        "outboundDate": outbound_date,
        "returnDate": return_date,
        "type": str(type),
        "currency": currency,
    }
    data = _flight_get(q, **params)
    insights = data.get("price_insights") or {}
    return insights

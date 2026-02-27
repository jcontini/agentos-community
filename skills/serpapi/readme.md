---
id: serpapi
name: SerpAPI
description: Google search results API — flights, hotels, web search, and more
icon: icon.svg
color: "#0FA47F"

website: https://serpapi.com
privacy_url: https://serpapi.com/privacy
terms_url: https://serpapi.com/terms-and-conditions

auth:
  query:
    api_key: "{token}"
  label: API Key
  help_url: https://serpapi.com/manage-api-key

connects_to: serpapi

seed:
  - id: serpapi
    types: [software]
    name: SerpAPI
    data:
      software_type: api
      url: https://serpapi.com
      launched: "2018"
      platforms: [web]
      pricing: freemium
    relationships:
      - role: offered_by
        to: serpapi-llc

  - id: serpapi-llc
    types: [organization]
    name: SerpAPI LLC
    data:
      type: company
      url: https://serpapi.com

instructions: |
  SerpAPI scrapes Google search results and returns structured JSON. Currently
  supports Google Flights for flight search. More engines (hotels, web, maps)
  can be added later — they all use the same API key and base URL.

  ## Important: Offers, Not Flights

  SerpAPI returns **offers** — priced itineraries, not raw flight schedules.
  Each result is an offer containing one or more flight segments bundled with
  a price, cabin class, and booking conditions. The same physical flights
  appear in many offers at different prices.

  The offer entity has price, currency, and flight details in its data bag.
  Individual flight segments within data.flights contain departure/arrival
  airports, times, airline, aircraft, and duration.

  ## Google Flights

  Search using IATA airport codes (3-letter, e.g. "AUS", "JFK", "LHR").

  **Flight types:**
  - Round trip (default): requires outbound_date + return_date
  - One way: requires outbound_date only
  - Multi-city: use multi_city_json parameter

  **Travel classes:** 1=Economy (default), 2=Premium economy, 3=Business, 4=First

  **Stops:** 0=Any (default), 1=Nonstop only, 2=1 stop or fewer, 3=2 stops or fewer

  **Sorting:** 1=Top flights (default), 2=Price, 3=Departure, 4=Arrival, 5=Duration, 6=Emissions

  **Round trip flow:** First search returns outbound offers with departure_tokens.
  To get return flights, call offer.get with the departure_token from your chosen
  outbound offer.

  **Booking flow:** Once you have both outbound and return selected, call
  get_booking_options with the booking_token to see booking links and prices.

  **Tips:**
  - Dates must be YYYY-MM-DD format and in the future
  - Airport codes are case-insensitive but conventionally uppercase
  - Multiple departure/arrival airports can be comma-separated: "CDG,ORY"
  - deep_search=true gives browser-identical results but slower response
  - Free tier: 100 searches/month

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

transformers:
  offer:
    terminology: Flight Offer
    mapping:
      id: >
        ((.flights[0].departure_airport.id) + "-" +
         (.flights[-1].arrival_airport.id) + "-" +
         (.flights[0].departure_airport.time | split(" ") | .[0]) + "-" +
         (.flights[0].flight_number | gsub(" "; "-")))
      name: >
        ((.flights[0].departure_airport.id) + " → " +
         (.flights[-1].arrival_airport.id) + " · " +
         (.flights[0].airline // "Unknown") +
         (if (.flights | length) > 1 then " +" + ((.flights | length) - 1 | tostring) + " stop" + (if ((.flights | length) - 1) > 1 then "s" else "" end) else " nonstop" end) +
         " · $" + (.price | tostring))
      price: .price
      currency: '"USD"'
      offer_type: '"flight"'
      data.trip_type: .type
      data.total_duration: .total_duration
      data.flights: .flights
      data.layovers: .layovers
      data.carbon_emissions: .carbon_emissions
      data.airline_logo: .airline_logo
      data.extensions: .extensions
      data.departure_token: .departure_token
      data.booking_token: .booking_token
      content: >
        ((.flights[0].departure_airport.id) + " → " +
         (.flights[-1].arrival_airport.id) + "\n" +
         "Price: $" + (.price | tostring) + " " + (.type // "") + "\n" +
         "Duration: " + ((.total_duration / 60 | floor | tostring) + "h " + ((.total_duration % 60) | tostring) + "m") + "\n" +
         "Airline: " + (.flights[0].airline // "Unknown") + "\n" +
         "Flight: " + (.flights[0].flight_number // "Unknown") + "\n" +
         "Class: " + (.flights[0].travel_class // "Economy") + "\n" +
         "Aircraft: " + (.flights[0].airplane // "Unknown") + "\n" +
         (if (.flights | length) > 1 then
           "Stops: " + ((.flights | length) - 1 | tostring) + " (" +
           ([.layovers[]? | .name + " (" + (.duration / 60 | floor | tostring) + "h " + ((.duration % 60) | tostring) + "m)"] | join(", ")) + ")\n"
         else "Nonstop\n" end) +
         "Depart: " + (.flights[0].departure_airport.time // "") + " from " + (.flights[0].departure_airport.name // "") + "\n" +
         "Arrive: " + (.flights[-1].arrival_airport.time // "") + " at " + (.flights[-1].arrival_airport.name // "") + "\n" +
         (if .carbon_emissions then
           "Carbon: " + ((.carbon_emissions.this_flight / 1000 | floor | tostring)) + " kg CO₂"
         else "" end))

  airport:
    terminology: Airport
    mapping:
      id: .airport.id
      name: .airport.name
      iata_code: .airport.id
      city: .city
      country: .country
      country_code: .country_code

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  offer.search:
    description: Search Google Flights for flight offers between airports
    returns: offer[]
    params:
      departure_id:
        type: string
        required: true
        description: "Departure airport IATA code(s), comma-separated (e.g. 'AUS' or 'CDG,ORY')"
      arrival_id:
        type: string
        required: true
        description: "Arrival airport IATA code(s), comma-separated (e.g. 'JFK' or 'LHR,LGW')"
      outbound_date:
        type: string
        required: true
        description: "Outbound date (YYYY-MM-DD)"
      return_date:
        type: string
        description: "Return date (YYYY-MM-DD). Required for round trip."
      type:
        type: integer
        default: 1
        description: "Flight type: 1=Round trip (default), 2=One way, 3=Multi-city"
      travel_class:
        type: integer
        default: 1
        description: "1=Economy (default), 2=Premium economy, 3=Business, 4=First"
      adults:
        type: integer
        default: 1
        description: "Number of adult passengers"
      children:
        type: integer
        description: "Number of children"
      stops:
        type: integer
        description: "0=Any (default), 1=Nonstop, 2=1 stop or fewer, 3=2 stops or fewer"
      max_price:
        type: integer
        description: "Maximum ticket price in USD"
      sort_by:
        type: integer
        description: "1=Top flights (default), 2=Price, 3=Departure, 4=Arrival, 5=Duration, 6=Emissions"
      include_airlines:
        type: string
        description: "Airline IATA codes to include, comma-separated (e.g. 'UA,AA')"
      exclude_airlines:
        type: string
        description: "Airline IATA codes to exclude, comma-separated"
      currency:
        type: string
        default: USD
        description: "Currency code (ISO 4217)"
      hl:
        type: string
        default: en
        description: "Language code"
      gl:
        type: string
        description: "Country code for localization (e.g. 'us', 'uk')"
      deep_search:
        type: boolean
        description: "true for browser-identical results (slower)"
    rest:
      method: GET
      url: https://serpapi.com/search
      query:
        engine: '"google_flights"'
        departure_id: .params.departure_id
        arrival_id: .params.arrival_id
        outbound_date: .params.outbound_date
        return_date: .params.return_date
        type: '.params.type | if . then tostring else null end'
        travel_class: '.params.travel_class | if . then tostring else null end'
        adults: '.params.adults | if . then tostring else null end'
        children: '.params.children | if . then tostring else null end'
        stops: '.params.stops | if . then tostring else null end'
        max_price: '.params.max_price | if . then tostring else null end'
        sort_by: '.params.sort_by | if . then tostring else null end'
        include_airlines: .params.include_airlines
        exclude_airlines: .params.exclude_airlines
        currency: .params.currency
        hl: .params.hl
        gl: .params.gl
        deep_search: '.params.deep_search | if . then tostring else null end'
      response:
        root: /other_flights

  offer.list:
    description: Get the best/recommended flight offers (may not always be available)
    returns: offer[]
    params:
      departure_id:
        type: string
        required: true
        description: "Departure airport IATA code(s)"
      arrival_id:
        type: string
        required: true
        description: "Arrival airport IATA code(s)"
      outbound_date:
        type: string
        required: true
        description: "Outbound date (YYYY-MM-DD)"
      return_date:
        type: string
        description: "Return date (YYYY-MM-DD)"
      type:
        type: integer
        default: 1
        description: "1=Round trip, 2=One way"
      travel_class:
        type: integer
        default: 1
        description: "1=Economy, 2=Premium economy, 3=Business, 4=First"
      currency:
        type: string
        default: USD
        description: "Currency code"
      hl:
        type: string
        default: en
        description: "Language code"
    rest:
      method: GET
      url: https://serpapi.com/search
      query:
        engine: '"google_flights"'
        departure_id: .params.departure_id
        arrival_id: .params.arrival_id
        outbound_date: .params.outbound_date
        return_date: .params.return_date
        type: '.params.type | tostring'
        travel_class: '.params.travel_class | tostring'
        currency: .params.currency
        hl: .params.hl
      response:
        root: /best_flights

  offer.get:
    description: Get return flight offers using a departure token from a previous search
    returns: offer[]
    params:
      departure_token:
        type: string
        required: true
        description: "Departure token from a flight offer search result"
      currency:
        type: string
        default: USD
        description: "Currency code"
      hl:
        type: string
        default: en
        description: "Language code"
    rest:
      method: GET
      url: https://serpapi.com/search
      query:
        engine: '"google_flights"'
        departure_token: .params.departure_token
        currency: .params.currency
        hl: .params.hl
      response:
        root: /other_flights

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

utilities:
  get_booking_options:
    description: Get booking options for selected flights using a booking token
    params:
      booking_token:
        type: string
        required: true
        description: "Booking token from a flight offer result"
      currency:
        type: string
        default: USD
        description: "Currency code"
      hl:
        type: string
        default: en
        description: "Language code"
    returns:
      booking_options: array
      price: number
    rest:
      method: GET
      url: https://serpapi.com/search
      query:
        engine: '"google_flights"'
        booking_token: .params.booking_token
        currency: .params.currency
        hl: .params.hl

  get_price_insights:
    description: Get price insights for a flight route (typical price range, price level, history)
    params:
      departure_id:
        type: string
        required: true
        description: "Departure airport IATA code"
      arrival_id:
        type: string
        required: true
        description: "Arrival airport IATA code"
      outbound_date:
        type: string
        required: true
        description: "Outbound date (YYYY-MM-DD)"
      return_date:
        type: string
        description: "Return date (YYYY-MM-DD)"
      type:
        type: integer
        default: 1
        description: "1=Round trip, 2=One way"
      currency:
        type: string
        default: USD
        description: "Currency code"
    returns:
      lowest_price: number
      price_level: string
      typical_price_range: array
      price_history: array
    rest:
      method: GET
      url: https://serpapi.com/search
      query:
        engine: '"google_flights"'
        departure_id: .params.departure_id
        arrival_id: .params.arrival_id
        outbound_date: .params.outbound_date
        return_date: .params.return_date
        type: '.params.type | tostring'
        currency: .params.currency
      response:
        root: /price_insights
---

# SerpAPI

Structured Google search results — starting with Google Flights.

## Setup

1. Sign up at https://serpapi.com/users/sign_up
2. Get your API key from https://serpapi.com/manage-api-key
3. Add credential in AgentOS Settings

## Google Flights

Search for flight offers using airport IATA codes and dates. Results are
**offers** — priced itineraries containing one or more flight segments.

### offer.search

Search for flight offers between airports.

```
use({ skill: "serpapi", tool: "offer.search", params: {
  departure_id: "AUS",
  arrival_id: "JFK",
  outbound_date: "2026-04-15",
  return_date: "2026-04-22"
}})
```

**One way:**
```
use({ skill: "serpapi", tool: "offer.search", params: {
  departure_id: "SFO",
  arrival_id: "LHR",
  outbound_date: "2026-05-01",
  type: 2
}})
```

**With filters:**
```
use({ skill: "serpapi", tool: "offer.search", params: {
  departure_id: "LAX",
  arrival_id: "NRT",
  outbound_date: "2026-06-01",
  return_date: "2026-06-15",
  travel_class: 3,
  stops: 1,
  sort_by: 2,
  max_price: 3000
}})
```

### offer.list

Get recommended/best offers (Google's picks). May not always be available.

```
use({ skill: "serpapi", tool: "offer.list", params: {
  departure_id: "AUS",
  arrival_id: "LHR",
  outbound_date: "2026-04-15",
  return_date: "2026-04-22"
}})
```

### offer.get

Get return flight offers after selecting an outbound (round trip flow).

```
use({ skill: "serpapi", tool: "offer.get", params: {
  departure_token: "W1siUEVLIi..."
}})
```

### get_booking_options

Get booking links and prices for a selected itinerary.

```
use({ skill: "serpapi", tool: "get_booking_options", params: {
  booking_token: "WyJDalJJ..."
}})
```

### get_price_insights

Check if prices are high or low for a route.

```
use({ skill: "serpapi", tool: "get_price_insights", params: {
  departure_id: "AUS",
  arrival_id: "JFK",
  outbound_date: "2026-04-15",
  return_date: "2026-04-22"
}})
```

## Airport Codes

Common codes for reference:
- **AUS** — Austin-Bergstrom
- **JFK** — New York JFK
- **LAX** — Los Angeles
- **SFO** — San Francisco
- **ORD** — Chicago O'Hare
- **LHR** — London Heathrow
- **CDG** — Paris Charles de Gaulle
- **NRT** — Tokyo Narita
- **HND** — Tokyo Haneda

Search for codes at [IATA](https://www.iata.org/en/publications/directories/code-search/) or on Google Flights.

## Pricing

- **Free tier**: 100 searches/month
- **Developer**: $75/month, 5,000 searches
- **Production**: $150/month, 15,000 searches

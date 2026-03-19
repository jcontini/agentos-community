# SerpAPI

Structured Google search results — starting with Google Flights.

## Setup

1. Sign up at https://serpapi.com/users/sign_up
2. Get your API key from https://serpapi.com/manage-api-key
3. Add credential in AgentOS Settings

## Google Flights

Search for flight offers using airport IATA codes and dates. Results are
**offers** — priced itineraries containing one or more flight segments.

### search_offers

Search for flight offers between airports.

```
use({ skill: "serpapi", tool: "search_offers", params: {
  departure_id: "AUS",
  arrival_id: "JFK",
  outbound_date: "2026-04-15",
  return_date: "2026-04-22"
}})
```

**One way:**
```
use({ skill: "serpapi", tool: "search_offers", params: {
  departure_id: "SFO",
  arrival_id: "LHR",
  outbound_date: "2026-05-01",
  type: 2
}})
```

**With filters:**
```
use({ skill: "serpapi", tool: "search_offers", params: {
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

### list_offers

Get recommended/best offers (Google's picks). May not always be available.

```
use({ skill: "serpapi", tool: "list_offers", params: {
  departure_id: "AUS",
  arrival_id: "LHR",
  outbound_date: "2026-04-15",
  return_date: "2026-04-22"
}})
```

### get_offer

Get return flight offers after selecting an outbound (round trip flow).

```
use({ skill: "serpapi", tool: "get_offer", params: {
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

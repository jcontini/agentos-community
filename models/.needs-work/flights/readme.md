# Flights App

Displays flight status, tracking, and search results.

## Capabilities

| Capability | Description |
|------------|-------------|
| `flight_status` | Get real-time flight status |
| `flight_search` | Search flights between airports |

---

## Schemas

### `flight_status`

Get real-time flight status.

```typescript
// Input
{
  flight_number?: string,    // "AA1004", "UA123"
  flight_iata?: string,      // alternative format
  date?: string,             // YYYY-MM-DD (default: today)
  dep_airport?: string,      // IATA code "SFO"
  arr_airport?: string       // IATA code "JFK"
}

// Output (based on AviationStack API)
{
  flight: {
    number: string           // required "AA1004"
    iata: string             // "AA1004"
    icao?: string            // "AAL1004"
  }
  status: 'scheduled' | 'active' | 'landed' | 'cancelled' | 'diverted' | 'delayed'
  airline: {
    name: string             // required "American Airlines"
    iata: string             // "AA"
    logo?: string            // URL
  }
  departure: {
    airport: string          // required "San Francisco International"
    iata: string             // required "SFO"
    city?: string
    terminal?: string
    gate?: string
    scheduled: string        // required (ISO datetime)
    estimated?: string
    actual?: string
    delay?: number           // minutes
  }
  arrival: {
    airport: string          // required
    iata: string             // required
    city?: string
    terminal?: string
    gate?: string
    baggage?: string         // baggage claim
    scheduled: string        // required
    estimated?: string
    actual?: string
    delay?: number           // minutes
  }
  aircraft?: {
    model: string            // "Boeing 737-800"
    registration?: string    // "N12345"
  }
  live?: {                   // only when in-flight
    latitude: number
    longitude: number
    altitude: number         // meters
    speed: number            // km/h
    direction: number        // degrees
    updated: string          // ISO datetime
  }
  duration?: {
    scheduled?: number       // minutes
    actual?: number
  }
}
```

### `flight_search`

Search for flights between airports.

```typescript
// Input
{
  dep_airport: string,       // required - IATA "SFO"
  arr_airport: string,       // required - IATA "JFK"
  date: string,              // required - YYYY-MM-DD
  airline?: string           // filter by airline
}

// Output
{
  flights: Flight[]          // same structure as flight_status
}
```

---

## Example Connectors

- **AviationStack** — Flight tracking API
- **FlightAware** — Flight tracking service
- **Flightradar24** — Live flight tracking

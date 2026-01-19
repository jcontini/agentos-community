---
id: demo
name: Demo
description: Fun demos using free public APIs - no API keys needed!
icon: icon.svg
tags: [demo, fun, examples]

# Terminology: how this service names entities
terminology:
  webpage: Web Page
  task: Task
  contact: Contact

# Relationship support (demo is a mock - no real relationships)
# relationships: {}  # Omitted = no relationships supported

# Mock entity implementations for testing
# Uses httpbin.org (reliable) to test entity-based architecture
entities:
  # Webpage entity mocks (for Browser app testing)
  webpage:
    search:
      description: Mock web search (returns sample results)
      params:
        query: { type: string, description: "Search query" }
      rest:
        method: GET
        url: "https://httpbin.org/anything?query={{params.query}}"
        response:
          mapping:
            results: "[{\"url\": \"https://example.com/1\", \"title\": \"Result for {{params.query}}\", \"snippet\": \"This is a mock search result for testing.\"}]"

    read:
      description: Mock webpage read (returns sample content)
      params:
        url: { type: string, description: "URL to read" }
      rest:
        method: GET
        url: "https://httpbin.org/anything?url={{params.url}}"
        response:
          mapping:
            url: ".args.url"
            title: "'Mock Page Title'"
            content: "'# Mock Content\\n\\nThis is mock webpage content for testing the entity-based architecture.'"

  # Task entity mocks (for Tasks app testing)
  task:
    list:
      description: Mock task list
      rest:
        method: GET
        url: "https://httpbin.org/anything?action=task.list"
        response:
          mapping:
            tasks: "[{\"id\": \"1\", \"title\": \"Mock task 1\", \"completed\": false}, {\"id\": \"2\", \"title\": \"Mock task 2\", \"completed\": true}]"

    create:
      description: Mock task creation
      params:
        title: { type: string, description: "Task title" }
      rest:
        method: POST
        url: "https://httpbin.org/anything"
        body:
          action: task.create
          title: "{{params.title}}"
        response:
          mapping:
            id: "'new-task-id'"
            title: ".json.title"
            completed: "false"

  # Contact entity mocks (for Contacts app testing)
  contact:
    list:
      description: Mock contact list
      rest:
        method: GET
        url: "https://httpbin.org/anything?action=contact.list"
        response:
          mapping:
            contacts: "[{\"id\": \"1\", \"name\": \"Alice Smith\", \"email\": \"alice@example.com\"}, {\"id\": \"2\", \"name\": \"Bob Jones\", \"email\": \"bob@example.com\"}]"

    get:
      description: Mock get contact by ID
      params:
        id: { type: string, description: "Contact ID" }
      rest:
        method: GET
        url: "https://httpbin.org/anything?action=contact.get&id={{params.id}}"
        response:
          mapping:
            id: ".args.id"
            name: "'Mock Contact'"
            email: "'mock@example.com'"
            phone: "'+1-555-0123'"

  # Demo-specific tools (fun/testing)
  demo:
    weather:
      description: Get current weather for a city
      params:
        city: { type: string, description: "City name", example: "Austin" }
      rest:
        method: GET
        url: "https://wttr.in/{{params.city}}?format=j1"
        response:
          root: "current_condition[0]"
          mapping:
            location: "'{{params.city}}'"
            temp_f: ".temp_F"
            temp_c: ".temp_C"
            condition: ".weatherDesc[0].value"
            humidity: ".humidity"
            wind_mph: ".windspeedMiles"

    ip:
      description: Get your public IP and location info
      rest:
        method: GET
        url: "http://ip-api.com/json/"
        response:
          mapping:
            ip: ".query"
            city: ".city"
            region: ".regionName"
            country: ".country"
            isp: ".isp"
            lat: ".lat"
            lon: ".lon"

    iss:
      description: Get current position of the International Space Station
      rest:
        method: GET
        url: "http://api.open-notify.org/iss-now.json"
        response:
          mapping:
            latitude: ".iss_position.latitude"
            longitude: ".iss_position.longitude"
            timestamp: ".timestamp"

    space:
      description: Get info about the next SpaceX launch
      rest:
        method: GET
        url: "https://api.spacexdata.com/v5/launches/next"
        response:
          mapping:
            name: ".name"
            date_utc: ".date_utc"
            rocket: ".rocket"
            details: ".details"
            webcast: ".links.webcast"

    joke:
      description: Get a random programming joke
      rest:
        method: GET
        url: "https://official-joke-api.appspot.com/jokes/programming/random"
        response:
          root: "[0]"
          mapping:
            setup: ".setup"
            punchline: ".punchline"

    fact:
      description: Get a random useless fact
      rest:
        method: GET
        url: "https://uselessfacts.jsph.pl/api/v2/facts/random"
        response:
          mapping:
            fact: ".text"
            source: ".source"

    echo:
      description: Echo back a message (for testing)
      params:
        message: { type: string, description: "Message to echo" }
      command:
        binary: echo
        args: ["{{params.message}}"]

    http_get:
      description: Test HTTP GET request via httpbin
      rest:
        method: GET
        url: "https://httpbin.org/get"

instructions: |
  Demo plugin for testing AgentOS. All actions use free APIs - no keys needed!
  
  Mock entity implementations (for testing apps):
  - webpage.search/read: Mock web search and page content
  - task.list/create: Mock task management
  - contact.list/get: Mock contact lookups
  
  Fun demos:
  - demo.weather: Get weather for any city
  - demo.ip: See your public IP and location
  - demo.iss: Track the International Space Station
  - demo.joke: Get a programming joke
---

# Demo

Test harness and showcase plugin. Uses free public APIs - no keys required!

## Mock Entity Implementations

For testing the entity-based architecture without real credentials:

| Entity | Operations | What it does |
|--------|------------|--------------|
| `webpage` | `search`, `read` | Mock web search results and page content |
| `task` | `list`, `create` | Mock task management |
| `contact` | `list`, `get` | Mock contact directory |

## Fun Demo Tools

| Tool | What it does |
|------|--------------|
| `demo.weather` | Current weather for any city (wttr.in) |
| `demo.ip` | Your public IP and location (ip-api.com) |
| `demo.iss` | Current ISS position (open-notify.org) |
| `demo.space` | Next SpaceX launch (spacexdata.com) |
| `demo.joke` | Random programming joke |
| `demo.fact` | Random useless fact |
| `demo.echo` | Echo a message (for testing) |
| `demo.http_get` | Test HTTP via httpbin |

## Examples

```
# Mock entity tests
UsePlugin(plugin: "demo", tool: "webpage.search", params: {query: "test"})
UsePlugin(plugin: "demo", tool: "task.list", params: {limit: 5})
UsePlugin(plugin: "demo", tool: "contact.get", params: {id: "1"})

# Fun demos
UsePlugin(plugin: "demo", tool: "demo.weather", params: {city: "Austin"})
UsePlugin(plugin: "demo", tool: "demo.joke")
```

## For Contributors

This plugin demonstrates:
- Entity-based plugin structure (`entities.webpage.search`)
- REST API calls with response mapping
- Shell commands (`demo.echo`)

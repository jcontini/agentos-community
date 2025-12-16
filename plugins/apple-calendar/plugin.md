---
id: apple-calendar
name: Apple Calendar
description: Read and manage macOS Calendar events
category: productivity
icon: https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Apple_Calendar_%28iOS%29.svg/2560px-Apple_Calendar_%28iOS%29.svg.png
color: "#FF3B30"
platform: macos

triggers:
  - asks about calendar, schedule, meetings, or availability

requires:
  - swift    # Pre-installed on macOS
  - osascript  # Pre-installed on macOS

permissions:
  - calendar

actions:
  list_calendars:
    readonly: true
    description: List all available calendars with colors
    run: |
      osascript << 'EOF'
      on clamp(val)
        if val > 255 then return 255
        if val < 0 then return 0
        return val
      end clamp
      
      on rgbToHex(r, g, b)
        -- Convert 16-bit RGB (0-65535) to 8-bit hex
        set r8 to my clamp(round (r / 257))
        set g8 to my clamp(round (g / 257))
        set b8 to my clamp(round (b / 257))
        set hexChars to "0123456789ABCDEF"
        set hexColor to "#"
        repeat with val in {r8, g8, b8}
          set hi to (val div 16) + 1
          set lo to (val mod 16) + 1
          set hexColor to hexColor & character hi of hexChars & character lo of hexChars
        end repeat
        return hexColor
      end rgbToHex
      
      tell application "Calendar"
        set calList to {}
        repeat with cal in calendars
          set calName to name of cal
          set calColor to color of cal
          set hexColor to my rgbToHex(item 1 of calColor, item 2 of calColor, item 3 of calColor)
          set end of calList to "{\"name\":\"" & calName & "\",\"color\":\"" & hexColor & "\"}"
        end repeat
        set AppleScript's text item delimiters to ","
        return "[" & (calList as text) & "]"
      end tell
      EOF

  list:
    readonly: true
    description: List calendar events (upcoming or past)
    params:
      days:
        type: number
        default: 7
        description: Number of days to fetch (1-30)
      past:
        type: boolean
        default: "false"
        description: Look backward instead of forward
      calendar:
        type: string
        description: Filter by calendar name (partial match)
      query:
        type: string
        description: Search title, location, or notes (partial match)
      limit:
        type: number
        description: Max events to return
      exclude_all_day:
        type: boolean
        default: "false"
        description: Exclude all-day events
    run: |
      cat << 'SWIFT' > /tmp/agentos_cal_list.swift
      import EventKit
      import Foundation
      
      let store = EKEventStore()
      let semaphore = DispatchSemaphore(value: 0)
      var accessGranted = false
      
      if #available(macOS 14.0, *) {
          store.requestFullAccessToEvents { granted, _ in
              accessGranted = granted
              semaphore.signal()
          }
      } else {
          store.requestAccess(to: .event) { granted, _ in
              accessGranted = granted
              semaphore.signal()
          }
      }
      semaphore.wait()
      
      guard accessGranted else {
          fputs("Error: Calendar access denied. Grant access in System Settings > Privacy & Security > Calendars\n", stderr)
          exit(1)
      }
      
      // Parse arguments: days, past, calendar, query, limit, exclude_all_day
      let args = CommandLine.arguments
      let days = args.count > 1 ? Int(args[1]) ?? 7 : 7
      let past = args.count > 2 && args[2] == "true"
      let calendarFilter = args.count > 3 && args[3] != "" ? args[3].lowercased() : nil
      let titleQuery = args.count > 4 && args[4] != "" ? args[4].lowercased() : nil
      let limit = args.count > 5 && args[5] != "" ? Int(args[5]) : nil
      let excludeAllDay = args.count > 6 && args[6] == "true"
      
      // Date range
      let calendar = Calendar.current
      let now = Date()
      let startOfDay = calendar.startOfDay(for: now)
      
      let startDate: Date
      let endDate: Date
      if past {
          startDate = calendar.date(byAdding: .day, value: -days, to: startOfDay)!
          endDate = now
      } else {
          startDate = startOfDay
          endDate = calendar.date(byAdding: .day, value: days, to: startOfDay)!
      }
      
      // Filter calendars if specified
      var calendarsToSearch: [EKCalendar]? = nil
      if let filter = calendarFilter {
          calendarsToSearch = store.calendars(for: .event).filter {
              $0.title.lowercased().contains(filter)
          }
      }
      
      // Query events
      let predicate = store.predicateForEvents(withStart: startDate, end: endDate, calendars: calendarsToSearch)
      var events = store.events(matching: predicate)
      
      // Filter all-day if requested
      if excludeAllDay {
          events = events.filter { !$0.isAllDay }
      }
      
      // Filter by title, location, or notes if query specified
      if let query = titleQuery {
          events = events.filter {
              ($0.title ?? "").lowercased().contains(query) ||
              ($0.location ?? "").lowercased().contains(query) ||
              ($0.notes ?? "").lowercased().contains(query)
          }
      }
      
      // Sort: past = newest first, future = oldest first
      if past {
          events.sort { $0.startDate > $1.startDate }
      } else {
          events.sort { $0.startDate < $1.startDate }
      }
      
      // Apply limit
      if let lim = limit, lim > 0 {
          events = Array(events.prefix(lim))
      }
      
      // Date formatters
      let isoFormatter = ISO8601DateFormatter()
      isoFormatter.formatOptions = [.withInternetDateTime]
      
      let timeFormatter = DateFormatter()
      timeFormatter.dateFormat = "HH:mm"
      
      let dateFormatter = DateFormatter()
      dateFormatter.dateFormat = "yyyy-MM-dd"
      
      // Build JSON output
      var output: [[String: Any]] = []
      for event in events {
          var dict: [String: Any] = [
              "uid": event.eventIdentifier ?? "",
              "title": event.title ?? "",
              "calendar": event.calendar.title,
              "start": isoFormatter.string(from: event.startDate),
              "end": isoFormatter.string(from: event.endDate),
              "date": dateFormatter.string(from: event.startDate),
              "start_time": timeFormatter.string(from: event.startDate),
              "end_time": timeFormatter.string(from: event.endDate),
              "all_day": event.isAllDay
          ]
          if let location = event.location, !location.isEmpty {
              dict["location"] = location
          }
          if let notes = event.notes, !notes.isEmpty {
              dict["notes"] = notes
          }
          if let url = event.url {
              dict["url"] = url.absoluteString
          }
          output.append(dict)
      }
      
      // Output JSON
      if let jsonData = try? JSONSerialization.data(withJSONObject: output, options: [.prettyPrinted, .sortedKeys]),
         let jsonString = String(data: jsonData, encoding: .utf8) {
          print(jsonString)
      } else {
          print("[]")
      }
      SWIFT
      swift /tmp/agentos_cal_list.swift "${PARAM_DAYS:-7}" "${PARAM_PAST:-false}" "${PARAM_CALENDAR:-}" "${PARAM_QUERY:-}" "${PARAM_LIMIT:-}" "${PARAM_EXCLUDE_ALL_DAY:-false}"

  get:
    readonly: true
    description: Get full details of a specific event by UID
    params:
      uid:
        type: string
        required: true
        description: Event UID from list
    run: |
      cat << 'SWIFT' > /tmp/agentos_cal_get.swift
      import EventKit
      import Foundation
      
      let store = EKEventStore()
      let semaphore = DispatchSemaphore(value: 0)
      var accessGranted = false
      
      if #available(macOS 14.0, *) {
          store.requestFullAccessToEvents { granted, _ in
              accessGranted = granted
              semaphore.signal()
          }
      } else {
          store.requestAccess(to: .event) { granted, _ in
              accessGranted = granted
              semaphore.signal()
          }
      }
      semaphore.wait()
      
      guard accessGranted else {
          fputs("Error: Calendar access denied\n", stderr)
          exit(1)
      }
      
      let uid = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : ""
      guard !uid.isEmpty, let event = store.event(withIdentifier: uid) else {
          fputs("Error: Event not found\n", stderr)
          exit(1)
      }
      
      let isoFormatter = ISO8601DateFormatter()
      isoFormatter.formatOptions = [.withInternetDateTime]
      
      var dict: [String: Any] = [
          "uid": event.eventIdentifier ?? "",
          "title": event.title ?? "",
          "calendar": event.calendar.title,
          "start": isoFormatter.string(from: event.startDate),
          "end": isoFormatter.string(from: event.endDate),
          "all_day": event.isAllDay
      ]
      if let location = event.location, !location.isEmpty {
          dict["location"] = location
      }
      if let notes = event.notes, !notes.isEmpty {
          dict["notes"] = notes
      }
      if let url = event.url {
          dict["url"] = url.absoluteString
      }
      if event.hasRecurrenceRules, let rules = event.recurrenceRules {
          dict["recurring"] = true
          dict["recurrence"] = rules.map { $0.description }
      }
      if event.hasAttendees, let attendees = event.attendees {
          dict["attendees"] = attendees.compactMap { $0.name }
      }
      if event.hasAlarms, let alarms = event.alarms {
          dict["alarms"] = alarms.map { Int($0.relativeOffset / 60) }  // minutes before
      }
      
      if let jsonData = try? JSONSerialization.data(withJSONObject: dict, options: [.prettyPrinted, .sortedKeys]),
         let jsonString = String(data: jsonData, encoding: .utf8) {
          print(jsonString)
      }
      SWIFT
      swift /tmp/agentos_cal_get.swift "$PARAM_UID"

  create:
    description: Create a new calendar event
    params:
      title:
        type: string
        required: true
        description: Event title
      start:
        type: string
        required: true
        description: Start date/time (YYYY-MM-DD HH:MM or YYYY-MM-DD for all-day)
      end:
        type: string
        description: End date/time (defaults to 1 hour after start)
      calendar:
        type: string
        description: Calendar name (uses system default if not specified)
      location:
        type: string
        description: Event location
      notes:
        type: string
        description: Event notes/description
      all_day:
        type: boolean
        default: "false"
        description: Create as all-day event
    run: |
      CAL="${PARAM_CALENDAR:-}"
      cat << 'SWIFT' > /tmp/agentos_cal_create.swift
      import EventKit
      import Foundation
      
      let store = EKEventStore()
      let semaphore = DispatchSemaphore(value: 0)
      var accessGranted = false
      
      if #available(macOS 14.0, *) {
          store.requestFullAccessToEvents { granted, _ in
              accessGranted = granted
              semaphore.signal()
          }
      } else {
          store.requestAccess(to: .event) { granted, _ in
              accessGranted = granted
              semaphore.signal()
          }
      }
      semaphore.wait()
      
      guard accessGranted else {
          fputs("Error: Calendar access denied\n", stderr)
          exit(1)
      }
      
      // Parse arguments: title, start, end, calendar, location, notes, all_day
      let args = CommandLine.arguments
      guard args.count > 2 else {
          fputs("Error: title and start required\n", stderr)
          exit(1)
      }
      
      let title = args[1]
      let startStr = args[2]
      let endStr = args.count > 3 && args[3] != "" ? args[3] : ""
      let calName = args.count > 4 && args[4] != "" ? args[4] : ""
      let location = args.count > 5 && args[5] != "" ? args[5] : ""
      let notes = args.count > 6 && args[6] != "" ? args[6] : ""
      let allDay = args.count > 7 && args[7] == "true"
      
      // Find calendar
      var calendar: EKCalendar?
      if !calName.isEmpty {
          calendar = store.calendars(for: .event).first { $0.title.lowercased().contains(calName.lowercased()) }
      }
      if calendar == nil {
          calendar = store.defaultCalendarForNewEvents
      }
      guard let targetCalendar = calendar else {
          fputs("Error: No calendar found\n", stderr)
          exit(1)
      }
      
      // Parse dates
      let formatter = DateFormatter()
      formatter.timeZone = TimeZone.current
      
      var startDate: Date?
      var endDate: Date?
      
      if allDay || startStr.count == 10 {
          // All-day event: YYYY-MM-DD
          formatter.dateFormat = "yyyy-MM-dd"
          startDate = formatter.date(from: String(startStr.prefix(10)))
          if !endStr.isEmpty {
              endDate = formatter.date(from: String(endStr.prefix(10)))
          } else {
              endDate = startDate
          }
      } else {
          // Timed event: YYYY-MM-DD HH:MM
          formatter.dateFormat = "yyyy-MM-dd HH:mm"
          startDate = formatter.date(from: startStr)
          if !endStr.isEmpty {
              endDate = formatter.date(from: endStr)
          } else if let start = startDate {
              endDate = start.addingTimeInterval(3600) // 1 hour default
          }
      }
      
      guard let start = startDate, let end = endDate else {
          fputs("Error: Invalid date format. Use YYYY-MM-DD HH:MM or YYYY-MM-DD\n", stderr)
          exit(1)
      }
      
      // Create event
      let event = EKEvent(eventStore: store)
      event.title = title
      event.startDate = start
      event.endDate = end
      event.calendar = targetCalendar
      event.isAllDay = allDay || startStr.count == 10
      
      if !location.isEmpty { event.location = location }
      if !notes.isEmpty { event.notes = notes }
      
      do {
          try store.save(event, span: .thisEvent)
          print("{\"status\":\"created\", \"uid\":\"\(event.eventIdentifier ?? "")\", \"calendar\":\"\(targetCalendar.title)\"}")
      } catch {
          fputs("Error: \(error.localizedDescription)\n", stderr)
          exit(1)
      }
      SWIFT
      swift /tmp/agentos_cal_create.swift "$PARAM_TITLE" "$PARAM_START" "${PARAM_END:-}" "$CAL" "${PARAM_LOCATION:-}" "${PARAM_NOTES:-}" "${PARAM_ALL_DAY:-false}"

  update:
    description: Update an existing event (only specify fields you want to change)
    params:
      uid:
        type: string
        required: true
        description: Event UID to update
      title:
        type: string
        description: New title
      start:
        type: string
        description: New start date/time (YYYY-MM-DD HH:MM)
      end:
        type: string
        description: New end date/time (YYYY-MM-DD HH:MM)
      location:
        type: string
        description: New location
      notes:
        type: string
        description: New notes/description
      url:
        type: string
        description: URL to attach (e.g., Zoom link)
      calendar:
        type: string
        description: Move to different calendar (by name)
    run: |
      cat << 'SWIFT' > /tmp/agentos_cal_update.swift
      import EventKit
      import Foundation
      
      let store = EKEventStore()
      let semaphore = DispatchSemaphore(value: 0)
      var accessGranted = false
      
      if #available(macOS 14.0, *) {
          store.requestFullAccessToEvents { granted, _ in
              accessGranted = granted
              semaphore.signal()
          }
      } else {
          store.requestAccess(to: .event) { granted, _ in
              accessGranted = granted
              semaphore.signal()
          }
      }
      semaphore.wait()
      
      guard accessGranted else {
          fputs("Error: Calendar access denied\n", stderr)
          exit(1)
      }
      
      // Parse arguments: uid, title, start, end, location, notes, url, calendar
      let args = CommandLine.arguments
      guard args.count > 1 else {
          fputs("Error: UID required\n", stderr)
          exit(1)
      }
      
      let uid = args[1]
      let title = args.count > 2 && args[2] != "" ? args[2] : nil
      let startStr = args.count > 3 && args[3] != "" ? args[3] : nil
      let endStr = args.count > 4 && args[4] != "" ? args[4] : nil
      let location = args.count > 5 && args[5] != "" ? args[5] : nil
      let notes = args.count > 6 && args[6] != "" ? args[6] : nil
      let urlStr = args.count > 7 && args[7] != "" ? args[7] : nil
      let calendarName = args.count > 8 && args[8] != "" ? args[8] : nil
      
      guard let event = store.event(withIdentifier: uid) else {
          fputs("Error: Event not found\n", stderr)
          exit(1)
      }
      
      let formatter = DateFormatter()
      formatter.dateFormat = "yyyy-MM-dd HH:mm"
      formatter.timeZone = TimeZone.current
      
      if let t = title { event.title = t }
      if let s = startStr, let d = formatter.date(from: s) { event.startDate = d }
      if let e = endStr, let d = formatter.date(from: e) { event.endDate = d }
      if let l = location { event.location = l }
      if let n = notes { event.notes = n }
      if let u = urlStr, let url = URL(string: u) { event.url = url }
      
      // Move to different calendar if specified
      if let calName = calendarName {
          if let newCal = store.calendars(for: .event).first(where: { $0.title.lowercased().contains(calName.lowercased()) }) {
              event.calendar = newCal
          } else {
              fputs("Error: Calendar '\(calName)' not found\n", stderr)
              exit(1)
          }
      }
      
      do {
          try store.save(event, span: .thisEvent)
          print("{\"status\":\"updated\", \"uid\":\"\(event.eventIdentifier ?? uid)\", \"calendar\":\"\(event.calendar.title)\"}")
      } catch {
          fputs("Error: \(error.localizedDescription)\n", stderr)
          exit(1)
      }
      SWIFT
      swift /tmp/agentos_cal_update.swift "$PARAM_UID" "${PARAM_TITLE:-}" "${PARAM_START:-}" "${PARAM_END:-}" "${PARAM_LOCATION:-}" "${PARAM_NOTES:-}" "${PARAM_URL:-}" "${PARAM_CALENDAR:-}"

  delete:
    description: Delete a calendar event
    params:
      uid:
        type: string
        required: true
        description: Event UID to delete
    run: |
      cat << 'SWIFT' > /tmp/agentos_cal_delete.swift
      import EventKit
      import Foundation
      
      let store = EKEventStore()
      let semaphore = DispatchSemaphore(value: 0)
      var accessGranted = false
      
      if #available(macOS 14.0, *) {
          store.requestFullAccessToEvents { granted, _ in
              accessGranted = granted
              semaphore.signal()
          }
      } else {
          store.requestAccess(to: .event) { granted, _ in
              accessGranted = granted
              semaphore.signal()
          }
      }
      semaphore.wait()
      
      guard accessGranted else {
          fputs("Error: Calendar access denied\n", stderr)
          exit(1)
      }
      
      let uid = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : ""
      guard !uid.isEmpty, let event = store.event(withIdentifier: uid) else {
          fputs("Error: Event not found\n", stderr)
          exit(1)
      }
      
      let title = event.title ?? "Untitled"
      
      do {
          try store.remove(event, span: .thisEvent)
          print("{\"status\":\"deleted\", \"title\":\"\(title)\"}")
      } catch {
          fputs("Error: \(error.localizedDescription)\n", stderr)
          exit(1)
      }
      SWIFT
      swift /tmp/agentos_cal_delete.swift "$PARAM_UID"

  today:
    readonly: true
    description: Get today's events (shortcut for list with days=1)
    params:
      exclude_all_day:
        type: boolean
        default: "false"
        description: Exclude all-day events
    run: |
      # Reuse the list script with days=1
      cat << 'SWIFT' > /tmp/agentos_cal_list.swift
      import EventKit
      import Foundation
      
      let store = EKEventStore()
      let semaphore = DispatchSemaphore(value: 0)
      var accessGranted = false
      
      if #available(macOS 14.0, *) {
          store.requestFullAccessToEvents { granted, _ in
              accessGranted = granted
              semaphore.signal()
          }
      } else {
          store.requestAccess(to: .event) { granted, _ in
              accessGranted = granted
              semaphore.signal()
          }
      }
      semaphore.wait()
      
      guard accessGranted else {
          fputs("Error: Calendar access denied\n", stderr)
          exit(1)
      }
      
      let args = CommandLine.arguments
      let days = args.count > 1 ? Int(args[1]) ?? 7 : 7
      let past = args.count > 2 && args[2] == "true"
      let calendarFilter = args.count > 3 && args[3] != "" ? args[3].lowercased() : nil
      let limit = args.count > 4 && args[4] != "" ? Int(args[4]) : nil
      let excludeAllDay = args.count > 5 && args[5] == "true"
      
      let calendar = Calendar.current
      let now = Date()
      let startOfDay = calendar.startOfDay(for: now)
      
      let startDate: Date
      let endDate: Date
      if past {
          startDate = calendar.date(byAdding: .day, value: -days, to: startOfDay)!
          endDate = now
      } else {
          startDate = startOfDay
          endDate = calendar.date(byAdding: .day, value: days, to: startOfDay)!
      }
      
      var calendarsToSearch: [EKCalendar]? = nil
      if let filter = calendarFilter {
          calendarsToSearch = store.calendars(for: .event).filter {
              $0.title.lowercased().contains(filter)
          }
      }
      
      let predicate = store.predicateForEvents(withStart: startDate, end: endDate, calendars: calendarsToSearch)
      var events = store.events(matching: predicate)
      
      if excludeAllDay {
          events = events.filter { !$0.isAllDay }
      }
      
      if past {
          events.sort { $0.startDate > $1.startDate }
      } else {
          events.sort { $0.startDate < $1.startDate }
      }
      
      if let lim = limit, lim > 0 {
          events = Array(events.prefix(lim))
      }
      
      let isoFormatter = ISO8601DateFormatter()
      isoFormatter.formatOptions = [.withInternetDateTime]
      let timeFormatter = DateFormatter()
      timeFormatter.dateFormat = "HH:mm"
      let dateFormatter = DateFormatter()
      dateFormatter.dateFormat = "yyyy-MM-dd"
      
      var output: [[String: Any]] = []
      for event in events {
          var dict: [String: Any] = [
              "uid": event.eventIdentifier ?? "",
              "title": event.title ?? "",
              "calendar": event.calendar.title,
              "start": isoFormatter.string(from: event.startDate),
              "end": isoFormatter.string(from: event.endDate),
              "date": dateFormatter.string(from: event.startDate),
              "start_time": timeFormatter.string(from: event.startDate),
              "end_time": timeFormatter.string(from: event.endDate),
              "all_day": event.isAllDay
          ]
          if let location = event.location, !location.isEmpty {
              dict["location"] = location
          }
          output.append(dict)
      }
      
      if let jsonData = try? JSONSerialization.data(withJSONObject: output, options: [.prettyPrinted, .sortedKeys]),
         let jsonString = String(data: jsonData, encoding: .utf8) {
          print(jsonString)
      } else {
          print("[]")
      }
      SWIFT
      swift /tmp/agentos_cal_list.swift "1" "false" "" "" "${PARAM_EXCLUDE_ALL_DAY:-false}"
---

# Apple Calendar

Read and manage macOS Calendar events. Uses EventKit for fast reads and AppleScript for reliable writes with iCloud sync.

## Requirements

- **macOS only** - Uses Calendar.app APIs
- **Calendar permission** - System Settings → Privacy & Security → Calendars → Full Access for Cursor/Terminal

## Tools (6 total)

| Action | Purpose | Implementation |
|--------|---------|----------------|
| `list_calendars` | List all calendars | AppleScript |
| `list` | List upcoming events | Swift/EventKit |
| `get` | Get event details by UID | Swift/EventKit |
| `today` | Get today's events | Swift/EventKit |
| `create` | Create new event | Swift/EventKit |
| `update` | Update event | Swift/EventKit |
| `delete` | Delete event | Swift/EventKit |

---

## list_calendars

List all available calendars with their IDs.

**Example:**
```
list_calendars()
```

**Output:**
```json
[{"name": "Work", "id": "ABC123"}, {"name": "Personal", "id": "DEF456"}]
```

---

## list

List calendar events - upcoming or past, with filtering options.

**Parameters:**
- `days` (optional): Number of days to search, default 7
- `past` (optional): Look backward instead of forward, default false
- `calendar` (optional): Filter by calendar name (partial match)
- `query` (optional): Search by event title (partial match)
- `limit` (optional): Max events to return
- `exclude_all_day` (optional): Exclude all-day events, default false

**Examples:**
```
list()                                    # Next 7 days, all calendars
list(limit: 5)                            # Next 5 events
list(past: true, limit: 5)                # Last 5 events
list(query: "sync")                       # Events with "sync" in title
list(query: "John", days: 30)             # Meetings with John, next 30 days  
list(query: "Zoom", past: true)           # Past events at Zoom (or with Zoom in title)
list(query: "Uchi", past: true, days: 90) # Events at Uchi in past 90 days
list(calendar: "Work")                    # Only Work calendar
list(exclude_all_day: true, limit: 10)    # Next 10 timed events
list(past: true, days: 30, calendar: "Adavia")  # Past month from Adavia
```

**Output:** JSON array of events with: `uid`, `title`, `calendar`, `start`, `end`, `date`, `start_time`, `end_time`, `all_day`, and optional `location`, `notes`, `url`.

---

## get

Get full details of a specific event.

**Parameters:**
- `uid` (required): Event UID from list

**Example:**
```
get(uid: "ABC123:XYZ")
```

**Output:** JSON object with all event fields including `attendees`, `recurrence`, `alarms`.

---

## today

Shortcut to get today's events only.

**Example:**
```
today()
```

---

## create

Create a new calendar event.

**Parameters:**
- `title` (required): Event title
- `start` (required): Start date/time (`YYYY-MM-DD HH:MM` or `YYYY-MM-DD` for all-day)
- `end` (optional): End date/time (defaults to 1 hour after start)
- `calendar` (optional): Calendar name (uses setting if not specified)
- `location` (optional): Event location
- `notes` (optional): Event description
- `url` (optional): URL to attach
- `all_day` (optional): Create as all-day event

**Examples:**
```
create(title: "Team Sync", start: "2025-12-15 10:00", end: "2025-12-15 11:00")
create(title: "Vacation", start: "2025-12-20", all_day: true, calendar: "Personal")
create(title: "Dinner", start: "2025-12-15 19:00", location: "Uchi Austin", notes: "Birthday dinner")
```

---

## update

Update an existing event. Only specify fields you want to change.

**Parameters:**
- `uid` (required): Event UID
- `title` (optional): New title
- `start` (optional): New start time (YYYY-MM-DD HH:MM)
- `end` (optional): New end time (YYYY-MM-DD HH:MM)
- `location` (optional): New location
- `notes` (optional): New description
- `url` (optional): URL to attach (e.g., Zoom link)
- `calendar` (optional): Move to different calendar

**Examples:**
```
update(uid: "ABC123", location: "Zoom")           # Just add location
update(uid: "ABC123", start: "2025-12-15 15:00")  # Reschedule to 3pm
update(uid: "ABC123", url: "https://zoom.us/j/123")  # Add Zoom link
update(uid: "ABC123", calendar: "Work")           # Move to Work calendar
update(uid: "ABC123", title: "New Title", notes: "Updated notes")
```

---

## delete

Delete a calendar event.

**Parameters:**
- `uid` (required): Event UID

**Example:**
```
delete(uid: "ABC123:XYZ")
```

---

## Notes

- **Permission required**: Full Calendar access must be granted to Cursor/Terminal in System Settings
- **Subscribed calendars**: EventKit sees all calendars including ICS subscriptions (US Holidays, etc.)
- **Recurring events**: Updates/deletes only affect the single occurrence by default
- **Time zones**: Uses system timezone automatically
- **iCloud sync**: Changes sync automatically to iCloud/Google

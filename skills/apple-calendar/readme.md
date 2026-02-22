---
id: apple-calendar
name: Apple Calendar
description: Access macOS Calendar via native EventKit APIs
icon: icon.png
color: "#000000"

website: https://www.apple.com/macos/

auth: none
connects_to: apple-calendar

seed:
  - id: apple-calendar
    types: [software]
    name: Apple Calendar
    data:
      software_type: app
      url: https://support.apple.com/guide/calendar/welcome/mac
      launched: "2002"
      platforms: [macos, ios, ipados, watchos, visionos]
      wikidata_id: Q306184
    relationships:
      - role: offered_by
        to: apple

  - id: apple
    types: [organization]
    name: Apple Inc.
    data:
      type: company
      url: https://apple.com
      founded: "1976"
      ticker: AAPL
      exchange: NASDAQ
      wikidata_id: Q312

instructions: |
  Apple Calendar accesses local macOS Calendar via EventKit.
  
  **Requirements:**
  - macOS only
  - Grant permissions in System Settings → Privacy & Security:
    - Calendars → Full Access for Cursor/Terminal
  
  **Notes:**
  - All calendars configured in macOS Calendar.app are accessible (iCloud, Google, etc.)
  - Subscribed calendars (ICS feeds like US Holidays) are read-only
  - Recurring events: updates/deletes only affect the single occurrence
  - Times use system timezone

transformers:
  calendar:
    terminology: Calendar
    mapping:
      id: .id
      name: .name
      color: .color
      is_subscribed: .is_readonly

  meeting:
    terminology: Event
    mapping:
      id: .id
      title: .title
      description: .description
      content: .description
      start: .start
      end: .end
      all_day: .all_day
      location: .location
      recurrence: .recurrence

operations:
  calendar.list:
    description: List all available calendars
    returns: calendar[]
    swift:
      script: |
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
            fputs("{\"error\": \"Calendar access denied\"}\n", stderr)
            exit(1)
        }
        
        let calendars = store.calendars(for: .event)
        var output: [[String: Any]] = []
        
        for cal in calendars {
            var dict: [String: Any] = [
                "id": cal.calendarIdentifier,
                "name": cal.title
            ]
            if let cgColor = cal.cgColor {
                let r = Int((cgColor.components?[0] ?? 0) * 255)
                let g = Int((cgColor.components?[1] ?? 0) * 255)
                let b = Int((cgColor.components?[2] ?? 0) * 255)
                dict["color"] = String(format: "#%02X%02X%02X", r, g, b)
            }
            dict["is_readonly"] = !cal.allowsContentModifications
            output.append(dict)
        }
        
        if let jsonData = try? JSONSerialization.data(withJSONObject: output, options: []),
           let jsonString = String(data: jsonData, encoding: .utf8) {
            print(jsonString)
        } else {
            print("[]")
        }

  meeting.list:
    description: List calendar events within a date range
    returns: meeting[]
    params:
      days: { type: integer, default: 7, description: "Days from today (1-30)" }
      past: { type: boolean, default: false, description: "Look backward instead of forward" }
      calendar_id: { type: string, description: "Filter by calendar name (partial match)" }
      query: { type: string, description: "Search title, location, or description" }
      limit: { type: integer, default: 50 }
      exclude_all_day: { type: boolean, default: false, description: "Exclude all-day events" }
    swift:
      script: |
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
            fputs("{\"error\": \"Calendar access denied. Grant in System Settings > Privacy > Calendars\"}\n", stderr)
            exit(1)
        }
        
        let args = CommandLine.arguments
        let days = args.count > 1 ? Int(args[1]) ?? 7 : 7
        let past = args.count > 2 && args[2] == "true"
        let calendarFilter = args.count > 3 && args[3] != "" ? args[3].lowercased() : nil
        let titleQuery = args.count > 4 && args[4] != "" ? args[4].lowercased() : nil
        let limit = args.count > 5 && args[5] != "" ? Int(args[5]) : nil
        let excludeAllDay = args.count > 6 && args[6] == "true"
        
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
        
        if let query = titleQuery {
            events = events.filter {
                ($0.title ?? "").lowercased().contains(query) ||
                ($0.location ?? "").lowercased().contains(query) ||
                ($0.notes ?? "").lowercased().contains(query)
            }
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
        
        var output: [[String: Any]] = []
        for event in events {
            var dict: [String: Any] = [
                "id": event.eventIdentifier ?? "",
                "title": event.title ?? "",
                "start": isoFormatter.string(from: event.startDate),
                "end": isoFormatter.string(from: event.endDate),
                "all_day": event.isAllDay
            ]
            if let location = event.location, !location.isEmpty {
                dict["location"] = location
            }
            if let notes = event.notes, !notes.isEmpty {
                dict["description"] = notes
            }
            if event.hasRecurrenceRules, let rules = event.recurrenceRules, let rule = rules.first {
                dict["recurrence"] = rule.description
            }
            output.append(dict)
        }
        
        if let jsonData = try? JSONSerialization.data(withJSONObject: output, options: []),
           let jsonString = String(data: jsonData, encoding: .utf8) {
            print(jsonString)
        } else {
            print("[]")
        }
      args:
        - "{{params.days}}"
        - "{{params.past}}"
        - "{{params.calendar_id}}"
        - "{{params.query}}"
        - "{{params.limit}}"
        - "{{params.exclude_all_day}}"

  meeting.get:
    description: Get full details of a specific event
    returns: meeting
    params:
      id: { type: string, required: true, description: "Event ID" }
    swift:
      script: |
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
            fputs("{\"error\": \"Calendar access denied\"}\n", stderr)
            exit(1)
        }
        
        let uid = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : ""
        guard !uid.isEmpty, let event = store.event(withIdentifier: uid) else {
            fputs("{\"error\": \"Event not found\"}\n", stderr)
            exit(1)
        }
        
        let isoFormatter = ISO8601DateFormatter()
        isoFormatter.formatOptions = [.withInternetDateTime]
        
        var dict: [String: Any] = [
            "id": event.eventIdentifier ?? "",
            "title": event.title ?? "",
            "start": isoFormatter.string(from: event.startDate),
            "end": isoFormatter.string(from: event.endDate),
            "all_day": event.isAllDay
        ]
        if let location = event.location, !location.isEmpty {
            dict["location"] = location
        }
        if let notes = event.notes, !notes.isEmpty {
            dict["description"] = notes
        }
        if event.hasRecurrenceRules, let rules = event.recurrenceRules {
            dict["recurrence"] = rules.map { $0.description }.joined(separator: ";")
        }
        
        if let jsonData = try? JSONSerialization.data(withJSONObject: dict, options: [.prettyPrinted]),
           let jsonString = String(data: jsonData, encoding: .utf8) {
            print(jsonString)
        }
      args:
        - "{{params.id}}"

  meeting.create:
    description: Create a new calendar event
    returns: meeting
    params:
      title: { type: string, required: true, description: "Event title" }
      start: { type: string, required: true, description: "Start (YYYY-MM-DD HH:MM or YYYY-MM-DD)" }
      end: { type: string, description: "End (defaults to 1 hour after start)" }
      all_day: { type: boolean, description: "Create as all-day event" }
      location: { type: string, description: "Event location" }
      description: { type: string, description: "Event description/notes" }
      calendar_id: { type: string, description: "Target calendar name (partial match)" }
    swift:
      script: |
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
            fputs("{\"error\": \"Calendar access denied\"}\n", stderr)
            exit(1)
        }
        
        let args = CommandLine.arguments
        guard args.count > 2 else {
            fputs("{\"error\": \"title and start required\"}\n", stderr)
            exit(1)
        }
        
        let title = args[1]
        let startStr = args[2]
        let endStr = args.count > 3 && args[3] != "" ? args[3] : ""
        let calName = args.count > 4 && args[4] != "" ? args[4] : ""
        let location = args.count > 5 && args[5] != "" ? args[5] : ""
        let notes = args.count > 6 && args[6] != "" ? args[6] : ""
        let allDay = args.count > 7 && args[7] == "true"
        
        var calendar: EKCalendar?
        if !calName.isEmpty {
            calendar = store.calendars(for: .event).first { 
                $0.title.lowercased().contains(calName.lowercased()) 
            }
        }
        if calendar == nil {
            calendar = store.defaultCalendarForNewEvents
        }
        guard let targetCalendar = calendar else {
            fputs("{\"error\": \"No calendar found\"}\n", stderr)
            exit(1)
        }
        
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone.current
        
        var startDate: Date?
        var endDate: Date?
        
        if allDay || startStr.count == 10 {
            formatter.dateFormat = "yyyy-MM-dd"
            startDate = formatter.date(from: String(startStr.prefix(10)))
            if !endStr.isEmpty {
                endDate = formatter.date(from: String(endStr.prefix(10)))
            } else {
                endDate = startDate
            }
        } else {
            formatter.dateFormat = "yyyy-MM-dd HH:mm"
            startDate = formatter.date(from: startStr)
            if !endStr.isEmpty {
                endDate = formatter.date(from: endStr)
            } else if let start = startDate {
                endDate = start.addingTimeInterval(3600)
            }
        }
        
        guard let start = startDate, let end = endDate else {
            fputs("{\"error\": \"Invalid date format\"}\n", stderr)
            exit(1)
        }
        
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
            let isoFormatter = ISO8601DateFormatter()
            isoFormatter.formatOptions = [.withInternetDateTime]
            var dict: [String: Any] = [
                "id": event.eventIdentifier ?? "",
                "title": title,
                "start": isoFormatter.string(from: start),
                "end": isoFormatter.string(from: end),
                "all_day": event.isAllDay
            ]
            if !location.isEmpty { dict["location"] = location }
            if !notes.isEmpty { dict["description"] = notes }
            if let jsonData = try? JSONSerialization.data(withJSONObject: dict, options: []),
               let jsonString = String(data: jsonData, encoding: .utf8) {
                print(jsonString)
            }
        } catch {
            fputs("{\"error\": \"\(error.localizedDescription)\"}\n", stderr)
            exit(1)
        }
      args:
        - "{{params.title}}"
        - "{{params.start}}"
        - "{{params.end}}"
        - "{{params.calendar_id}}"
        - "{{params.location}}"
        - "{{params.description}}"
        - "{{params.all_day}}"

  meeting.update:
    description: Update an existing calendar event
    returns: meeting
    params:
      id: { type: string, required: true, description: "Event ID" }
      title: { type: string, description: "New title" }
      start: { type: string, description: "New start time" }
      end: { type: string, description: "New end time" }
      location: { type: string, description: "New location" }
      description: { type: string, description: "New description" }
      calendar_id: { type: string, description: "Move to different calendar" }
    swift:
      script: |
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
            fputs("{\"error\": \"Calendar access denied\"}\n", stderr)
            exit(1)
        }
        
        let args = CommandLine.arguments
        guard args.count > 1 else {
            fputs("{\"error\": \"Event ID required\"}\n", stderr)
            exit(1)
        }
        
        let uid = args[1]
        let title = args.count > 2 && args[2] != "" ? args[2] : nil
        let startStr = args.count > 3 && args[3] != "" ? args[3] : nil
        let endStr = args.count > 4 && args[4] != "" ? args[4] : nil
        let location = args.count > 5 && args[5] != "" ? args[5] : nil
        let notes = args.count > 6 && args[6] != "" ? args[6] : nil
        let calendarName = args.count > 7 && args[7] != "" ? args[7] : nil
        
        guard let event = store.event(withIdentifier: uid) else {
            fputs("{\"error\": \"Event not found\"}\n", stderr)
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
        
        if let calName = calendarName {
            if let newCal = store.calendars(for: .event).first(where: { 
                $0.title.lowercased().contains(calName.lowercased()) 
            }) {
                event.calendar = newCal
            } else {
                fputs("{\"error\": \"Calendar not found\"}\n", stderr)
                exit(1)
            }
        }
        
        do {
            try store.save(event, span: .thisEvent)
            let isoFormatter = ISO8601DateFormatter()
            isoFormatter.formatOptions = [.withInternetDateTime]
            var dict: [String: Any] = [
                "id": event.eventIdentifier ?? uid,
                "title": event.title ?? "",
                "start": isoFormatter.string(from: event.startDate),
                "end": isoFormatter.string(from: event.endDate),
                "all_day": event.isAllDay
            ]
            if let loc = event.location, !loc.isEmpty { dict["location"] = loc }
            if let desc = event.notes, !desc.isEmpty { dict["description"] = desc }
            if let jsonData = try? JSONSerialization.data(withJSONObject: dict, options: []),
               let jsonString = String(data: jsonData, encoding: .utf8) {
                print(jsonString)
            }
        } catch {
            fputs("{\"error\": \"\(error.localizedDescription)\"}\n", stderr)
            exit(1)
        }
      args:
        - "{{params.id}}"
        - "{{params.title}}"
        - "{{params.start}}"
        - "{{params.end}}"
        - "{{params.location}}"
        - "{{params.description}}"
        - "{{params.calendar_id}}"

  meeting.delete:
    description: Delete a calendar event
    returns: void
    params:
      id: { type: string, required: true, description: "Event ID" }
    swift:
      script: |
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
            fputs("{\"error\": \"Calendar access denied\"}\n", stderr)
            exit(1)
        }
        
        let uid = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : ""
        guard !uid.isEmpty, let event = store.event(withIdentifier: uid) else {
            fputs("{\"error\": \"Event not found\"}\n", stderr)
            exit(1)
        }
        
        do {
            try store.remove(event, span: .thisEvent)
            print("{\"success\":true}")
        } catch {
            fputs("{\"error\": \"\(error.localizedDescription)\"}\n", stderr)
            exit(1)
        }
      args:
        - "{{params.id}}"
---

# Apple

Access macOS Calendar and Contacts via native APIs.

## Requirements

- **macOS only**
- **Permissions required** in System Settings → Privacy & Security:
  - Calendars → Full Access
  - Contacts → Allow

### Granting Permissions

1. Open **System Settings → Privacy & Security**
2. Click **Calendars** (or **Contacts**)
3. Enable access for the app (Cursor, Terminal, etc.)
4. Restart the app if needed

## Tools

| Tool | Implementation | Notes |
|------|----------------|-------|
| Calendar | EventKit (Swift binary) | Full CRUD, attendees, recurrence |
| Contacts | SQL reads + AppleScript writes | Full CRUD, photos |

## Why This Architecture?

### Calendar: EventKit

AppleScript calendar access is limited:
- Can't handle async permission prompts (macOS 14+)
- Recurrence rules are difficult to parse
- No attendee access
- Slow for large calendars

EventKit provides full access via a compiled Swift helper binary.

### Contacts: AppleScript

The Contacts framework (`CNContact`) has known bugs:
- `mutableCopy()` doesn't preserve notes
- Social profiles get corrupted
- Unreliable iCloud sync

AppleScript is Apple's canonical interface - changes sync reliably with iCloud.
SQLite is used for reads (fast, indexed) while AppleScript handles writes.

## Calendar Features

- List events with date range, calendar filter, search
- Get event details including attendees and recurrence
- Create events (timed or all-day)
- Update events (title, time, location, calendar)
- Delete events
- List all calendars

## Contacts Features

- Search/list contacts
- Get full contact details (all phones, emails, URLs)
- Create contacts with auto-normalization
- Update contact fields
- Delete contacts

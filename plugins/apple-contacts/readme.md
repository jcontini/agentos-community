---
id: apple-contacts
name: Apple Contacts
description: Access macOS Contacts as Person entities with multi-account support
icon: icon.png

website: https://www.apple.com/macos/
platform: macos

# No auth block = no credentials needed (local system access)
# Uses macOS permissions: Contacts

testing:
  exempt:
    cleanup: "Tests only verify list/read behavior, do not create contacts"
    create: "Write operation - modifies contacts database"
    update: "Write operation - modifies contacts database"
    delete: "Write operation - modifies contacts database"

instructions: |
  Apple Contacts connector with multi-account support (iCloud, local, work, etc.).
  
  **Requirements:**
  - macOS only
  - Grant permissions in System Settings → Privacy & Security → Contacts
  
  **Multi-Account Support:**
  macOS can have multiple contact accounts (iCloud, local, Exchange, etc.).
  
  **Always call `accounts` first** to get available accounts and find the default.
  Then use the account ID in list/search calls.
  
  Example workflow:
  1. `apple-contacts.accounts()` → Find account with `is_default: true`
  2. `person.list(source: "apple-contacts", account: "ABC-123-UUID", limit: 10)`
  
  **Performance:**
  - The `list` response includes phones, emails, urls, has_photo, organization, job_title
  - Only call `get` when you need addresses, notes, birthday, or full label info
  
  **Notes:**
  - Contact IDs can change after iCloud sync - query by name after create
  - Phone numbers are auto-normalized: 5125551234 → +15125551234

# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  person:
    terminology: Contact
    mapping:
      id: .id
      name: '.display_name // (.first_name + " " + .last_name) // .organization'
      first_name: .first_name
      last_name: .last_name
      middle_name: .middle_name
      nickname: .nickname
      phone: '.phones | if type == "string" then split(",")[0] else null end'
      email: '.emails | if type == "string" then split(",")[0] else null end'
      avatar: 'if .has_photo == 1 then "contacts://photo/" + .id else null end'
      organization: .organization
      job_title: .job_title
      department: .department
      birthday: .birthday
      notes: .notes
      
      # Raw arrays for building accounts
      _phones_raw: .phones
      _emails_raw: .emails

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  person.list:
    description: List contacts from a specific account with optional filtering
    returns: person[]
    params:
      account: { type: string, required: true, description: "Account ID from accounts utility" }
      query: { type: string, description: "Search by name, email, phone, or organization" }
      organization: { type: string, description: "Filter by organization" }
      sort: { type: string, default: "modified", description: "Sort by: modified (default), created, name" }
      limit: { type: integer, default: 50 }
    sql:
      database: '"~/Library/Application Support/AddressBook/Sources/" + .params.account + "/AddressBook-v22.abcddb"'
      query: |
        SELECT 
          r.ZUNIQUEID as id,
          r.ZFIRSTNAME as first_name,
          r.ZLASTNAME as last_name,
          r.ZMIDDLENAME as middle_name,
          r.ZNICKNAME as nickname,
          r.ZORGANIZATION as organization,
          r.ZJOBTITLE as job_title,
          r.ZDEPARTMENT as department,
          COALESCE(r.ZFIRSTNAME || ' ' || r.ZLASTNAME, r.ZORGANIZATION, r.ZFIRSTNAME, r.ZLASTNAME) as display_name,
          date(r.ZBIRTHDAY + 978307200, 'unixepoch') as birthday,
          datetime(r.ZMODIFICATIONDATE + 978307200, 'unixepoch') as modified_at,
          datetime(r.ZCREATIONDATE + 978307200, 'unixepoch') as created_at,
          CASE WHEN r.ZTHUMBNAILIMAGEDATA IS NOT NULL THEN 1 ELSE 0 END as has_photo,
          GROUP_CONCAT(DISTINCT p.ZFULLNUMBER) as phones,
          GROUP_CONCAT(DISTINCT e.ZADDRESS) as emails,
          GROUP_CONCAT(DISTINCT u.ZURL) as urls
        FROM ZABCDRECORD r
        LEFT JOIN ZABCDPHONENUMBER p ON p.ZOWNER = r.Z_PK
        LEFT JOIN ZABCDEMAILADDRESS e ON e.ZOWNER = r.Z_PK
        LEFT JOIN ZABCDURLADDRESS u ON u.ZOWNER = r.Z_PK
        WHERE r.ZUNIQUEID LIKE '%:ABPerson'
        GROUP BY r.Z_PK
        ORDER BY r.ZMODIFICATIONDATE DESC
        LIMIT 50

  person.get:
    description: Get full contact details by ID including addresses, notes, birthday
    returns: person
    params:
      id: { type: string, required: true, description: "Contact ID (ZUNIQUEID)" }
    applescript:
      script: |
        set contactId to "{{params.id}}"
        if contactId does not end with ":ABPerson" then
          set contactId to contactId & ":ABPerson"
        end if
        
        tell application "Contacts"
          try
            set p to person id contactId
            
            set pFirst to first name of p
            set pLast to last name of p
            set pMiddle to middle name of p
            set pNick to nickname of p
            set pOrg to organization of p
            set pJob to job title of p
            set pDept to department of p
            set pNote to note of p
            set pBday to birth date of p
            set pImage to image of p
            
            if pFirst is missing value then set pFirst to ""
            if pLast is missing value then set pLast to ""
            if pMiddle is missing value then set pMiddle to ""
            if pNick is missing value then set pNick to ""
            if pOrg is missing value then set pOrg to ""
            if pJob is missing value then set pJob to ""
            if pDept is missing value then set pDept to ""
            if pNote is missing value then set pNote to ""
            
            set hasPhoto to "false"
            if pImage is not missing value then set hasPhoto to "true"
            
            set bdayStr to ""
            if pBday is not missing value then
              set bdayStr to (year of pBday as string) & "-" & text -2 thru -1 of ("0" & ((month of pBday) as integer)) & "-" & text -2 thru -1 of ("0" & (day of pBday))
            end if
            
            set displayName to ""
            if pFirst is not "" then set displayName to pFirst
            if pLast is not "" then
              if displayName is not "" then set displayName to displayName & " "
              set displayName to displayName & pLast
            end if
            if displayName is "" and pOrg is not "" then set displayName to pOrg
            
            -- Build phones array
            set phoneList to ""
            repeat with ph in phones of p
              if phoneList is not "" then set phoneList to phoneList & ","
              set phoneList to phoneList & "{\"label\":\"" & label of ph & "\",\"value\":\"" & value of ph & "\"}"
            end repeat
            
            -- Build emails array
            set emailList to ""
            repeat with em in emails of p
              if emailList is not "" then set emailList to emailList & ","
              set emailList to emailList & "{\"label\":\"" & label of em & "\",\"value\":\"" & value of em & "\"}"
            end repeat
            
            -- Build URLs array
            set urlList to ""
            repeat with u in urls of p
              if urlList is not "" then set urlList to urlList & ","
              set urlList to urlList & "{\"label\":\"" & label of u & "\",\"value\":\"" & value of u & "\"}"
            end repeat
            
            -- Build addresses array
            set addrList to ""
            repeat with a in addresses of p
              if addrList is not "" then set addrList to addrList & ","
              set aLabel to label of a
              set aStreet to street of a
              set aCity to city of a
              set aState to state of a
              set aZip to zip of a
              set aCountry to country of a
              if aLabel is missing value then set aLabel to ""
              if aStreet is missing value then set aStreet to ""
              if aCity is missing value then set aCity to ""
              if aState is missing value then set aState to ""
              if aZip is missing value then set aZip to ""
              if aCountry is missing value then set aCountry to ""
              set addrList to addrList & "{\"label\":\"" & aLabel & "\",\"street\":\"" & aStreet & "\",\"city\":\"" & aCity & "\",\"state\":\"" & aState & "\",\"postal_code\":\"" & aZip & "\",\"country\":\"" & aCountry & "\"}"
            end repeat
            
            set output to "{"
            set output to output & "\"id\":\"" & id of p & "\","
            set output to output & "\"first_name\":\"" & pFirst & "\","
            set output to output & "\"last_name\":\"" & pLast & "\","
            set output to output & "\"middle_name\":\"" & pMiddle & "\","
            set output to output & "\"nickname\":\"" & pNick & "\","
            set output to output & "\"display_name\":\"" & displayName & "\","
            set output to output & "\"organization\":\"" & pOrg & "\","
            set output to output & "\"job_title\":\"" & pJob & "\","
            set output to output & "\"department\":\"" & pDept & "\","
            set output to output & "\"birthday\":\"" & bdayStr & "\","
            set output to output & "\"notes\":\"" & pNote & "\","
            set output to output & "\"has_photo\":" & hasPhoto & ","
            set output to output & "\"phones\":[" & phoneList & "],"
            set output to output & "\"emails\":[" & emailList & "],"
            set output to output & "\"urls\":[" & urlList & "],"
            set output to output & "\"addresses\":[" & addrList & "]"
            set output to output & "}"
            
            return output
          on error errMsg
            return "{\"error\":\"" & errMsg & "\"}"
          end try
        end tell

  person.search:
    description: Search contacts by any text within a specific account
    returns: person[]
    params:
      account: { type: string, required: true, description: "Account ID from accounts utility" }
      query: { type: string, required: true, description: "Search text" }
      limit: { type: integer, default: 50 }
    sql:
      database: '"~/Library/Application Support/AddressBook/Sources/" + .params.account + "/AddressBook-v22.abcddb"'
      query: |
        SELECT DISTINCT
          r.ZUNIQUEID as id,
          r.ZFIRSTNAME as first_name,
          r.ZLASTNAME as last_name,
          r.ZMIDDLENAME as middle_name,
          r.ZNICKNAME as nickname,
          r.ZORGANIZATION as organization,
          r.ZJOBTITLE as job_title,
          r.ZDEPARTMENT as department,
          COALESCE(r.ZFIRSTNAME || ' ' || r.ZLASTNAME, r.ZORGANIZATION) as display_name,
          date(r.ZBIRTHDAY + 978307200, 'unixepoch') as birthday,
          CASE WHEN r.ZTHUMBNAILIMAGEDATA IS NOT NULL THEN 1 ELSE 0 END as has_photo,
          GROUP_CONCAT(DISTINCT p.ZFULLNUMBER) as phones,
          GROUP_CONCAT(DISTINCT e.ZADDRESS) as emails
        FROM ZABCDRECORD r
        LEFT JOIN ZABCDPHONENUMBER p ON p.ZOWNER = r.Z_PK
        LEFT JOIN ZABCDEMAILADDRESS e ON e.ZOWNER = r.Z_PK
        WHERE r.ZUNIQUEID LIKE '%:ABPerson'
          AND (
            r.ZFIRSTNAME LIKE '%' || :query || '%'
            OR r.ZLASTNAME LIKE '%' || :query || '%'
            OR r.ZORGANIZATION LIKE '%' || :query || '%'
            OR p.ZFULLNUMBER LIKE '%' || :query || '%'
            OR e.ZADDRESS LIKE '%' || :query || '%'
          )
        GROUP BY r.Z_PK
        ORDER BY COALESCE(r.ZLASTNAME, r.ZFIRSTNAME, r.ZORGANIZATION)
        LIMIT :limit
      params:
        query: .params.query
        limit: '.params.limit // 50'

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

utilities:
  accounts:
    operation: read
    label: "List accounts"
    description: List available contact accounts/containers (iCloud, local, work, etc.)
    returns:
      id: string
      name: string
      count: integer
      is_default: boolean
    swift:
      script: |
        import Contacts
        import Foundation
        
        let store = CNContactStore()
        let semaphore = DispatchSemaphore(value: 0)
        var accessGranted = false
        
        store.requestAccess(for: .contacts) { granted, _ in
            accessGranted = granted
            semaphore.signal()
        }
        semaphore.wait()
        
        guard accessGranted else {
            fputs("{\"error\": \"Contacts access denied. Grant in System Settings > Privacy > Contacts\"}\n", stderr)
            exit(1)
        }
        
        let defaultId = store.defaultContainerIdentifier()
        let containers = try! store.containers(matching: nil)
        var results: [[String: Any]] = []
        
        for c in containers {
            let pred = CNContact.predicateForContactsInContainer(withIdentifier: c.identifier)
            let count = try! store.unifiedContacts(matching: pred, keysToFetch: []).count
            // Strip :ABAccount suffix to match directory names in AddressBook/Sources/
            let dirId = c.identifier.replacingOccurrences(of: ":ABAccount", with: "")
            let defaultDirId = defaultId.replacingOccurrences(of: ":ABAccount", with: "")
            results.append([
                "id": dirId,
                "name": c.name,
                "count": count,
                "is_default": dirId == defaultDirId
            ])
        }
        
        if let jsonData = try? JSONSerialization.data(withJSONObject: results, options: []),
           let jsonString = String(data: jsonData, encoding: .utf8) {
            print(jsonString)
        } else {
            print("[]")
        }

  create:
    operation: create
    label: "Create contact"
    description: Create a new contact in a specific account
    returns:
      id: string
      display_name: string
      status: string
    params:
      account: { type: string, required: true, description: "Account ID to create contact in" }
      first_name: { type: string, description: "First name" }
      last_name: { type: string, description: "Last name" }
      organization: { type: string, description: "Organization" }
      job_title: { type: string, description: "Job title" }
      phones: { type: array, description: "Phones [{label, value}]" }
      emails: { type: array, description: "Emails [{label, value}]" }
    applescript:
      script: |
        tell application "Contacts"
          set props to {}
          
          if "{{params.first_name}}" is not "" then set props to props & {first name:"{{params.first_name}}"}
          if "{{params.last_name}}" is not "" then set props to props & {last name:"{{params.last_name}}"}
          if "{{params.organization}}" is not "" then set props to props & {organization:"{{params.organization}}"}
          if "{{params.job_title}}" is not "" then set props to props & {job title:"{{params.job_title}}"}
          
          set newPerson to make new person with properties props
          
          -- Add phones from array
          {{#each params.phones}}
          make new phone at end of phones of newPerson with properties {label:"{{this.label | default: mobile}}", value:"{{this.value}}"}
          {{/each}}
          
          -- Add emails from array
          {{#each params.emails}}
          make new email at end of emails of newPerson with properties {label:"{{this.label | default: home}}", value:"{{this.value}}"}
          {{/each}}
          
          save
          
          set newId to id of newPerson
          set displayName to ""
          if first name of newPerson is not missing value then set displayName to first name of newPerson
          if last name of newPerson is not missing value then set displayName to displayName & " " & last name of newPerson
          if displayName is "" and organization of newPerson is not missing value then set displayName to organization of newPerson
          
          return "{\"id\":\"" & newId & "\",\"display_name\":\"" & displayName & "\",\"status\":\"created\"}"
        end tell

  update:
    operation: update
    label: "Update contact"
    description: Update scalar fields on a contact
    returns:
      id: string
      status: string
    params:
      id: { type: string, required: true, description: "Contact ID" }
      first_name: { type: string, description: "First name" }
      last_name: { type: string, description: "Last name" }
      organization: { type: string, description: "Organization" }
      job_title: { type: string, description: "Job title" }
    applescript:
      script: |
        set contactId to "{{params.id}}"
        if contactId does not end with ":ABPerson" then
          set contactId to contactId & ":ABPerson"
        end if
        
        tell application "Contacts"
          try
            set p to person id contactId
            
            if "{{params.first_name}}" is not "" then set first name of p to "{{params.first_name}}"
            if "{{params.last_name}}" is not "" then set last name of p to "{{params.last_name}}"
            if "{{params.organization}}" is not "" then set organization of p to "{{params.organization}}"
            if "{{params.job_title}}" is not "" then set job title of p to "{{params.job_title}}"
            
            save
            return "{\"id\":\"" & id of p & "\",\"status\":\"updated\"}"
          on error errMsg
            return "{\"error\":\"" & errMsg & "\"}"
          end try
        end tell

  delete:
    operation: delete
    label: "Delete contact"
    description: Delete a contact
    returns:
      status: string
      name: string
    params:
      id: { type: string, required: true, description: "Contact ID" }
    applescript:
      script: |
        set contactId to "{{params.id}}"
        if contactId does not end with ":ABPerson" then
          set contactId to contactId & ":ABPerson"
        end if
        
        tell application "Contacts"
          try
            set p to person id contactId
            set pName to ""
            if first name of p is not missing value then set pName to first name of p
            if last name of p is not missing value then set pName to pName & " " & last name of p
            delete p
            save
            return "{\"status\":\"deleted\",\"name\":\"" & pName & "\"}"
          on error errMsg
            return "{\"error\":\"" & errMsg & "\"}"
          end try
        end tell

---

# Apple Contacts

Access macOS Contacts as Person entities with multi-account support.

## Requirements

- **macOS only**
- **Permissions required** in System Settings → Privacy & Security → Contacts

## Multi-Account Support

macOS can have multiple contact accounts (iCloud, local, Exchange, etc.). Use the `accounts` utility to list available accounts and find the default one.

### Example Workflow

```
1. apple-contacts.accounts()  
   → Returns: [{id: "ABC-123", name: "iCloud", count: 500, is_default: true}, ...]

2. person.list(source: "apple-contacts", account: "ABC-123", limit: 10)
   → Returns: 10 most recently modified contacts as person entities
```

## Operations

| Operation | Description |
|-----------|-------------|
| `person.list` | List contacts with phones, emails, organization |
| `person.get` | Get full details: addresses, notes, birthday |
| `person.search` | Search contacts by name, email, phone, organization |

## Utilities

| Utility | Description |
|---------|-------------|
| `accounts` | List contact accounts (iCloud, local, work) |
| `create` | Create new contact |
| `update` | Update contact fields |
| `delete` | Delete contact |

## Architecture

| Operation | Executor | Notes |
|-----------|----------|-------|
| accounts | Swift (CNContactStore) | Lists contact containers |
| list/search | SQL | Fast indexed queries on AddressBook DB |
| get | AppleScript | Full details with arrays |
| create/update/delete | AppleScript | Reliable iCloud sync |

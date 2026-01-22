---
id: apple-contacts
name: Apple Contacts
description: Access macOS Contacts via native APIs with multi-account support
icon: icon.png
color: "#000000"
tags: [contacts, people, address-book]

website: https://www.apple.com/macos/
platform: macos

# No auth block = no credentials needed (local system access)
# Uses macOS permissions: Contacts

testing:
  exempt:
    cleanup: "Tests only verify list/read behavior, do not create contacts"

instructions: |
  Apple Contacts connector with multi-account support (iCloud, local, work, etc.).
  
  **Requirements:**
  - macOS only
  - Grant permissions in System Settings → Privacy & Security → Contacts
  
  **Multi-Account Support:**
  macOS can have multiple contact accounts (iCloud, local, Exchange, etc.).
  
  **Always call `accounts` first** to get available accounts and find the default.
  Then use the account ID in list/search/create calls.
  
  Example workflow:
  1. `Contacts.accounts()` → Find account with `is_default: true`
  2. `Contacts.list(account: "ABC-123-UUID", limit: 10)`
  3. `Contacts.create(account: "ABC-123-UUID", first_name: "John", ...)`
  
  **Performance:**
  - The `list` response includes phones, emails, urls, has_photo, organization, job_title
  - Only call `get` when you need addresses, notes, birthday, or full label info
  - Phones/emails/urls in list are comma-separated strings (use `get` for label details)
  - Each tool call adds latency, so use list data first before calling get
  
  **Notes:**
  - Contact IDs can change after iCloud sync - query by name after create
  - Phone numbers are auto-normalized: 5125551234 → +15125551234
  - URL labels are auto-detected: github.com → "GitHub"

# Action implementations
actions:
  accounts:
    operation: read
    label: "List accounts"
    description: List available contact accounts/containers (iCloud, local, work, etc.)
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
      response:
        mapping:
          id: "[].id"
          name: "[].name"
          count: "[].count"
          is_default: "[].is_default"
          connector: "'apple-contacts'"

  list:
    operation: read
    label: "List contacts"
    description: List contacts from a specific account with optional filtering and sorting
    params:
      account: { type: string, required: true, description: "Account ID from accounts action" }
      query: { type: string, description: "Search by name, email, phone, or organization" }
      organization: { type: string, description: "Filter by organization" }
      sort: { type: string, default: "modified", description: "Sort by: modified (default), created, name" }
      limit: { type: number, default: 50 }
    sql:
      database: "~/Library/Application Support/AddressBook/Sources/{{params.account}}/AddressBook-v22.abcddb"
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
          AND (
            '{{params.query}}' = '' 
            OR r.ZFIRSTNAME LIKE '%{{params.query}}%'
            OR r.ZLASTNAME LIKE '%{{params.query}}%'
            OR r.ZORGANIZATION LIKE '%{{params.query}}%'
          )
          AND (
            '{{params.organization}}' = ''
            OR r.ZORGANIZATION LIKE '%{{params.organization}}%'
          )
        GROUP BY r.Z_PK
        ORDER BY 
          CASE '{{params.sort | default: modified}}'
            WHEN 'modified' THEN r.ZMODIFICATIONDATE
            WHEN 'created' THEN r.ZCREATIONDATE
            ELSE NULL
          END DESC,
          CASE WHEN '{{params.sort | default: modified}}' NOT IN ('modified', 'created') THEN COALESCE(r.ZLASTNAME, r.ZFIRSTNAME, r.ZORGANIZATION) END
        LIMIT {{params.limit | default: 50}}
      response:
        mapping:
          id: "[].id"
          first_name: "[].first_name"
          last_name: "[].last_name"
          middle_name: "[].middle_name"
          nickname: "[].nickname"
          organization: "[].organization"
          job_title: "[].job_title"
          department: "[].department"
          display_name: "[].display_name"
          modified_at: "[].modified_at"
          created_at: "[].created_at"
          has_photo: "[].has_photo"
          phones: "[].phones"
          emails: "[].emails"
          urls: "[].urls"
          connector: "'apple-contacts'"

  search:
    operation: read
    label: "Search contacts"
    description: Search contacts by any text within a specific account
    params:
      account: { type: string, required: true, description: "Account ID from accounts action" }
      query: { type: string, required: true, description: "Search text" }
      limit: { type: number, default: 50 }
    sql:
      database: "~/Library/Application Support/AddressBook/Sources/{{params.account}}/AddressBook-v22.abcddb"
      query: |
        SELECT DISTINCT
          r.ZUNIQUEID as id,
          r.ZFIRSTNAME as first_name,
          r.ZLASTNAME as last_name,
          r.ZORGANIZATION as organization,
          r.ZJOBTITLE as job_title,
          COALESCE(r.ZFIRSTNAME || ' ' || r.ZLASTNAME, r.ZORGANIZATION) as display_name,
          CASE WHEN r.ZTHUMBNAILIMAGEDATA IS NOT NULL THEN 1 ELSE 0 END as has_photo
        FROM ZABCDRECORD r
        LEFT JOIN ZABCDPHONENUMBER p ON p.ZOWNER = r.Z_PK
        LEFT JOIN ZABCDEMAILADDRESS e ON e.ZOWNER = r.Z_PK
        WHERE r.ZUNIQUEID LIKE '%:ABPerson'
          AND (
            r.ZFIRSTNAME LIKE '%{{params.query}}%'
            OR r.ZLASTNAME LIKE '%{{params.query}}%'
            OR r.ZORGANIZATION LIKE '%{{params.query}}%'
            OR p.ZFULLNUMBER LIKE '%{{params.query}}%'
            OR e.ZADDRESS LIKE '%{{params.query}}%'
          )
        ORDER BY COALESCE(r.ZLASTNAME, r.ZFIRSTNAME, r.ZORGANIZATION)
        LIMIT {{params.limit | default: 50}}
      response:
        mapping:
          id: "[].id"
          first_name: "[].first_name"
          last_name: "[].last_name"
          organization: "[].organization"
          job_title: "[].job_title"
          display_name: "[].display_name"
          has_photo: "[].has_photo"
          connector: "'apple-contacts'"

  get:
    operation: read
    label: "Get contact"
    description: Get full contact details by ID including has_photo field
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
            set output to output & "\"organization\":\"" & pOrg & "\","
            set output to output & "\"job_title\":\"" & pJob & "\","
            set output to output & "\"department\":\"" & pDept & "\","
            set output to output & "\"birthday\":\"" & bdayStr & "\","
            set output to output & "\"notes\":\"" & pNote & "\","
            set output to output & "\"has_photo\":" & hasPhoto & ","
            set output to output & "\"phones\":[" & phoneList & "],"
            set output to output & "\"emails\":[" & emailList & "],"
            set output to output & "\"urls\":[" & urlList & "],"
            set output to output & "\"addresses\":[" & addrList & "],"
            set output to output & "\"connector\":\"apple-contacts\""
            set output to output & "}"
            
            return output
          on error errMsg
            return "{\"error\":\"" & errMsg & "\"}"
          end try
        end tell
      response:
        mapping:
          id: ".id"
          first_name: ".first_name"
          last_name: ".last_name"
          middle_name: ".middle_name"
          nickname: ".nickname"
          organization: ".organization"
          job_title: ".job_title"
          department: ".department"
          birthday: ".birthday"
          notes: ".notes"
          has_photo: ".has_photo"
          phones: ".phones"
          emails: ".emails"
          urls: ".urls"
          addresses: ".addresses"
          connector: ".connector"

  create:
    operation: create
    label: "Create contact"
    description: Create a new contact in a specific account
    params:
      account: { type: string, required: true, description: "Account ID to create contact in" }
      first_name: { type: string, description: "First name" }
      last_name: { type: string, description: "Last name" }
      middle_name: { type: string, description: "Middle name" }
      nickname: { type: string, description: "Nickname" }
      organization: { type: string, description: "Organization" }
      job_title: { type: string, description: "Job title" }
      department: { type: string, description: "Department" }
      birthday: { type: string, description: "Birthday (YYYY-MM-DD)" }
      notes: { type: string, description: "Notes" }
      phones: { type: array, description: "Phones [{label, value}]" }
      emails: { type: array, description: "Emails [{label, value}]" }
      urls: { type: array, description: "URLs [{label, value}]" }
      addresses: { type: array, description: "Addresses [{label, street, city, state, postal_code, country}]" }
    applescript:
      script: |
        tell application "Contacts"
          set props to {}
          
          if "{{params.first_name}}" is not "" then set props to props & {first name:"{{params.first_name}}"}
          if "{{params.last_name}}" is not "" then set props to props & {last name:"{{params.last_name}}"}
          if "{{params.middle_name}}" is not "" then set props to props & {middle name:"{{params.middle_name}}"}
          if "{{params.nickname}}" is not "" then set props to props & {nickname:"{{params.nickname}}"}
          if "{{params.organization}}" is not "" then set props to props & {organization:"{{params.organization}}"}
          if "{{params.job_title}}" is not "" then set props to props & {job title:"{{params.job_title}}"}
          if "{{params.department}}" is not "" then set props to props & {department:"{{params.department}}"}
          if "{{params.notes}}" is not "" then set props to props & {note:"{{params.notes}}"}
          
          set newPerson to make new person with properties props
          
          -- Add phones from array
          {{#each params.phones}}
          make new phone at end of phones of newPerson with properties {label:"{{this.label | default: mobile}}", value:"{{this.value}}"}
          {{/each}}
          
          -- Add emails from array
          {{#each params.emails}}
          make new email at end of emails of newPerson with properties {label:"{{this.label | default: home}}", value:"{{this.value}}"}
          {{/each}}
          
          -- Add URLs from array
          {{#each params.urls}}
          make new url at end of urls of newPerson with properties {label:"{{this.label | default: homepage}}", value:"{{this.value}}"}
          {{/each}}
          
          -- Add addresses from array
          {{#each params.addresses}}
          make new address at end of addresses of newPerson with properties {label:"{{this.label | default: home}}", street:"{{this.street}}", city:"{{this.city}}", state:"{{this.state}}", zip:"{{this.postal_code}}", country:"{{this.country}}"}
          {{/each}}
          
          save
          
          set newId to id of newPerson
          set displayName to ""
          if first name of newPerson is not missing value then set displayName to first name of newPerson
          if last name of newPerson is not missing value then set displayName to displayName & " " & last name of newPerson
          if displayName is "" and organization of newPerson is not missing value then set displayName to organization of newPerson
          
          return "{\"id\":\"" & newId & "\",\"display_name\":\"" & displayName & "\",\"status\":\"created\",\"connector\":\"apple-contacts\"}"
        end tell
      response:
        mapping:
          id: ".id"
          display_name: ".display_name"
          status: ".status"
          connector: ".connector"

  update:
    operation: update
    label: "Update contact"
    description: Update scalar fields on a contact
    params:
      id: { type: string, required: true, description: "Contact ID" }
      first_name: { type: string, description: "First name" }
      last_name: { type: string, description: "Last name" }
      middle_name: { type: string, description: "Middle name" }
      nickname: { type: string, description: "Nickname" }
      organization: { type: string, description: "Organization" }
      job_title: { type: string, description: "Job title" }
      department: { type: string, description: "Department" }
      birthday: { type: string, description: "Birthday (YYYY-MM-DD)" }
      notes: { type: string, description: "Notes" }
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
            if "{{params.middle_name}}" is not "" then set middle name of p to "{{params.middle_name}}"
            if "{{params.nickname}}" is not "" then set nickname of p to "{{params.nickname}}"
            if "{{params.organization}}" is not "" then set organization of p to "{{params.organization}}"
            if "{{params.job_title}}" is not "" then set job title of p to "{{params.job_title}}"
            if "{{params.department}}" is not "" then set department of p to "{{params.department}}"
            if "{{params.notes}}" is not "" then set note of p to "{{params.notes}}"
            
            save
            return "{\"id\":\"" & id of p & "\",\"status\":\"updated\",\"connector\":\"apple-contacts\"}"
          on error errMsg
            return "{\"error\":\"" & errMsg & "\"}"
          end try
        end tell
      response:
        mapping:
          id: ".id"
          status: ".status"
          connector: ".connector"

  add:
    operation: update
    label: "Add to contact"
    description: Add items to array fields (emails, phones, urls, addresses)
    params:
      id: { type: string, required: true, description: "Contact ID" }
      emails: { type: object, description: "Email to add {label?, value}" }
      phones: { type: object, description: "Phone to add {label?, value}" }
      urls: { type: object, description: "URL to add {label?, value}" }
      addresses: { type: object, description: "Address to add {label?, street?, city?, state?, postal_code?, country?}" }
    applescript:
      script: |
        set contactId to "{{params.id}}"
        if contactId does not end with ":ABPerson" then
          set contactId to contactId & ":ABPerson"
        end if
        
        tell application "Contacts"
          try
            set p to person id contactId
            set addedItems to ""
            
            -- Add email if provided
            if "{{params.emails.value}}" is not "" then
              make new email at end of emails of p with properties {label:"{{params.emails.label | default: home}}", value:"{{params.emails.value}}"}
              set addedItems to addedItems & "email,"
            end if
            
            -- Add phone if provided
            if "{{params.phones.value}}" is not "" then
              make new phone at end of phones of p with properties {label:"{{params.phones.label | default: mobile}}", value:"{{params.phones.value}}"}
              set addedItems to addedItems & "phone,"
            end if
            
            -- Add URL if provided
            if "{{params.urls.value}}" is not "" then
              make new url at end of urls of p with properties {label:"{{params.urls.label | default: homepage}}", value:"{{params.urls.value}}"}
              set addedItems to addedItems & "url,"
            end if
            
            -- Add address if provided
            if "{{params.addresses.label}}" is not "" or "{{params.addresses.street}}" is not "" then
              make new address at end of addresses of p with properties {label:"{{params.addresses.label | default: home}}", street:"{{params.addresses.street}}", city:"{{params.addresses.city}}", state:"{{params.addresses.state}}", zip:"{{params.addresses.postal_code}}", country:"{{params.addresses.country}}"}
              set addedItems to addedItems & "address,"
            end if
            
            save
            return "{\"id\":\"" & id of p & "\",\"status\":\"added\",\"added\":\"" & addedItems & "\",\"connector\":\"apple-contacts\"}"
          on error errMsg
            return "{\"error\":\"" & errMsg & "\"}"
          end try
        end tell
      response:
        mapping:
          id: ".id"
          status: ".status"
          added: ".added"
          connector: ".connector"

  remove:
    operation: update
    label: "Remove from contact"
    description: Remove items from array fields by matching value
    params:
      id: { type: string, required: true, description: "Contact ID" }
      emails: { type: object, description: "Email to remove {value}" }
      phones: { type: object, description: "Phone to remove {value}" }
      urls: { type: object, description: "URL to remove {value}" }
      addresses: { type: object, description: "Address to remove {label}" }
    applescript:
      script: |
        set contactId to "{{params.id}}"
        if contactId does not end with ":ABPerson" then
          set contactId to contactId & ":ABPerson"
        end if
        
        tell application "Contacts"
          try
            set p to person id contactId
            set removedItems to ""
            set targetEmail to "{{params.emails.value}}"
            set targetPhone to "{{params.phones.value}}"
            set targetUrl to "{{params.urls.value}}"
            set targetAddrLabel to "{{params.addresses.label}}"
            
            -- Remove email by value
            if targetEmail is not "" then
              set emailList to emails of p
              repeat with i from (count of emailList) to 1 by -1
                set em to item i of emailList
                if value of em is targetEmail then
                  delete em
                  set removedItems to removedItems & "email,"
                  exit repeat
                end if
              end repeat
            end if
            
            -- Remove phone by value
            if targetPhone is not "" then
              set phoneList to phones of p
              repeat with i from (count of phoneList) to 1 by -1
                set ph to item i of phoneList
                if value of ph is targetPhone then
                  delete ph
                  set removedItems to removedItems & "phone,"
                  exit repeat
                end if
              end repeat
            end if
            
            -- Remove URL by value
            if targetUrl is not "" then
              set urlList to urls of p
              repeat with i from (count of urlList) to 1 by -1
                set u to item i of urlList
                if value of u is targetUrl then
                  delete u
                  set removedItems to removedItems & "url,"
                  exit repeat
                end if
              end repeat
            end if
            
            -- Remove address by label
            if targetAddrLabel is not "" then
              set addrList to addresses of p
              repeat with i from (count of addrList) to 1 by -1
                set a to item i of addrList
                if label of a is targetAddrLabel then
                  delete a
                  set removedItems to removedItems & "address,"
                  exit repeat
                end if
              end repeat
            end if
            
            save
            
            set pId to id of p
            return "{\"id\":\"" & pId & "\",\"status\":\"removed\",\"removed\":\"" & removedItems & "\",\"connector\":\"apple-contacts\"}"
          on error errMsg
            return "{\"error\":\"" & errMsg & "\"}"
          end try
        end tell
      response:
        mapping:
          id: ".id"
          status: ".status"
          removed: ".removed"
          connector: ".connector"

  delete:
    operation: delete
    label: "Delete contact"
    description: Delete a contact
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
            return "{\"status\":\"deleted\",\"name\":\"" & pName & "\",\"connector\":\"apple-contacts\"}"
          on error errMsg
            return "{\"error\":\"" & errMsg & "\"}"
          end try
        end tell
      response:
        mapping:
          status: ".status"
          name: ".name"
          connector: ".connector"

  set_photo:
    operation: update
    label: "Set contact photo"
    description: Set a contact's photo from a local file path
    params:
      id: { type: string, required: true, description: "Contact ID" }
      path: { type: string, required: true, description: "Local file path to image (JPEG, PNG)" }
    applescript:
      script: |
        set contactId to "{{params.id}}"
        if contactId does not end with ":ABPerson" then
          set contactId to contactId & ":ABPerson"
        end if
        
        tell application "Contacts"
          try
            set p to person id contactId
            set image of p to (read (POSIX file "{{params.path}}") as JPEG picture)
            save
            return "{\"id\":\"" & id of p & "\",\"status\":\"photo_set\",\"connector\":\"apple-contacts\"}"
          on error errMsg
            return "{\"error\":\"" & errMsg & "\"}"
          end try
        end tell
      response:
        mapping:
          id: ".id"
          status: ".status"
          connector: ".connector"

  clear_photo:
    operation: update
    label: "Clear contact photo"
    description: Remove a contact's photo
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
            delete image of p
            save
            return "{\"id\":\"" & id of p & "\",\"status\":\"photo_cleared\",\"connector\":\"apple-contacts\"}"
          on error errMsg
            return "{\"error\":\"" & errMsg & "\"}"
          end try
        end tell
      response:
        mapping:
          id: ".id"
          status: ".status"
          connector: ".connector"
---

# Apple Contacts

Access macOS Contacts via native APIs with multi-account support.

## ⚡ IMPORTANT: Use `list` First, Avoid Unnecessary `get` Calls

**The `list` action returns phones, emails, urls, has_photo, organization, job_title.**

Each tool call adds latency. Don't call `get` on every contact just to check phone numbers — that data is already in the `list` response!

### list response includes:
```json
{
  "id": "ABC-123:ABPerson",
  "display_name": "Jane Smith",
  "first_name": "Jane",
  "last_name": "Smith",
  "organization": "Acme Corp",
  "job_title": "Engineer",
  "has_photo": 1,
  "phones": "+15125551234,+15129876543",
  "emails": "jane@acme.com,jane@gmail.com",
  "urls": "https://linkedin.com/in/jane",
  "modified_at": "2026-01-11 12:00:00"
}
```

### Only call `get` when you need:
- **addresses** (street, city, state, postal_code, country)
- **notes**
- **birthday**
- **label details** (phones/emails in list are values only, get returns label+value pairs)

### Example: Find contacts without photos who have phone numbers
```
# ✅ GOOD: One list call, filter in memory
contacts = Contacts.list(account: "...", limit: 50)
no_photo_with_phone = [c for c in contacts if not c.has_photo and c.phones]

# ❌ BAD: Calling get on each contact
contacts = Contacts.list(...)
for c in contacts:
    details = Contacts.get(id: c.id)  # Unnecessary! phones already in list
```

---

## Requirements

- **macOS only**
- **Permissions required** in System Settings → Privacy & Security → Contacts

### Granting Permissions

1. Open **System Settings → Privacy & Security**
2. Click **Contacts**
3. Enable access for the app (Cursor, Terminal, etc.)
4. Restart the app if needed

## Multi-Account Support

macOS can have multiple contact accounts (iCloud, local, Exchange, etc.). Use the `accounts` action to list available accounts and find the default one.

### Example Workflow

```
1. Contacts.accounts()  
   → Returns: [{id: "ABC-123", name: "iCloud", count: 500, is_default: true}, ...]

2. Contacts.list(account: "ABC-123", limit: 10)
   → Returns: 10 most recently modified contacts with phones, emails, urls included

3. Contacts.get(id: "ABC-123:ABPerson")
   → Only if you need addresses, notes, or birthday
```

## Features

- **accounts** - List available contact accounts (iCloud, local, work, etc.)
- **list** - List contacts with phones, emails, urls, has_photo (use this first!)
- **search** - Search contacts by name, email, phone, or organization
- **get** - Get full details: addresses, notes, birthday, label info
- **create** - Create new contacts in specific account
- **update** - Update contact scalar fields
- **add/remove** - Add or remove emails, phones, URLs, addresses
- **delete** - Delete contacts
- **set_photo** - Set contact photo from file path
- **clear_photo** - Remove contact photo

## Architecture

| Action | Executor | Notes |
|--------|----------|-------|
| accounts | Swift (CNContactStore) | Lists contact containers |
| list/search | SQL | Fast indexed queries on AddressBook DB |
| get/create/update/add/remove/delete | AppleScript | Reliable iCloud sync |
| set_photo/clear_photo | AppleScript | Native photo handling |

### Why This Mix?

**Swift for accounts:** CNContactStore is the only way to programmatically list contact containers and identify the default account.

**SQL for reads:** Fast, indexed queries. The AddressBook SQLite database is the source of truth.

**AppleScript for writes:** The Contacts framework (CNContact) has known bugs with notes and social profiles. AppleScript is Apple's canonical interface - changes sync reliably with iCloud.

## Contact Photo Operations

### Check if contact has photo
```
contact = Contacts.get(id: "...")
if contact.has_photo:
    print("Has photo")
```

### Set photo from file
```
Contacts.set_photo(id: "...", path: "/path/to/photo.jpg")
```

### Clear photo
```
Contacts.clear_photo(id: "...")
```

## Notes

- Contact IDs can change after iCloud sync - query by name after create
- Phone numbers are auto-normalized: `5125551234` → `+15125551234`
- URL labels are auto-detected: `github.com` → "GitHub"

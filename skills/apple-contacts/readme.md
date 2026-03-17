---
id: apple-contacts
name: Apple Contacts
description: Access macOS Contacts as Person entities with multi-account support
icon: icon.png
color: "#333333"

website: https://www.apple.com/macos/

auth: none
# ═══════════════════════════════════════════════════════════════════════════════
# ADAPTERS
# ═══════════════════════════════════════════════════════════════════════════════

adapters:
  person:
    id: .id
    name: '.display_name // (.first_name + " " + .last_name) // .organization'
    first_name: .first_name
    last_name: .last_name
    middle_name: .middle_name
    nickname: .nickname
    phone: '.phones_json | fromjson | .[0].value? // null'
    email: '.emails_json | fromjson | .[0].value? // null'
    avatar: 'if .has_photo == 1 then "contacts://photo/" + .id else null end'
    organization: .organization
    job_title: .job_title
    department: .department
    birthday: .birthday
    notes: .notes

    # Build unified accounts array from phones, emails, URLs, and social profiles
    accounts: |
        # Check if label is Apple internal format like _$!<Home>!$_
        def is_apple_label: . != null and test("^_\\$!<");
        
        # Check if label is generic (should fall back to URL domain)
        def is_generic_label: . != null and (. | ascii_downcase | test("^(profile|website|homepage|home-page|company|company-website|business|personal|other|home|work)$"));
        
        # Parse Apple label: _$!<Home>!$_ → "home"
        def parse_apple_label: if is_apple_label then gsub("^_\\$!<|>!\\$_$"; "") | ascii_downcase else null end;
        
        # Extract domain from URL → platform type (linkedin.com → linkedin, www.github.com → github)
        def url_to_platform: 
          if . == null then null 
          else capture("https?://(?:www\\.)?(?<d>[^/]+)").d? // null |
            if . then split(".")[0] |
              # Normalize a few known aliases
              if . == "x" then "twitter" elif . == "angel" then "angellist" else . end
            else null end
          end;
        
        # Extract username from URL using common patterns
        def extract_username:
          if . == null then null
          # /in/username, /pub/username (LinkedIn)
          elif test("/in/|/pub/") then capture("/(in|pub)/(?<u>[^/?]+)").u
          # /user/username, /users/username
          elif test("/users?/") then capture("/users?/(?<u>[^/?]+)").u
          # /profile/username (but not profile.php?id=)
          elif test("/profile/[^.?]") then capture("/profile/(?<u>[^/?]+)").u
          # profile.php?id=123 (Facebook legacy)
          elif test("profile\\.php\\?id=") then capture("profile\\.php\\?id=(?<u>[0-9]+)").u
          # /@username (Medium, etc)
          elif test("/@") then capture("/@(?<u>[^/?]+)").u
          # /people/username (TripIt, etc)
          elif test("/people/") then capture("/people/(?<u>[^/?]+)").u
          # Generic: first path segment after domain (works for most: github.com/user, twitter.com/user)
          else capture("https?://[^/]+/(?<u>[^/?]+)").u? // null
          end;
        
        # Normalize truncated/variant service names from Apple's social profiles table
        def normalize_service:
          if . == null then null 
          else ascii_downcase |
            # Handle Apple's truncated mess: "li", "lin", "linke" → "linkedin"
            if . == "li" or test("^lin") then "linkedin"
            elif test("^fac") then "facebook"
            elif test("^twit") or . == "x" then "twitter"
            elif test("^ins") then "instagram"
            elif test("^plus") then "google-plus"
            else . end
          end;
        
        # Phones → accounts (only include label if not null)
        ((.phones_json // "[]") | fromjson | map(select(.value) | 
          (.label | parse_apple_label) as $lbl |
          {type: "phone", value: .value} + (if $lbl then {label: $lbl} else {} end)
        )) as $phones |
        
        # Emails → accounts (only include label if not null)
        ((.emails_json // "[]") | fromjson | map(select(.value) | 
          (.label | parse_apple_label) as $lbl |
          {type: "email", value: .value} + (if $lbl then {label: $lbl} else {} end)
        )) as $emails |
        
        # URLs → accounts
        # If label is Apple internal or generic → extract type from URL domain
        # Otherwise use label as type (like "LinkedIn", "Dex Contact Details", "about.me")
        ((.urls_json // "[]") | fromjson | map(select(.url) |
          (.label | ascii_downcase | gsub(" "; "-")) as $normalized_label |
          (if (.label | is_apple_label) or (.label | is_generic_label) then .url | url_to_platform else $normalized_label end) as $type |
          (.url | extract_username) as $username |
          select($type) | {type: $type} + (if $username then {value: $username} else {} end) + {url: .url}
        )) as $url_accounts |
        
        # Social profiles → accounts (normalize truncated service names)
        ((.social_json // "[]") | fromjson | map(select(.username) |
          {type: (.service | normalize_service), value: (.username | ascii_downcase)}
        )) as $social_accounts |
        
        # Combine: phones + emails + (URLs and social deduped by type, prefer entries with usernames)
        $phones + $emails + (($url_accounts + $social_accounts) | group_by(.type) | map(sort_by(if .value then 0 else 1 end) | .[0]))

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

operations:
  list_persons:
    description: List contacts from a specific account with optional filtering
    returns: person[]
    params:
      account: { type: string, required: true, description: "Account ID from accounts utility" }
      query: { type: string, description: "Search by name, email, phone, or organization" }
      organization: { type: string, description: "Filter by organization" }
      sort: { type: string, default: "modified", description: "Sort by: modified (default), created, name" }
      limit: { type: integer }
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
          
          -- JSON arrays for phones, emails, URLs, social profiles
          (SELECT json_group_array(json_object('value', p.ZFULLNUMBER, 'label', p.ZLABEL))
           FROM ZABCDPHONENUMBER p WHERE p.ZOWNER = r.Z_PK) as phones_json,
          
          (SELECT json_group_array(json_object('value', e.ZADDRESS, 'label', e.ZLABEL))
           FROM ZABCDEMAILADDRESS e WHERE e.ZOWNER = r.Z_PK) as emails_json,
          
          (SELECT json_group_array(json_object('url', u.ZURL, 'label', u.ZLABEL))
           FROM ZABCDURLADDRESS u WHERE u.ZOWNER = r.Z_PK) as urls_json,
          
          (SELECT json_group_array(json_object('service', sp.ZSERVICENAME, 'username', sp.ZUSERNAME))
           FROM ZABCDSOCIALPROFILE sp WHERE sp.ZOWNER = r.Z_PK) as social_json
          
        FROM ZABCDRECORD r
        WHERE (r.ZUNIQUEID LIKE '%:ABPerson' OR r.ZUNIQUEID LIKE '%:ABInfo')
          AND (r.ZFIRSTNAME IS NOT NULL OR r.ZLASTNAME IS NOT NULL OR r.ZORGANIZATION IS NOT NULL)
        ORDER BY r.ZMODIFICATIONDATE DESC
        LIMIT :limit
      params:
        limit: '.params.limit // 1000'
    test:
      mode: read
      fixtures:
        limit: 10
      discover_from:
        op: accounts
        map:
          account: id

  get_person:
    description: Get full contact details by ID including addresses, notes, birthday
    returns: person
    params:
      id: { type: string, required: true, description: "Contact ID (ZUNIQUEID)" }
    command:
      binary: swift
      args:
        - ./get_person.swift
        - ".params.id"
      working_dir: .
      timeout: 20
    test:
      mode: read
      discover_from:
        op: list_persons
        params:
          limit: 10
        map:
          id: id

  search_persons:
    description: Search contacts by any text within a specific account
    returns: person[]
    params:
      account: { type: string, required: true, description: "Account ID from accounts utility" }
      query: { type: string, required: true, description: "Search text" }
      limit: { type: integer }
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
          
          -- JSON arrays for accounts building
          (SELECT json_group_array(json_object('value', p2.ZFULLNUMBER, 'label', p2.ZLABEL))
           FROM ZABCDPHONENUMBER p2 WHERE p2.ZOWNER = r.Z_PK) as phones_json,
          
          (SELECT json_group_array(json_object('value', e2.ZADDRESS, 'label', e2.ZLABEL))
           FROM ZABCDEMAILADDRESS e2 WHERE e2.ZOWNER = r.Z_PK) as emails_json,
          
          (SELECT json_group_array(json_object('url', u.ZURL, 'label', u.ZLABEL))
           FROM ZABCDURLADDRESS u WHERE u.ZOWNER = r.Z_PK) as urls_json,
          
          (SELECT json_group_array(json_object('service', sp.ZSERVICENAME, 'username', sp.ZUSERNAME))
           FROM ZABCDSOCIALPROFILE sp WHERE sp.ZOWNER = r.Z_PK) as social_json
           
        FROM ZABCDRECORD r
        LEFT JOIN ZABCDPHONENUMBER p ON p.ZOWNER = r.Z_PK
        LEFT JOIN ZABCDEMAILADDRESS e ON e.ZOWNER = r.Z_PK
        WHERE (r.ZUNIQUEID LIKE '%:ABPerson' OR r.ZUNIQUEID LIKE '%:ABInfo')
          AND (r.ZFIRSTNAME IS NOT NULL OR r.ZLASTNAME IS NOT NULL OR r.ZORGANIZATION IS NOT NULL)
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
        limit: '.params.limit // 1000'
    test:
      mode: read
      fixtures:
        query: a
        limit: 10
      discover_from:
        op: accounts
        map:
          account: id

  accounts:
    operation: read
    label: "List accounts"
    description: List available contact accounts/containers (iCloud, local, work, etc.)
    returns: object[]
    command:
      binary: swift
      args:
        - ./accounts.swift
      working_dir: .
      timeout: 20
    test:
      mode: read

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
    command:
      binary: swift
      args:
        - ./create.swift
      stdin: '.params | tojson'
      working_dir: .
      timeout: 20

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
    command:
      binary: swift
      args:
        - ./update.swift
      stdin: '.params | tojson'
      working_dir: .
      timeout: 20

  delete:
    operation: delete
    label: "Delete contact"
    description: Delete a contact
    returns:
      status: string
      name: string
    params:
      id: { type: string, required: true, description: "Contact ID" }
    command:
      binary: swift
      args:
        - ./delete.swift
      stdin: '.params | tojson'
      working_dir: .
      timeout: 20

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
| `list_persons` | List contacts with phones, emails, organization |
| `get_person` | Get full details: addresses, notes, birthday |
| `search_persons` | Search contacts by name, email, phone, organization |

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
| accounts | Swift helper | Lists contact containers |
| list/search | SQL | Fast indexed queries on AddressBook DB |
| get | Swift helper | Full details with structured arrays |
| create/update/delete | Swift helpers | Mutations with native Contacts APIs |

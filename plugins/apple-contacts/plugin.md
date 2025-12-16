---
id: apple-contacts
name: Apple Contacts
description: Search, view, and manage macOS Contacts
category: productivity
icon: https://upload.wikimedia.org/wikipedia/en/a/ac/MacOS_Contacts_icon.png
color: "#000000"

triggers:
  - asks about contacts, phone numbers, or email addresses
platform: macos

requires:
  - osascript  # Pre-installed on macOS
  - sqlite3    # Pre-installed on macOS

permissions:
  - contacts

actions:
  query:
    readonly: true
    description: Run read-only SQLite query against Contacts database
    params:
      sql:
        type: string
        required: true
        description: SQL query (SELECT only). Use schema reference below.
      limit:
        type: number
        default: 50
        description: Max rows to return
    run: |
      for db in ~/Library/Application\ Support/AddressBook/Sources/*/AddressBook-v22.abcddb; do
        # Only append LIMIT if query doesn't already have one
        if echo "$PARAM_SQL" | grep -qi "LIMIT"; then
          sqlite3 -header -separator ' | ' "$db" "$PARAM_SQL"
        else
          sqlite3 -header -separator ' | ' "$db" "$PARAM_SQL LIMIT ${PARAM_LIMIT:-50}"
        fi
      done

  get:
    readonly: true
    description: Get full contact details by ID (all phones, emails, URLs, notes)
    params:
      id:
        type: string
        required: true
        description: Contact ID (ZUNIQUEID from query)
    run: |
      ID="$PARAM_ID"
      [[ "$ID" != *":ABPerson" ]] && ID="${ID}:ABPerson"
      
      osascript << EOF
      tell application "Contacts"
        try
          set p to person id "$ID"
          
          set pFirst to first name of p
          set pLast to last name of p
          set pMiddle to middle name of p
          set pNick to nickname of p
          set pOrg to organization of p
          set pJob to job title of p
          set pDept to department of p
          set pNote to note of p
          
          if pFirst is missing value then set pFirst to ""
          if pLast is missing value then set pLast to ""
          if pMiddle is missing value then set pMiddle to ""
          if pNick is missing value then set pNick to ""
          if pOrg is missing value then set pOrg to ""
          if pJob is missing value then set pJob to ""
          if pDept is missing value then set pDept to ""
          if pNote is missing value then set pNote to ""
          
          set output to "=== Contact ===" & "\n"
          set output to output & "ID: " & id of p & "\n"
          set output to output & "Name: " & pFirst & " " & pLast & "\n"
          if pMiddle is not "" then set output to output & "Middle: " & pMiddle & "\n"
          if pNick is not "" then set output to output & "Nickname: " & pNick & "\n"
          if pOrg is not "" then set output to output & "Organization: " & pOrg & "\n"
          if pJob is not "" then set output to output & "Job Title: " & pJob & "\n"
          if pDept is not "" then set output to output & "Department: " & pDept & "\n"
          if pNote is not "" then set output to output & "Note: " & pNote & "\n"
          
          set output to output & "\n=== Phones ===" & "\n"
          repeat with ph in phones of p
            set output to output & label of ph & ": " & value of ph & "\n"
          end repeat
          
          set output to output & "\n=== Emails ===" & "\n"
          repeat with em in emails of p
            set output to output & label of em & ": " & value of em & "\n"
          end repeat
          
          set output to output & "\n=== URLs ===" & "\n"
          repeat with u in urls of p
            set output to output & label of u & ": " & value of u & "\n"
          end repeat
          
          return output
        on error errMsg
          return "Error: " & errMsg
        end try
      end tell
      EOF

  create:
    description: Create a new contact
    params:
      first_name:
        type: string
        description: First name
      last_name:
        type: string
        description: Last name
      organization:
        type: string
        description: Organization/company
      job_title:
        type: string
        description: Job title
      phone:
        type: string
        description: Phone number (auto-normalized with +1 for US)
      phone_label:
        type: string
        default: mobile
        description: Phone label (mobile, home, work)
      email:
        type: string
        description: Email address
      email_label:
        type: string
        default: home
        description: Email label (home, work)
      url:
        type: string
        description: URL (label auto-detected from domain)
      note:
        type: string
        description: Note text
    run: |
      # Normalize phone number
      normalize_phone() {
        local num="$1"
        local digits=$(echo "$num" | tr -cd '0-9')
        if [[ ${#digits} -eq 10 ]]; then
          echo "+1$digits"
        elif [[ ${#digits} -eq 11 && ${digits:0:1} == "1" ]]; then
          echo "+$digits"
        elif [[ "$num" == +* ]]; then
          echo "$num"
        else
          echo "$num"
        fi
      }
      
      # Auto-detect URL label
      detect_url_label() {
        local url="$1"
        case "$url" in
          *twitter.com*|*x.com*) echo "Twitter" ;;
          *linkedin.com*) echo "LinkedIn" ;;
          *github.com*) echo "GitHub" ;;
          *instagram.com*) echo "Instagram" ;;
          *facebook.com*) echo "Facebook" ;;
          *youtube.com*) echo "YouTube" ;;
          *tiktok.com*) echo "TikTok" ;;
          *threads.net*) echo "Threads" ;;
          *bsky.app*) echo "Bluesky" ;;
          *mastodon.*) echo "Mastodon" ;;
          *keybase.io*) echo "Keybase" ;;
          *t.me*|*telegram.*) echo "Telegram" ;;
          *wa.me*|*whatsapp.com*) echo "WhatsApp" ;;
          *reddit.com*) echo "Reddit" ;;
          *twitch.tv*) echo "Twitch" ;;
          *medium.com*) echo "Medium" ;;
          *pinterest.com*) echo "Pinterest" ;;
          *snapchat.com*) echo "Snapchat" ;;
          *dribbble.com*) echo "Dribbble" ;;
          *behance.net*) echo "Behance" ;;
          *dev.to*) echo "DEV" ;;
          *stackoverflow.com*) echo "StackOverflow" ;;
          *angel.co*) echo "AngelList" ;;
          *producthunt.com*) echo "ProductHunt" ;;
          *spotify.com*) echo "Spotify" ;;
          *soundcloud.com*) echo "SoundCloud" ;;
          *gitlab.com*) echo "GitLab" ;;
          *) echo "homepage" ;;
        esac
      }
      
      PHONE_NORMALIZED=""
      [ -n "$PARAM_PHONE" ] && PHONE_NORMALIZED=$(normalize_phone "$PARAM_PHONE")
      
      URL_LABEL=""
      [ -n "$PARAM_URL" ] && URL_LABEL=$(detect_url_label "$PARAM_URL")
      
      osascript << EOF
      tell application "Contacts"
        set props to {}
        
        if "$PARAM_FIRST_NAME" is not "" then set props to props & {first name:"$PARAM_FIRST_NAME"}
        if "$PARAM_LAST_NAME" is not "" then set props to props & {last name:"$PARAM_LAST_NAME"}
        if "$PARAM_ORGANIZATION" is not "" then set props to props & {organization:"$PARAM_ORGANIZATION"}
        if "$PARAM_JOB_TITLE" is not "" then set props to props & {job title:"$PARAM_JOB_TITLE"}
        if "$PARAM_NOTE" is not "" then set props to props & {note:"$PARAM_NOTE"}
        
        set newPerson to make new person with properties props
        
        if "$PHONE_NORMALIZED" is not "" then
          make new phone at end of phones of newPerson with properties {label:"${PARAM_PHONE_LABEL:-mobile}", value:"$PHONE_NORMALIZED"}
        end if
        
        if "$PARAM_EMAIL" is not "" then
          make new email at end of emails of newPerson with properties {label:"${PARAM_EMAIL_LABEL:-home}", value:"$PARAM_EMAIL"}
        end if
        
        if "$PARAM_URL" is not "" then
          make new url at end of urls of newPerson with properties {label:"$URL_LABEL", value:"$PARAM_URL"}
        end if
        
        save
        return "Created: " & first name of newPerson & " " & last name of newPerson & " (query by name to get ID)"
      end tell
      EOF

  update:
    description: Update contact scalar fields (name, org, job title, note)
    params:
      id:
        type: string
        required: true
        description: Contact ID
      first_name:
        type: string
        description: New first name
      last_name:
        type: string
        description: New last name
      middle_name:
        type: string
        description: New middle name
      nickname:
        type: string
        description: New nickname
      organization:
        type: string
        description: New organization
      job_title:
        type: string
        description: New job title
      department:
        type: string
        description: New department
      note:
        type: string
        description: New note
    run: |
      ID="$PARAM_ID"
      [[ "$ID" != *":ABPerson" ]] && ID="${ID}:ABPerson"
      
      osascript << EOF
      tell application "Contacts"
        try
          set p to person id "$ID"
          
          if "$PARAM_FIRST_NAME" is not "" then set first name of p to "$PARAM_FIRST_NAME"
          if "$PARAM_LAST_NAME" is not "" then set last name of p to "$PARAM_LAST_NAME"
          if "$PARAM_MIDDLE_NAME" is not "" then set middle name of p to "$PARAM_MIDDLE_NAME"
          if "$PARAM_NICKNAME" is not "" then set nickname of p to "$PARAM_NICKNAME"
          if "$PARAM_ORGANIZATION" is not "" then set organization of p to "$PARAM_ORGANIZATION"
          if "$PARAM_JOB_TITLE" is not "" then set job title of p to "$PARAM_JOB_TITLE"
          if "$PARAM_DEPARTMENT" is not "" then set department of p to "$PARAM_DEPARTMENT"
          if "$PARAM_NOTE" is not "" then set note of p to "$PARAM_NOTE"
          
          save
          return "Updated contact"
        on error errMsg
          return "Error: " & errMsg
        end try
      end tell
      EOF

  modify:
    description: Add or remove phone, email, or URL from a contact
    params:
      id:
        type: string
        required: true
        description: Contact ID
      op:
        type: string
        required: true
        description: "Operation: add or remove"
      type:
        type: string
        required: true
        description: "Field type: phone, email, or url"
      value:
        type: string
        required: true
        description: The value to add/remove
      label:
        type: string
        description: Label (mobile/home/work for phone/email, auto-detected for URLs)
    run: |
      ID="$PARAM_ID"
      [[ "$ID" != *":ABPerson" ]] && ID="${ID}:ABPerson"
      
      # Normalize phone number
      normalize_phone() {
        local num="$1"
        local digits=$(echo "$num" | tr -cd '0-9')
        if [[ ${#digits} -eq 10 ]]; then
          echo "+1$digits"
        elif [[ ${#digits} -eq 11 && ${digits:0:1} == "1" ]]; then
          echo "+$digits"
        elif [[ "$num" == +* ]]; then
          echo "$num"
        else
          echo "$num"
        fi
      }
      
      # Auto-detect URL label
      detect_url_label() {
        local url="$1"
        case "$url" in
          *twitter.com*|*x.com*) echo "Twitter" ;;
          *linkedin.com*) echo "LinkedIn" ;;
          *github.com*) echo "GitHub" ;;
          *instagram.com*) echo "Instagram" ;;
          *facebook.com*) echo "Facebook" ;;
          *youtube.com*) echo "YouTube" ;;
          *tiktok.com*) echo "TikTok" ;;
          *threads.net*) echo "Threads" ;;
          *bsky.app*) echo "Bluesky" ;;
          *mastodon.*) echo "Mastodon" ;;
          *keybase.io*) echo "Keybase" ;;
          *t.me*|*telegram.*) echo "Telegram" ;;
          *wa.me*|*whatsapp.com*) echo "WhatsApp" ;;
          *reddit.com*) echo "Reddit" ;;
          *twitch.tv*) echo "Twitch" ;;
          *medium.com*) echo "Medium" ;;
          *pinterest.com*) echo "Pinterest" ;;
          *snapchat.com*) echo "Snapchat" ;;
          *dribbble.com*) echo "Dribbble" ;;
          *behance.net*) echo "Behance" ;;
          *dev.to*) echo "DEV" ;;
          *stackoverflow.com*) echo "StackOverflow" ;;
          *angel.co*) echo "AngelList" ;;
          *producthunt.com*) echo "ProductHunt" ;;
          *spotify.com*) echo "Spotify" ;;
          *soundcloud.com*) echo "SoundCloud" ;;
          *gitlab.com*) echo "GitLab" ;;
          *) echo "homepage" ;;
        esac
      }
      
      # Prepare value and label based on type
      VALUE="$PARAM_VALUE"
      LABEL="${PARAM_LABEL:-}"
      
      if [ "$PARAM_TYPE" = "phone" ]; then
        VALUE=$(normalize_phone "$PARAM_VALUE")
        [ -z "$LABEL" ] && LABEL="mobile"
      elif [ "$PARAM_TYPE" = "email" ]; then
        [ -z "$LABEL" ] && LABEL="home"
      elif [ "$PARAM_TYPE" = "url" ]; then
        [ -z "$LABEL" ] && LABEL=$(detect_url_label "$PARAM_VALUE")
      fi
      
      if [ "$PARAM_OP" = "add" ]; then
        osascript << EOF
      tell application "Contacts"
        try
          set p to person id "$ID"
          make new $PARAM_TYPE at end of ${PARAM_TYPE}s of p with properties {label:"$LABEL", value:"$VALUE"}
          save
          return "Added $PARAM_TYPE: $VALUE"
        on error errMsg
          return "Error: " & errMsg
        end try
      end tell
      EOF
      elif [ "$PARAM_OP" = "remove" ]; then
        osascript << EOF
      tell application "Contacts"
        try
          set p to person id "$ID"
          set itemCount to count of ${PARAM_TYPE}s of p
          repeat with i from itemCount to 1 by -1
            set item_ref to $PARAM_TYPE i of p
            if value of item_ref contains "$PARAM_VALUE" then
              delete $PARAM_TYPE i of p
              exit repeat
            end if
          end repeat
          save
          return "Removed $PARAM_TYPE"
        on error errMsg
          return "Error: " & errMsg
        end try
      end tell
      EOF
      else
        echo "Error: op must be 'add' or 'remove'"
        exit 1
      fi

  photo:
    description: Set or clear contact photo
    params:
      id:
        type: string
        required: true
        description: Contact ID
      op:
        type: string
        required: true
        description: "Operation: set or clear"
      source:
        type: string
        description: URL or local file path (required for set)
    run: |
      ID="$PARAM_ID"
      [[ "$ID" != *":ABPerson" ]] && ID="${ID}:ABPerson"
      
      if [ "$PARAM_OP" = "set" ]; then
        [ -z "$PARAM_SOURCE" ] && echo "Error: source required for set" && exit 1
        
        # Download if URL, otherwise use as file path
        if [[ "$PARAM_SOURCE" == http* ]]; then
          PHOTO_PATH="/tmp/contact_photo_$$.jpg"
          curl -sL "$PARAM_SOURCE" -o "$PHOTO_PATH"
        else
          PHOTO_PATH="$PARAM_SOURCE"
        fi
        
        osascript << EOF
      tell application "Contacts"
        try
          set p to person id "$ID"
          set imagePath to POSIX file "$PHOTO_PATH"
          set image of p to (read imagePath as picture)
          save
          return "Set photo"
        on error errMsg
          return "Error: " & errMsg
        end try
      end tell
      EOF
        
        # Cleanup temp file
        [[ "$PARAM_SOURCE" == http* ]] && rm -f "$PHOTO_PATH"
        
      elif [ "$PARAM_OP" = "clear" ]; then
        osascript << EOF
      tell application "Contacts"
        try
          set p to person id "$ID"
          set image of p to missing value
          save
          return "Cleared photo"
        on error errMsg
          return "Error: " & errMsg
        end try
      end tell
      EOF
      else
        echo "Error: op must be 'set' or 'clear'"
        exit 1
      fi

  delete:
    description: Delete a contact
    params:
      id:
        type: string
        required: true
        description: Contact ID
    run: |
      ID="$PARAM_ID"
      [[ "$ID" != *":ABPerson" ]] && ID="${ID}:ABPerson"
      
      osascript << EOF
      tell application "Contacts"
        try
          set p to person id "$ID"
          delete p
          save
          return "Deleted contact"
        on error errMsg
          return "Error: " & errMsg
        end try
      end tell
      EOF
---

# Apple Contacts

Search, view, and manage macOS Contacts. Uses SQLite for fast reads and AppleScript for reliable writes with iCloud sync.

## Requirements

- **macOS only** - Uses Contacts.app database and AppleScript
- **Contacts permission** - System Settings → Privacy & Security → Contacts

## Tools (7 total)

| Action | Purpose | Implementation |
|--------|---------|----------------|
| `query` | Flexible read queries | SQLite (read-only) |
| `get` | Full contact details by ID | AppleScript |
| `create` | Create new contact | AppleScript |
| `update` | Update scalar fields | AppleScript |
| `modify` | Add/remove phone/email/url | AppleScript |
| `photo` | Set or clear photo | AppleScript |
| `delete` | Delete contact | AppleScript |

---

## query

Run any SELECT query against the Contacts database. Use the schema reference below.

**Parameters:**
- `sql` (required): SQL SELECT query
- `limit` (optional): Max rows, default 50

**Examples:**

```
# Search by name
query(sql: "SELECT ZUNIQUEID, ZFIRSTNAME, ZLASTNAME FROM ZABCDRECORD WHERE ZFIRSTNAME LIKE '%John%'")

# Find contacts at a company
query(sql: "SELECT ZUNIQUEID, ZFIRSTNAME, ZLASTNAME, ZJOBTITLE FROM ZABCDRECORD WHERE ZORGANIZATION = 'Stripe'")

# Contacts without photos
query(sql: "SELECT ZUNIQUEID, ZFIRSTNAME, ZLASTNAME FROM ZABCDRECORD WHERE ZIMAGEDATA IS NULL AND ZTHUMBNAILIMAGEDATA IS NULL")

# Contacts with photos (>100 bytes = embedded, <100 = iCloud reference)
query(sql: "SELECT ZUNIQUEID, ZFIRSTNAME, ZLASTNAME, length(ZTHUMBNAILIMAGEDATA) as photo_bytes FROM ZABCDRECORD WHERE length(ZTHUMBNAILIMAGEDATA) > 100")

# Search by phone (last 4 digits indexed)
query(sql: "SELECT r.ZUNIQUEID, r.ZFIRSTNAME, r.ZLASTNAME, p.ZFULLNUMBER FROM ZABCDRECORD r JOIN ZABCDPHONENUMBER p ON p.ZOWNER = r.Z_PK WHERE p.ZLASTFOURDIGITS = '1234'")

# Contacts with LinkedIn URLs
query(sql: "SELECT r.ZUNIQUEID, r.ZFIRSTNAME, r.ZLASTNAME, u.ZURL FROM ZABCDRECORD r JOIN ZABCDURLADDRESS u ON u.ZOWNER = r.Z_PK WHERE u.ZURL LIKE '%linkedin%'")

# Contacts with no email
query(sql: "SELECT r.ZUNIQUEID, r.ZFIRSTNAME, r.ZLASTNAME FROM ZABCDRECORD r LEFT JOIN ZABCDEMAILADDRESS e ON e.ZOWNER = r.Z_PK WHERE e.ZADDRESS IS NULL")
```

---

## get

Get full contact details including all phones, emails, URLs, and notes.

**Parameters:**
- `id` (required): Contact ID from query

---

## create

Create a new contact with optional phone, email, and URL.

**Parameters:**
- `first_name`, `last_name`, `organization`, `job_title`, `note` (optional)
- `phone` (optional): Auto-normalized (+1 for US 10-digit)
- `phone_label` (optional): default "mobile"
- `email`, `email_label` (optional): default "home"
- `url` (optional): Label auto-detected from domain

**Note:** After create, query by name to get the stable ID for further operations.

---

## update

Update scalar fields (name, org, job title, note, etc.)

**Parameters:**
- `id` (required): Contact ID
- Fields: `first_name`, `last_name`, `middle_name`, `nickname`, `organization`, `job_title`, `department`, `note`

---

## modify

Add or remove multi-value fields (phone, email, URL).

**Parameters:**
- `id` (required): Contact ID
- `op` (required): `add` or `remove`
- `type` (required): `phone`, `email`, or `url`
- `value` (required): The value to add/remove
- `label` (optional): Auto-detected for URLs, defaults to "mobile"/"home" for phone/email

**Examples:**

```
# Add phone
modify(id: "ABC123", op: "add", type: "phone", value: "5125551234", label: "work")

# Add URL (label auto-detected)
modify(id: "ABC123", op: "add", type: "url", value: "https://github.com/johndoe")

# Remove email
modify(id: "ABC123", op: "remove", type: "email", value: "old@email.com")
```

---

## photo

Set or clear contact photo.

**Parameters:**
- `id` (required): Contact ID
- `op` (required): `set` or `clear`
- `source` (required for set): URL or local file path

**Photo URL sources by service:**

| Service | URL Pattern |
|---------|------------|
| GitHub | `https://github.com/{username}.png` |
| Gravatar | `https://gravatar.com/avatar/{md5_email}?s=400` |
| Keybase | `https://keybase.io/{username}/photo.png` |

---

## delete

Permanently delete a contact.

**Parameters:**
- `id` (required): Contact ID

---

## Schema Reference

Database: `~/Library/Application Support/AddressBook/Sources/*/AddressBook-v22.abcddb`

### ZABCDRECORD (Main contacts table)

| Column | Description |
|--------|-------------|
| `Z_PK` | Internal primary key (for JOINs) |
| `ZUNIQUEID` | Contact ID (use this) |
| `ZFIRSTNAME` | First name |
| `ZLASTNAME` | Last name |
| `ZMIDDLENAME` | Middle name |
| `ZNICKNAME` | Nickname |
| `ZORGANIZATION` | Company/organization |
| `ZJOBTITLE` | Job title |
| `ZDEPARTMENT` | Department |
| `ZIMAGEDATA` | Full image BLOB |
| `ZTHUMBNAILIMAGEDATA` | Thumbnail BLOB (main photo storage) |

### ZABCDPHONENUMBER (Phones)

| Column | Description |
|--------|-------------|
| `ZOWNER` | FK to ZABCDRECORD.Z_PK |
| `ZFULLNUMBER` | Phone number |
| `ZLABEL` | Label (mobile, home, work) |
| `ZLASTFOURDIGITS` | Indexed for fast lookup |

### ZABCDEMAILADDRESS (Emails)

| Column | Description |
|--------|-------------|
| `ZOWNER` | FK to ZABCDRECORD.Z_PK |
| `ZADDRESS` | Email address |
| `ZLABEL` | Label (home, work) |

### ZABCDURLADDRESS (URLs)

| Column | Description |
|--------|-------------|
| `ZOWNER` | FK to ZABCDRECORD.Z_PK |
| `ZURL` | URL |
| `ZLABEL` | Label (GitHub, LinkedIn, homepage, etc.) |

### ZABCDNOTE (Notes)

| Column | Description |
|--------|-------------|
| `ZOWNER` | FK to ZABCDRECORD.Z_PK |
| `ZTEXT` | Note text |

### ZABCDPOSTALADDRESS (Addresses)

| Column | Description |
|--------|-------------|
| `ZOWNER` | FK to ZABCDRECORD.Z_PK |
| `ZSTREET` | Street address |
| `ZCITY` | City |
| `ZSTATE` | State/province |
| `ZZIPCODE` | Postal code |
| `ZCOUNTRYNAME` | Country |

---

## Smart Behaviors

### Phone Normalization

10-digit US numbers automatically get `+1` prefix:
- `5125551234` → `+15125551234`
- `15125551234` → `+15125551234`
- `+44 7911 123456` → kept as-is (international)

### URL Auto-Labeling

URLs are auto-labeled by domain (25+ services):

| Domain | Label |
|--------|-------|
| twitter.com, x.com | Twitter |
| linkedin.com | LinkedIn |
| github.com | GitHub |
| instagram.com | Instagram |
| facebook.com | Facebook |
| youtube.com | YouTube |
| tiktok.com | TikTok |
| threads.net | Threads |
| bsky.app | Bluesky |
| mastodon.* | Mastodon |
| keybase.io | Keybase |
| t.me, telegram.* | Telegram |
| reddit.com | Reddit |
| twitch.tv | Twitch |
| medium.com | Medium |
| dev.to | DEV |
| stackoverflow.com | StackOverflow |
| dribbble.com | Dribbble |
| behance.net | Behance |
| spotify.com | Spotify |
| soundcloud.com | SoundCloud |
| gitlab.com | GitLab |
| (other) | homepage |

### Photo Detection

Apple stores photos in two columns, and contacts can have photos from multiple sources (manual, iCloud linked, iMessage, etc.):

| Column | Purpose |
|--------|---------|
| `ZIMAGEDATA` | Full-size image BLOB |
| `ZTHUMBNAILIMAGEDATA` | Thumbnail BLOB (main storage for programmatically-set photos) |

**Photo states:**

| State | Query | Notes |
|-------|-------|-------|
| No photo at all | `ZIMAGEDATA IS NULL AND ZTHUMBNAILIMAGEDATA IS NULL` | Contact has no photo |
| Has any photo | `ZIMAGEDATA IS NOT NULL OR ZTHUMBNAILIMAGEDATA IS NOT NULL` | Includes iCloud references |
| iCloud reference only | `length(ZIMAGEDATA) < 100 OR length(ZTHUMBNAILIMAGEDATA) < 100` | ~38 bytes, still displays in Contacts.app |
| Embedded photo | `length(ZTHUMBNAILIMAGEDATA) > 100` | Actual image data stored locally |

**Example: Find contacts that need photos added:**
```sql
SELECT ZUNIQUEID, ZFIRSTNAME, ZLASTNAME 
FROM ZABCDRECORD 
WHERE ZIMAGEDATA IS NULL AND ZTHUMBNAILIMAGEDATA IS NULL
```

**Example: Find contacts with only iCloud reference (no embedded):**
```sql
SELECT ZUNIQUEID, ZFIRSTNAME, ZLASTNAME,
       length(ZIMAGEDATA) as img_bytes,
       length(ZTHUMBNAILIMAGEDATA) as thumb_bytes
FROM ZABCDRECORD 
WHERE (ZIMAGEDATA IS NOT NULL OR ZTHUMBNAILIMAGEDATA IS NOT NULL)
  AND COALESCE(length(ZIMAGEDATA), 0) < 100 
  AND COALESCE(length(ZTHUMBNAILIMAGEDATA), 0) < 100
```

---

## Notes

- **ID Instability**: Contact IDs can change after iCloud sync. After `create`, query by name to get the stable ID.
- **Read vs Write**: SQLite for reads (fast, indexed), AppleScript for writes (reliable iCloud sync)
- **Why AppleScript for writes?** The macOS Contacts framework (`CNContact`) has known bugs - `mutableCopy()` doesn't preserve notes, and social profiles get corrupted. AppleScript is the canonical interface that Apple maintains, and changes sync automatically with iCloud.
- **Multiple Sources**: Queries iterate all AddressBook sources (local + iCloud accounts)

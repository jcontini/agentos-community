---
id: google-contacts
name: Google Contacts
description: "Read, search, create, and update Google Contacts via the People API"
color: "#4285F4"
website: "https://contacts.google.com"
privacy_url: "https://policies.google.com/privacy"

connections:
  api:
    base_url: https://people.googleapis.com/v1
    auth:
      type: oauth
      service: google
      scopes:
      - https://www.googleapis.com/auth/contacts

test:
  list_contacts:
    params:
      limit: 5
  search_contacts:
    params:
      query: a
      limit: 5
---

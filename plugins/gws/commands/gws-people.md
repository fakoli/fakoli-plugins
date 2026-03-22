---
description: Search and look up Google Contacts and directory profiles
argument-hint: "<search|list> [query]"
allowed-tools: [Bash]
---

# /gws-people

Search Google Contacts using the `gws` CLI.

## Instructions

When this command is invoked, parse `$ARGUMENTS` to determine the operation.

### Common Operations

**Search contacts:**
```bash
gws people people searchContacts --params '{"query": "SEARCH_TERM", "readMask": "names,emailAddresses,phoneNumbers"}' --format table
```

**List connections:**
```bash
gws people people connections list --params '{"resourceName": "people/me", "personFields": "names,emailAddresses", "pageSize": 20}' --format table
```

## Tips

- Always include `readMask` or `personFields` to specify which fields to return.
- Common field masks: `names`, `emailAddresses`, `phoneNumbers`, `organizations`.

## Error Handling

- Exit code 2: Auth expired. Tell user to run `gws auth login`.

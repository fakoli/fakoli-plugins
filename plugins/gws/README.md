# GWS — Google Workspace for Claude Code

A unified Claude Code plugin for interacting with Google Workspace services via the [`gws` CLI](https://github.com/googleworkspace/cli).

## Prerequisites

- [gws CLI](https://github.com/googleworkspace/cli) installed and authenticated (`gws auth login`)

## Skills (100)

### Core Services

| Service | Skill | Helper Commands |
|---------|-------|----------------|
| Shared | gws-shared | Auth, config, global flags |
| Gmail | gws-gmail | `+send`, `+triage`, `+reply`, `+reply-all`, `+forward`, `+watch` |
| Calendar | gws-calendar | `+agenda`, `+insert` |
| Drive | gws-drive | `+upload` |
| Sheets | gws-sheets | `+read`, `+append` |
| Docs | gws-docs | `+write` |
| Slides | gws-slides | Raw API |
| Tasks | gws-tasks | Raw API |
| Chat | gws-chat | `+send` |
| Workflow | gws-workflow | `+standup-report`, `+meeting-prep`, `+email-to-task`, `+weekly-digest`, `+file-announce` |
| Events | gws-events | `+subscribe`, `+renew` |
| Admin Reports | gws-admin-reports | Raw API |
| Classroom | gws-classroom | Raw API |
| Forms | gws-forms | Raw API |
| Keep | gws-keep | Raw API |
| Meet | gws-meet | Raw API |
| People | gws-people | Raw API |
| Model Armor | gws-modelarmor | `+create-template`, `+sanitize-prompt`, `+sanitize-response` |
| Script | gws-script | `+push` |

### Plugin-Original Skills (5)

Skills we created that go beyond the official repo:

| Skill | Description |
|-------|-------------|
| gws-auth | Authentication management — login, logout, status, scopes, service accounts |
| gws-schema | API schema introspection — discover methods, parameters, and types |
| gws-script | Apps Script deployment — push local files to Apps Script projects |
| gws-agent-safety | Security rules for AI agents — input validation, path safety, Model Armor |
| gws-quick-ref | Quick reference card — core syntax, flags, patterns, output formats |

### Persona Skills (10)

Role-based skill bundles that provide context-specific guidance:

| Persona | Description |
|---------|-------------|
| persona-exec-assistant | Manage an executive's schedule, inbox, and communications |
| persona-project-manager | Coordinate projects — track tasks, schedule meetings, share docs |
| persona-hr-coordinator | Handle HR workflows — onboarding, announcements, employee comms |
| persona-sales-ops | Manage sales workflows — track deals, schedule calls, client comms |
| persona-it-admin | Administer IT — monitor security, configure Workspace |
| persona-content-creator | Create, organize, and distribute content |
| persona-customer-support | Manage customer support — track tickets, respond, escalate |
| persona-event-coordinator | Plan and manage events — scheduling, invitations, logistics |
| persona-team-lead | Lead a team — run standups, coordinate tasks, communicate |
| persona-researcher | Organize research — manage references, notes, collaboration |

### Recipe Skills (44)

Curated multi-step workflows for common tasks (41 official + 3 plugin-original):

| Recipe | Description |
|--------|-------------|
| recipe-stream-inbox | Stream real-time Gmail notifications (plugin-original) |
| recipe-schema-explore | Discover and introspect any API before using it (plugin-original) |
| recipe-setup-sanitization | Configure Model Armor globally for all commands (plugin-original) |
| recipe-label-and-archive-emails | Label and archive Gmail threads |
| recipe-draft-email-from-doc | Draft a Gmail message from a Google Doc |
| recipe-organize-drive-folder | Organize files into Drive folders |
| recipe-share-folder-with-team | Share a Drive folder with a team |
| recipe-email-drive-link | Email a Google Drive file link |
| recipe-create-doc-from-template | Create a Doc from a template |
| recipe-create-expense-tracker | Set up a Sheets expense tracker |
| recipe-copy-sheet-for-new-month | Copy a Sheet tab for a new month |
| recipe-block-focus-time | Block focus time on Calendar |
| recipe-reschedule-meeting | Reschedule a Calendar meeting |
| recipe-create-gmail-filter | Create a Gmail filter |
| recipe-schedule-recurring-event | Schedule a recurring meeting |
| recipe-find-free-time | Find free time across calendars |
| recipe-bulk-download-folder | Bulk download a Drive folder |
| recipe-find-large-files | Find largest files in Drive |
| recipe-create-shared-drive | Create and configure a Shared Drive |
| recipe-log-deal-update | Log a deal update to a Sheet |
| recipe-collect-form-responses | Check Form responses |
| recipe-post-mortem-setup | Set up a post-mortem (Doc + Calendar + Chat) |
| recipe-create-task-list | Create a Task list with tasks |
| recipe-review-overdue-tasks | Review overdue tasks |
| recipe-watch-drive-changes | Watch for Drive changes |
| recipe-create-classroom-course | Create a Classroom course |
| recipe-create-meet-space | Create a Google Meet conference |
| recipe-review-meet-participants | Review Meet attendance |
| recipe-create-presentation | Create a Slides presentation |
| recipe-save-email-attachments | Save Gmail attachments to Drive |
| recipe-send-team-announcement | Announce via Gmail and Chat |
| recipe-create-feedback-form | Create and share a Google Form |
| recipe-sync-contacts-to-sheet | Export Contacts to Sheets |
| recipe-share-event-materials | Share files with meeting attendees |
| recipe-create-vacation-responder | Set up Gmail vacation responder |
| recipe-create-events-from-sheet | Create Calendar events from a Sheet |
| recipe-plan-weekly-schedule | Plan your weekly Calendar schedule |
| recipe-share-doc-and-notify | Share a Doc and notify collaborators |
| recipe-backup-sheet-as-csv | Export a Sheet as CSV |
| recipe-save-email-to-doc | Save a Gmail message to Docs |
| recipe-compare-sheet-tabs | Compare two Sheet tabs |
| recipe-batch-invite-to-event | Add multiple attendees to an event |
| recipe-forward-labeled-emails | Forward labeled Gmail messages |
| recipe-generate-report-from-sheet | Generate a Docs report from Sheet data |

## Agents (11)

| Agent | Role | Color |
|-------|------|-------|
| gws-orchestrator | Multi-step cross-service operations | blue |
| exec-assistant | Executive Assistant | blue |
| project-manager | Project Manager | cyan |
| hr-coordinator | HR Coordinator | green |
| sales-ops | Sales Operations | yellow |
| it-admin | IT Administrator | red |
| content-creator | Content Creator | magenta |
| customer-support | Customer Support Agent | green |
| event-coordinator | Event Coordinator | cyan |
| team-lead | Team Lead | blue |
| researcher | Researcher | magenta |

## Slash Commands (15)

### Quick Actions

| Command | Description |
|---------|-------------|
| `/send-email` | Send an email |
| `/agenda` | Show upcoming calendar events |
| `/upload` | Upload a file to Google Drive |
| `/triage` | Show unread inbox summary |
| `/standup` | Generate a standup report |
| `/meeting-prep` | Prepare for your next meeting |

### Service Commands

| Command | Description |
|---------|-------------|
| `/gws-drive` | Search, upload, download, share Drive files |
| `/gws-sheets` | Read, write, append spreadsheet data |
| `/gws-docs` | Read, create, append to Google Docs |
| `/gws-slides` | Read and create presentations |
| `/gws-tasks` | List, create, complete tasks |
| `/gws-chat` | Send messages, list Chat spaces |
| `/gws-people` | Search contacts and profiles |
| `/gws-keep` | List and read Keep notes |
| `/gws-standup` | Cross-service standup report |

## Installation

```bash
claude plugin install --dir ./gws
```

Or add the marketplace and install from there:

```
/plugin marketplace add fakoli/fakoli-plugins
/plugin install gws
```

## Author

Sekou Doumbouya ([@fakoli](https://github.com/fakoli))

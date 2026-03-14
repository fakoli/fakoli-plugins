# Google Workspace Plugin

Google Workspace integration for Claude Code via the [`gws` CLI](https://github.com/googleworkspace/cli).

## Prerequisites

- [`gws` CLI](https://github.com/googleworkspace/cli) installed and on `$PATH`
- Authenticated: `gws auth login`

## Commands

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
| `/gws-meeting-prep` | Prepare for your next meeting |

## Skills (92)

Skills auto-activate based on conversation context. Includes:

### Service Skills (16)
Full API reference for each Google Workspace service: Drive, Sheets, Docs, Slides, Gmail, Calendar, Tasks, Chat, People, Keep, Forms, Meet, Classroom, Events, Admin Reports, and Workflow.

### Helper Skills (20+)
Focused skills for specific operations: `sheets-read`, `sheets-append`, `gmail-send`, `gmail-triage`, `gmail-reply`, `drive-upload`, `docs-write`, `calendar-agenda`, `calendar-insert`, `chat-send`, and more.

### Personas (10)
Role-based skill bundles that combine multiple services:
- **Executive Assistant** — schedule, inbox, and communications management
- **Project Manager** — task tracking, scheduling, and document sharing
- **Team Lead** — standups, 1:1 prep, and team coordination
- **Researcher** — reference management, notes, and collaboration
- **Content Creator** — drafting, organizing, and distributing content
- **Sales Operations** — deal tracking, client comms, and pipeline management
- **HR Coordinator** — onboarding, announcements, and employee comms
- **Customer Support** — ticket tracking, responses, and escalation
- **Event Coordinator** — scheduling, invitations, and logistics
- **IT Administrator** — security monitoring and Workspace configuration

### Recipes (40+)
Multi-step workflows combining multiple services:
- Draft email from a Google Doc
- Create calendar events from a spreadsheet
- Save email attachments to Drive
- Generate a report from sheet data
- Set up a post-mortem (doc + meeting + Chat notification)
- And many more

## Agent

**workspace-orchestrator** — Handles cross-service workflows that combine multiple Google Workspace services in a single task.

## Skills Source

Skills are adapted from the [gws CLI repository](https://github.com/googleworkspace/cli/tree/main/skills), converted from Gemini CLI format to Claude Code plugin format with enhanced descriptions for automatic skill triggering.

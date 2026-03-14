---
name: recipe-create-classroom-course
description: "Create a Google Classroom course and invite students."
trigger:
  - keyword: create course
  - keyword: classroom course
  - keyword: new class
version: 1.0.0
---

# Create a Google Classroom Course

Create a Google Classroom course and invite students.

## When to Use

Use this workflow when the user needs to set up a new course in Google Classroom, including inviting students or teachers.

## Workflow

### 1. Gather course details

Ask the user for:
- **Course name** (e.g., "Introduction to CS")
- **Section** (e.g., "Period 1")
- **Room** (optional)

### 2. Create the course

Use `--dry-run` first:

```bash
gws classroom courses create \
  --json '{"name": "COURSE_NAME", "section": "SECTION", "room": "ROOM", "ownerId": "me"}' \
  --dry-run
```

Confirm with the user, then execute.

### 3. Invite students

For each student email:

```bash
gws classroom invitations create \
  --json '{"courseId": "COURSE_ID", "userId": "student@school.edu", "role": "STUDENT"}'
```

### 4. Verify enrollment

```bash
gws classroom courses students list --params '{"courseId": "COURSE_ID"}' --format table
```

## Safety

- Always `--dry-run` before creating courses
- Verify student email addresses before sending invitations

## Tips

- Use `"role": "TEACHER"` to invite co-teachers
- The `ownerId` can be `"me"` for the authenticated user

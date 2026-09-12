#!/usr/bin/env python3
"""Read Pi coding-agent JSONL sessions without importing Pi or sending data.

The format follows Pi 0.84.2's exported SessionEntry schema (also selected by
the reviewed 0.85.1 upgrade): a ``session`` header, then append-only entries
whose ``id``/``parentId`` form a tree.  The selected trajectory is the last
valid appended leaf; timestamps are never used to infer ancestry.
"""

import json
import re


KNOWN_VERSIONS = {None, 1, 2, 3}
KNOWN_ENTRIES = {"message", "thinking_level_change", "model_change",
                 "compaction", "branch_summary", "custom",
                 "custom_message", "label", "session_info"}
SECRET = re.compile(r"(?:sk-[A-Za-z0-9-]{16,}|(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._~+/-]{20,})", re.I)


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(block.get("text", "") for block in content
                         if isinstance(block, dict)
                         and isinstance(block.get("text"), str))
    return ""


def _redact(value):
    """Return public-safe visible data plus a simple signal for curation."""
    flagged = False
    def visit(item):
        nonlocal flagged
        if isinstance(item, str):
            if SECRET.search(item):
                flagged = True
                return SECRET.sub("[REDACTED]", item)
            return item
        if isinstance(item, dict):
            return {str(key): visit(val) for key, val in item.items()}
        if isinstance(item, list):
            return [visit(val) for val in item]
        return item
    return visit(value), (["secret"] if flagged else [])


def _read_jsonl(path):
    records, counts = [], {"malformed_records": 0, "truncated_records": 0,
                           "non_object_records": 0}
    with open(path, encoding="utf-8-sig", errors="replace") as stream:
        for line in stream:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                counts["malformed_records"] += 1
                if not line.endswith("\n"):
                    counts["truncated_records"] += 1
                continue
            if not isinstance(item, dict):
                counts["non_object_records"] += 1
                continue
            records.append(item)
    return records, counts


def _path(entries, leaf_id):
    by_id = {entry["id"]: entry for entry in entries}
    out, seen = [], set()
    current = by_id.get(leaf_id)
    while current and current["id"] not in seen:
        out.append(current)
        seen.add(current["id"])
        parent = current.get("parentId")
        current = by_id.get(parent) if parent else None
    out.reverse()
    return out


def read_session(path):
    """Return only selected-path visible tasks/actions/results and diagnostics."""
    raw, counts = _read_jsonl(path)
    counts.update({"unknown_version": 0, "unknown_entries": 0,
                   "duplicate_ids": 0, "missing_parents": 0,
                   "abandoned_entries": 0})
    header = next((item for item in raw if item.get("type") == "session"), None)
    if header and header.get("version") not in KNOWN_VERSIONS:
        counts["unknown_version"] += 1
    entries, ids = [], set()
    for item in raw:
        if item.get("type") == "session":
            continue
        if item.get("type") not in KNOWN_ENTRIES:
            counts["unknown_entries"] += 1
            continue
        entry_id = item.get("id")
        if not isinstance(entry_id, str) or not entry_id:
            counts["unknown_entries"] += 1
            continue
        if entry_id in ids:
            counts["duplicate_ids"] += 1
            continue
        ids.add(entry_id)
        entries.append(item)
    valid = []
    for entry in entries:
        parent = entry.get("parentId")
        if parent is not None and parent not in ids:
            counts["missing_parents"] += 1
            continue
        valid.append(entry)
    leaf = valid[-1]["id"] if valid else None
    selected = _path(valid, leaf) if leaf else []
    counts["abandoned_entries"] = len(valid) - len(selected)
    actions, pending, awaiting_followup, last_user, summaries = [], {}, [], None, []
    partial = bool(counts["malformed_records"] or counts["missing_parents"])
    for entry in selected:
        if entry["type"] == "compaction":
            summary = entry.get("summary")
            if isinstance(summary, str) and summary:
                summaries.append(summary)
            partial = True
            continue
        if entry["type"] != "message":
            continue
        message = entry.get("message") if isinstance(entry.get("message"), dict) else {}
        role = message.get("role")
        if role == "user":
            text = _text(message.get("content")).strip()
            if text:
                safe_text, user_flags = _redact(text)
                for action in awaiting_followup:
                    action["followup_user_text"] = safe_text
                    action["redaction_flags"] = sorted(
                        set(action["redaction_flags"] + user_flags))
                awaiting_followup.clear()
                last_user = safe_text
        elif role == "assistant":
            for block in message.get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "toolCall":
                    continue
                call_id = block.get("id")
                if not isinstance(call_id, str) or not call_id:
                    continue
                arguments, flags = _redact(block.get("arguments") if isinstance(block.get("arguments"), dict) else {})
                action = {"kind": "tool_call", "tool": block.get("name"),
                          "input": arguments,
                          "tool_call_id": call_id, "intent": last_user,
                          "result": None, "result_is_error": None,
                          "followup_user_text": None, "partial": partial,
                          "redaction_flags": flags}
                actions.append(action)
                pending[call_id] = action
                awaiting_followup.append(action)
        elif role == "toolResult":
            action = pending.pop(message.get("toolCallId"), None)
            if action:
                action["result"], result_flags = _redact(_text(message.get("content")))
                action["redaction_flags"] = sorted(set(action["redaction_flags"] + result_flags))
                action["result_is_error"] = bool(message.get("isError"))
                if action["result_is_error"]:
                    action["partial"] = True
    for action in pending.values():
        action["partial"] = True
    return {"header": {"version": header.get("version") if header else None},
            "actions": actions, "counts": counts,
            "compaction_summaries": summaries}

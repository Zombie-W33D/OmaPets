"""Read the active canonical Bot Chat turn without touching agent services.

Hermes serializes a Bot Chat turn with a profile-local SQLite lease and updates
its session activity in the same database. This reader opens SQLite read-only;
it never looks at message bodies or private tool arguments.
"""

import os
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from scripts.omapets_data import discover_profile_homes

_TOOL = re.compile(r"^tool running: ([a-z][a-z_0-9.]{0,39})$", re.I)
_OWNER_PID = re.compile(r"(?:^|:)pid=(\d+)(?::|$)")
_TOOL_LABELS = {
    "terminal": "Running a command", "process_manage": "Checking a running task",
    "read_file": "Reading a file", "search_files": "Searching files",
    "web_search": "Researching online", "web_extract": "Reading a web page",
    "browser_exec": "Browsing a website", "patch": "Editing a file",
    "write_file": "Writing a file", "delegate_task": "Coordinating an agent",
    "message_agent": "Messaging an agent",
}


def _live_holder(holder):
    """Return True/False for a local PID, or None when Hermes did not include one."""
    match = _OWNER_PID.search(holder or "")
    if not match:
        return None
    try:
        os.kill(int(match.group(1)), 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OverflowError):
        pass
    return True


def _brief_activity(description):
    """Derive a safe, short update from Hermes' own bounded status labels."""
    description = description or ""
    match = _TOOL.fullmatch(description)
    if match:
        name = match.group(1).lower()
        return {"category": "working", "detail": _TOOL_LABELS.get(name, "Using " + name.replace("_", " "))}
    if description.startswith(("receiving stream response", "starting API call", "waiting for provider")):
        return {"category": "thinking", "detail": "Thinking through a response"}
    if description.startswith("compacting") or description.startswith("compressing"):
        return {"category": "thinking", "detail": "Condensing context"}
    if description.startswith("tool ") or description.startswith("executing "):
        return {"category": "working", "detail": "Using tools"}
    return {"category": "thinking", "detail": "Working on a reply"}


def _bot_chat_activity(db, now):
    if not db.is_file() or db.is_symlink():
        return None
    # mode=ro reads WAL changes but cannot create or mutate the agent database.
    with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=0.2)) as conn:
        root = conn.execute(
            "SELECT id, end_reason, last_activity_at, last_activity_description "
            "FROM sessions WHERE title = 'Bot Chat' AND parent_session_id IS NULL "
            "ORDER BY last_activity_at DESC LIMIT 1"
        ).fetchone()
        if root is None:
            return None
        lease = conn.execute(
            "SELECT holder, expires_at FROM session_turn_leases WHERE conversation_id = ?", (root[0],)
        ).fetchone()
        if lease is None or lease[1] <= now:
            return None
        owner_alive = _live_holder(lease[0])
        if owner_alive is False:
            return None
        # A dead process can leave a five-minute lease. Require recent activity
        # when the holder has no independently checkable local PID.
        current = root
        for _ in range(20):
            if current[1] != "compression":
                break
            child = conn.execute(
                "SELECT id, end_reason, last_activity_at, last_activity_description "
                "FROM sessions WHERE parent_session_id = ? AND COALESCE(source, '') != 'tool' "
                "AND COALESCE(CASE WHEN json_valid(model_config) THEN json_extract(model_config, '$._branched_from') END, '') != ? "
                "AND COALESCE(CASE WHEN json_valid(model_config) THEN json_extract(model_config, '$._delegate_from') END, '') != ? "
                "AND COALESCE(CASE WHEN json_valid(model_config) THEN json_extract(model_config, '$._reset_from') END, '') != ? "
                "ORDER BY last_activity_at DESC LIMIT 1", (current[0],) * 4
            ).fetchone()
            if child is None:
                break
            current = child
        if current[2] is None or (owner_alive is None and not 0 <= now - current[2] < 150):
            return None
        return _brief_activity(current[3])


def scan_activity(root: Path, now=None):
    """Profile-keyed live Bot Chat status; absent entries are not active."""
    now = time.time() if now is None else now
    result = {}
    for profile, home in discover_profile_homes(root):
        try:
            activity = _bot_chat_activity(home / "state.db", now)
        except (OSError, sqlite3.Error):
            continue  # A missing/locked/older profile is not a shell failure.
        if activity:
            result[profile] = activity
    return result

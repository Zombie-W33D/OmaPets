"""Read-only Bot Chat activity bridge tests."""
import os
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path

from scripts.omapets_activity import scan_activity


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "profiles" / "aria"
        self.home.mkdir(parents=True)
        (self.home / "config.yaml").write_text("{}\n")
        self.now = time.time()
        with closing(sqlite3.connect(self.home / "state.db")) as conn, conn:
            conn.executescript("""
                CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT,
                    parent_session_id TEXT, source TEXT, end_reason TEXT,
                    last_activity_at REAL, last_activity_description TEXT,
                    model_config TEXT);
                CREATE TABLE session_turn_leases (conversation_id TEXT PRIMARY KEY,
                    holder TEXT, expires_at REAL);
            """)
            conn.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?)",
                ("bot", "Bot Chat", None, "bot", None, self.now, "tool running: terminal", None))
            conn.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?)",
                ("other", "A different chat", None, "bot", None, self.now, "tool running: browser", None))

    def _write(self, sql, params=()):
        with closing(sqlite3.connect(self.home / "state.db")) as conn, conn:
            conn.execute(sql, params)

    def test_active_bot_chat_uses_lease_and_short_status_detail(self):
        self._write("INSERT INTO session_turn_leases VALUES (?,?,?)", ("bot", "pid:1", self.now + 300))
        self.assertEqual(scan_activity(self.root, self.now), {
            "aria": {"category": "working", "detail": "Running a command"}})

    def test_unrelated_chat_does_not_activate_pet(self):
        self._write("INSERT INTO session_turn_leases VALUES (?,?,?)", ("other", "pid:1", self.now + 300))
        self.assertEqual(scan_activity(self.root, self.now), {})

    def test_expired_lease_or_stale_heartbeat_is_inactive(self):
        self._write("INSERT INTO session_turn_leases VALUES (?,?,?)", ("bot", "pid:1", self.now - 1))
        self.assertEqual(scan_activity(self.root, self.now), {})
        self._write("UPDATE session_turn_leases SET expires_at=?", (self.now + 300,))
        self._write("UPDATE sessions SET last_activity_at=? WHERE id='bot'", (self.now - 180,))
        self.assertEqual(scan_activity(self.root, self.now), {})

    def test_live_process_keeps_long_running_turn_active(self):
        self._write("INSERT INTO session_turn_leases VALUES (?,?,?)",
            ("bot", f"desktop:pid={os.getpid()}:turn", self.now + 300))
        self._write("UPDATE sessions SET last_activity_at=? WHERE id='bot'", (self.now - 180,))
        self.assertEqual(scan_activity(self.root, self.now)["aria"]["category"], "working")

    def test_dead_process_is_not_active_even_with_unexpired_lease(self):
        self._write("INSERT INTO session_turn_leases VALUES (?,?,?)",
            ("bot", "desktop:pid=99999999:turn", self.now + 300))
        self.assertEqual(scan_activity(self.root, self.now), {})

    def test_thinking_status_does_not_leak_arbitrary_description(self):
        self._write("INSERT INTO session_turn_leases VALUES (?,?,?)", ("bot", "pid:1", self.now + 300))
        self._write("UPDATE sessions SET last_activity_description=? WHERE id='bot'",
            ("receiving stream response with private user text",))
        self.assertEqual(scan_activity(self.root, self.now), {
            "aria": {"category": "thinking", "detail": "Thinking through a response"}})

    def test_compressed_bot_chat_segment_uses_root_lease(self):
        self._write("UPDATE sessions SET end_reason='compression' WHERE id='bot'")
        self._write("INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?)",
            ("continuation", None, "bot", "desktop", None, self.now, "tool running: web_search", None))
        self._write("INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?)",
            ("fork", None, "bot", "desktop", None, self.now + 1,
             "tool running: browser", '{"_branched_from":"bot"}'))
        self._write("INSERT INTO session_turn_leases VALUES (?,?,?)", ("bot", "pid:1", self.now + 300))
        self.assertEqual(scan_activity(self.root, self.now), {
            "aria": {"category": "working", "detail": "Researching online"}})


if __name__ == "__main__":
    unittest.main()

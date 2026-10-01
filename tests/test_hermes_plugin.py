"""Hermes bridge tests only inspect explicit, redacted event boundaries."""
import importlib.util
from pathlib import Path
import unittest

PLUGIN = Path(__file__).resolve().parents[1] / "hermes-plugin" / "__init__.py"
spec = importlib.util.spec_from_file_location("omapets_hermes_plugin", PLUGIN)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class HermesHookTests(unittest.TestCase):
    def test_native_hook_events_do_not_classify_response_text(self):
        self.assertEqual(module.event_for("pre_llm_call", {"user_message": "yes"}), "thinking")
        self.assertEqual(module.event_for("pre_tool_call", {"tool_name": "terminal"}), "waiting_on_task")
        self.assertIsNone(module.event_for("post_tool_call", {"status": "ok", "result": "success!"}))
        self.assertEqual(module.event_for("post_tool_call", {"status": "error"}), "failed")
        self.assertEqual(module.event_for("post_llm_call", {"assistant_response": "No."}), "finished")
        self.assertEqual(module.event_for("pre_approval_request", {"command": "secret"}), "waiting_on_you")
        self.assertEqual(module.event_for("api_request_error", {"error": "down"}), "failed")

    def test_callbacks_forward_only_fixed_ids_no_private_payload(self):
        sent = []
        callback = module.build_hook_callback("pre_tool_call", lambda *pair: sent.append(pair),
                                               lambda: "codedump")
        callback(tool_name="private", args={"password": "sensitive"},
                 result="private chat", user_message="private chat")
        self.assertEqual(sent, [("codedump", "waiting_on_task")])
        self.assertIsNone(callback(tool_name="private", args={"password": "sensitive"}))

    def test_invalid_or_missing_profile_is_not_sent(self):
        sent = []
        callback = module.build_hook_callback("pre_llm_call", lambda *pair: sent.append(pair),
                                               lambda: "../other")
        callback(user_message="secret")
        self.assertEqual(sent, [])

    def test_explicit_response_tool_accepts_only_yes_no_success(self):
        sent = []
        signal = module.build_signal_handler(lambda *pair: sent.append(pair), lambda: "aria")
        self.assertEqual(signal({"category": "success"}), '{"queued": true}')
        self.assertEqual(sent, [("aria", "success")])
        self.assertEqual(signal({"category": "finished"}), '{"queued": false}')
        self.assertEqual(signal({"category": "yes", "message": "private"}), '{"queued": false}')
        self.assertEqual(len(sent), 1)


if __name__ == "__main__":
    unittest.main()

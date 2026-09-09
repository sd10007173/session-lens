import json
import tempfile
import unittest
from pathlib import Path

from digest import process_codex_session


class ProcessCodexSessionTests(unittest.TestCase):
    def write_rollout(self, records):
        temp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        with temp:
            for record in records:
                temp.write(json.dumps(record) + "\n")
        self.addCleanup(Path(temp.name).unlink, missing_ok=True)
        return Path(temp.name)

    def test_reads_new_response_item_messages_and_skips_injected_context(self):
        metadata = {"turn_id": "turn-1", "create_time": 1}
        path = self.write_rollout([
            {"timestamp": "2026-08-23T10:00:00Z", "type": "session_meta",
             "payload": {"cwd": "/tmp/project"}},
            {"timestamp": "2026-08-23T10:00:01Z", "type": "response_item",
             "payload": {"type": "message", "role": "user",
                         "content": [{"type": "input_text", "text": "# AGENTS.md instructions for /tmp/project"}],
                         "internal_chat_message_metadata_passthrough": metadata}},
            {"timestamp": "2026-08-23T10:00:01Z", "type": "response_item",
             "payload": {"type": "message", "role": "user",
                         "content": [{"type": "input_text", "text": "<environment_context>hidden</environment_context>"}],
                         "internal_chat_message_metadata_passthrough": metadata}},
            {"timestamp": "2026-08-23T10:00:02Z", "type": "response_item",
             "payload": {"type": "message", "role": "user",
                         "content": [{"type": "input_text", "text": "Actual question"}],
                         "internal_chat_message_metadata_passthrough": metadata}},
            {"timestamp": "2026-08-23T10:00:03Z", "type": "response_item",
             "payload": {"type": "message", "role": "assistant",
                         "content": [{"type": "output_text", "text": "Actual answer"}],
                         "internal_chat_message_metadata_passthrough": metadata}},
        ])

        result = process_codex_session(path)

        self.assertEqual(result["turns"], [
            {"role": "user", "text": "Actual question"},
            {"role": "assistant", "text": "Actual answer"},
        ])
        self.assertEqual(result["first_message"], "Actual question")
        self.assertEqual(result["project"], "/tmp/project")

    def test_prefers_legacy_events_when_both_formats_exist(self):
        path = self.write_rollout([
            {"timestamp": "2026-08-01T10:00:00Z", "type": "event_msg",
             "payload": {"type": "user_message", "message": "Question"}},
            {"timestamp": "2026-08-01T10:00:01Z", "type": "event_msg",
             "payload": {"type": "agent_message", "message": "Answer"}},
            {"timestamp": "2026-08-01T10:00:00Z", "type": "response_item",
             "payload": {"type": "message", "role": "assistant",
                         "content": [{"type": "output_text", "text": "Duplicate answer"}]}},
        ])

        result = process_codex_session(path)

        self.assertEqual(result["turns"], [
            {"role": "user", "text": "Question"},
            {"role": "assistant", "text": "Answer"},
        ])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from unittest.mock import patch

from relay_ssh.adapters import TmuxAdapter
from relay_ssh.models import Handoff


class Result:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TmuxAdapterTest(unittest.TestCase):
    @patch("relay_ssh.adapters.subprocess.run")
    def test_tmux_delivery_never_reads_agent_output(self, run) -> None:
        run.return_value = Result()
        item = Handoff(
            repository="owner/repo",
            issue_number=1,
            issue_title="Task",
            issue_url="https://github.com/owner/repo/issues/1",
            event_id=123,
            event_created_at="2026-08-29T00:00:00Z",
            target_label="relay:codex",
        )
        TmuxAdapter("relay:0.0").deliver(item, "hello")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0][:3], ["tmux", "display-message", "-p"])
        self.assertIn("load-buffer", commands[1])
        self.assertIn("paste-buffer", commands[2])
        self.assertEqual(commands[3], ["tmux", "send-keys", "-t", "relay:0.0", "Enter"])


if __name__ == "__main__":
    unittest.main()

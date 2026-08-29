from __future__ import annotations

import unittest

from relay_ssh.models import Handoff, RelayConfig, build_codex_prompt, validate_repository


class ModelsTest(unittest.TestCase):
    def test_repository_validation(self) -> None:
        self.assertEqual(validate_repository("openai/codex"), "openai/codex")
        with self.assertRaises(ValueError):
            validate_repository("codex")
        with self.assertRaises(ValueError):
            validate_repository("owner/repo/extra")

    def test_config_requires_adapter_fields(self) -> None:
        with self.assertRaises(ValueError):
            RelayConfig(repository="owner/repo", adapter="tmux")
        with self.assertRaises(ValueError):
            RelayConfig(repository="owner/repo", adapter="command")

    def test_codex_prompt_contains_protocol(self) -> None:
        handoff = Handoff(
            repository="owner/repo",
            issue_number=12,
            issue_title="Run the experiment",
            issue_url="https://github.com/owner/repo/issues/12",
            event_id=99,
            event_created_at="2026-08-29T00:00:00Z",
            target_label="relay:codex",
        )
        prompt = build_codex_prompt(handoff)
        self.assertIn("owner/repo", prompt)
        self.assertIn("#12", prompt)
        self.assertIn("relay:chatgpt", prompt)
        self.assertIn("Handoff event: 99", prompt)


if __name__ == "__main__":
    unittest.main()

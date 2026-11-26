"""Offline checks for the optional browser acceptance tooling."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tools import playwright_acceptance as acceptance

ROOT = Path(__file__).resolve().parents[1]


class PlaywrightTestingTests(unittest.TestCase):
    def test_sanitize_apex_url(self):
        for original, expected in [
            ("/app?P_INSTANCE=987&x=12", "/app?P_INSTANCE=<SESSION>&x=12"),
            ("/f?p=101:2:987::NO", "/f?p=101:2:<SESSION>::NO"),
            ("p=APP:HOME:987", "p=APP:HOME:<SESSION>"),
            ("p=101%3A2%3a987%3A", "p=101%3A2%3a<SESSION>%3A"),
            (":SESSION:987", ":SESSION:<SESSION>"),
            ("/app?id=987", "/app?id=987"),
        ]:
            with self.subTest(original=original):
                self.assertEqual(expected, acceptance.sanitize_apex_url(original))
                acceptance.assert_sanitized(expected)

    def test_find_secret_leaks(self):
        for text in ("Cookie: k=v", "set-cookie: k=v", '{"Cookie": "k=v"}'):
            self.assertEqual(["cookie header"], acceptance.find_secret_leaks(text))
        self.assertEqual(
            ["literal secret", "cookie header", "APEX session token"],
            acceptance.find_secret_leaks(
                "Cookie: fake-value\np=101:2:987\nOTP 654321", ("", "654321")
            ),
        )
        self.assertEqual([], acceptance.find_secret_leaks("Passed 10 cases"))

    def test_assert_sanitized_does_not_echo_raw_data(self):
        with self.assertRaisesRegex(AssertionError, "^Unsafe output: literal secret$"):
            acceptance.assert_sanitized("synthetic-password", ("synthetic-password",))
        with self.assertRaisesRegex(AssertionError, "^Unsafe output: APEX session token$"):
            acceptance.assert_sanitized("p_instance=1234567")

    def test_find_system_chrome_override_and_invalid_override(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "browser.exe"
            executable.touch(mode=0o700)
            with patch.dict(os.environ, PLAYWRIGHT_CHROME_PATH=str(executable)):
                self.assertEqual(str(executable), acceptance.find_system_chrome())
            with patch.dict(os.environ, PLAYWRIGHT_CHROME_PATH=directory):
                with self.assertRaisesRegex(FileNotFoundError, "PLAYWRIGHT_CHROME_PATH"):
                    acceptance.find_system_chrome()

    def test_find_system_chrome_uses_path_then_common_paths(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(acceptance.shutil, "which", return_value="/test/chromium"):
                self.assertEqual("/test/chromium", acceptance.find_system_chrome())
            with (
                patch.object(acceptance.shutil, "which", return_value=None),
                patch.object(acceptance.sys, "platform", "linux"),
                patch.object(Path, "is_file", return_value=True),
                patch.object(acceptance.os, "access", return_value=True),
            ):
                self.assertEqual(str(Path("/usr/bin/google-chrome")), acceptance.find_system_chrome())

    def test_launch_and_context_helpers(self):
        playwright = Mock()
        browser = acceptance.launch_headless_chrome(playwright, Path("browser.exe"), timeout=10)
        playwright.chromium.launch.assert_called_once_with(
            executable_path="browser.exe", headless=True, timeout=10
        )
        browser.new_context.side_effect = [object(), object()]
        self.assertIsNot(acceptance.new_isolated_context(browser), acceptance.new_isolated_context(browser))
        with self.assertRaisesRegex(ValueError, "storage_state"):
            acceptance.new_isolated_context(browser, storage_state="saved.json")
        self.assertEqual(2, browser.new_context.call_count)

    def test_skills_are_mirrored_and_guide_is_cross_linked(self):
        guide = ROOT / "docs/playwright-testing.md"
        skills = [
            ROOT / agent / "skills/playwright-browser-testing/SKILL.md"
            for agent in (".agents", ".claude")
        ]
        self.assertEqual(skills[0].read_bytes(), skills[1].read_bytes())
        for skill in skills:
            self.assertIn("(../../../docs/playwright-testing.md)", skill.read_text(encoding="utf-8"))
        guide_text = guide.read_text(encoding="utf-8")
        self.assertIn("(browser-mcp.md)", guide_text)
        self.assertIn("(../.agents/skills/playwright-browser-testing/SKILL.md)", guide_text)
        for path in ("AGENTS.md", "CLAUDE.md", "README.md"):
            self.assertIn("(docs/playwright-testing.md)", (ROOT / path).read_text(encoding="utf-8"))
        self.assertIn("(playwright-testing.md)", (ROOT / "docs/browser-mcp.md").read_text(encoding="utf-8"))

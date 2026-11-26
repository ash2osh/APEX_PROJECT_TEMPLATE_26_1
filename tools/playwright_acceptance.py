"""Optional helpers for synchronous Playwright acceptance scripts.

The caller supplies Playwright objects, so this module needs only the standard
library even when imported by an offline test runner.
"""

import os
import re
import shutil
import sys
from pathlib import Path

_COLON = r"(?::|%3a)"
_SESSION = re.compile(
    rf"(?P<prefix>"
    rf"\bp_instance=|"
    rf"\bp=[^:\s&#\"'<>]+?{_COLON}[^:\s&#\"'<>]+?{_COLON}|"
    rf"{_COLON}session{_COLON}"
    rf")[0-9]+(?=$|{_COLON}|[\s&#?\"'<>,;/)\]}}])",
    re.IGNORECASE,
)
_COOKIE_HEADER = re.compile(r"""\b(?:set-cookie|cookie)["']?\s*:""", re.IGNORECASE)


def find_system_chrome() -> str:
    """Return the path to an installed Chrome or Chromium executable."""
    override = os.environ.get("PLAYWRIGHT_CHROME_PATH")
    if override is not None:
        executable = Path(override).expanduser().absolute()
        if executable.is_file() and os.access(executable, os.X_OK):
            return str(executable)
        raise FileNotFoundError("PLAYWRIGHT_CHROME_PATH must name an executable file")

    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        executable = shutil.which(name)
        if executable:
            return executable

    if sys.platform == "darwin":
        candidates = [
            base / f"{app}.app" / "Contents" / "MacOS" / app
            for base in (Path("/Applications"), Path.home() / "Applications")
            for app in ("Google Chrome", "Chromium")
        ]
    elif sys.platform == "win32":
        candidates = [
            Path(base) / vendor / "Application" / "chrome.exe"
            for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
            if (base := os.environ.get(key))
            for vendor in ("Google/Chrome", "Chromium")
        ]
    else:
        candidates = [
            Path("/usr/bin/google-chrome"),
            Path("/opt/google/chrome/google-chrome"),
            Path("/usr/bin/chromium"),
            Path("/usr/bin/chromium-browser"),
            Path("/snap/bin/chromium"),
        ]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise FileNotFoundError("Install Chrome or Chromium or set PLAYWRIGHT_CHROME_PATH")


def launch_headless_chrome(playwright_ctx, executable_path=None, **kwargs):
    """Launch the installed browser using an active sync_playwright object."""
    return playwright_ctx.chromium.launch(
        executable_path=os.fspath(executable_path) if executable_path is not None else find_system_chrome(),
        headless=True,
        **kwargs,
    )


def new_isolated_context(browser, **kwargs):
    """Create a fresh role context with no imported login state."""
    if kwargs.get("storage_state") is not None:
        raise ValueError("Role contexts must start without storage_state")
    return browser.new_context(**kwargs)


def sanitize_apex_url(url: str) -> str:
    """Replace numeric APEX session values while preserving URL spelling."""
    return _SESSION.sub(r"\g<prefix><SESSION>", url)


def find_secret_leaks(text: str, secrets=()) -> list[str]:
    """Return categories only, so findings can be reported without raw data."""
    findings = []
    if any(secret and secret in text for secret in secrets):
        findings.append("literal secret")
    if _COOKIE_HEADER.search(text):
        findings.append("cookie header")
    if _SESSION.search(text):
        findings.append("APEX session token")
    return findings


def assert_sanitized(text: str, secrets=()) -> None:
    """Reject text containing a known secret, cookie header, or session token."""
    findings = find_secret_leaks(text, secrets)
    if findings:
        raise AssertionError("Unsafe output: " + ", ".join(findings))

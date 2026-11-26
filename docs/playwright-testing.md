# Optional Playwright acceptance testing

Use Playwright for repeatable APEX role-based access and workflow checks
that require multiple independent logins. Use [Browser MCP selection](browser-mcp.md)
for interactive Chrome or Firefox inspection. Follow the checkout's project-owned
browser rules.

## Run a local DEV check

1. Install `uv` and system Chrome or Chromium. The helper checks PATH and
   common Linux, macOS, and Windows locations. Set `PLAYWRIGHT_CHROME_PATH`
   to the executable's full path to override discovery. There is no need to
   run `playwright install`.
2. Keep the script and any local credential file under the ignored `scratch/`
   directory. Have the script read credentials and OTPs from environment
   variables or the ignored file. Keep credentials out of terminal history,
   MCP arguments, and Git. Use dedicated test accounts for each role.
3. From the repository root, run:

       uv run --with playwright python -m scratch.acceptance

4. Check the exact DEV origin (scheme, host, and port), app identity, and
   expected login destination against trusted configuration before login.
   Verify redirects and stop on an unexpected destination before filling
   credentials or submitting a form. Keep staging and production out of
   the allowed targets. Use disposable test records and agreed cleanup
   steps for authorized mutations.

## Script pattern

```python
from playwright.sync_api import sync_playwright

from tools.playwright_acceptance import launch_headless_chrome, new_isolated_context

with sync_playwright() as playwright:
    with launch_headless_chrome(playwright) as browser:
        with new_isolated_context(browser) as requester, new_isolated_context(browser) as reviewer:
            requester_page = requester.new_page()
            reviewer_page = reviewer.new_page()
            # Verify the DEV target before signing each role in on its own page.
```

Log each role in inside its own context. Verify the expected workflow
transition and that the other role sees only the expected actions. Where
authorized, verify that the application rejects a forbidden action as well
as hiding its UI control. Use a unique fixture per run.

## Sanitize every report

Publish case names and outcomes. Use `sanitize_apex_url` on URLs that are
needed for the report, and call `assert_sanitized(report, secrets=...)` with
the actual credentials, OTPs, and any other known sensitive values before
printing or saving it. The assertion reports categories without echoing
the matching text. This check covers literal secrets, cookie headers, and
recognized numeric APEX session formats. Review the report for other
sensitive data, including encoded secrets and business data. Keep Playwright
debug logging, screenshots, HTML dumps, traces, and saved login state off
for routine runs. Catch exceptions at the runner boundary and report a
sanitized failure summary instead of a raw traceback.

See the [Playwright skill](../.agents/skills/playwright-browser-testing/SKILL.md).

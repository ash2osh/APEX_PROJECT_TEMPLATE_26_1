---
name: playwright-browser-testing
description: Use isolated Playwright browser contexts for repeatable multi-user APEX role and workflow acceptance in DEV.
---

# Playwright browser testing

Use Playwright when one repeatable acceptance case needs multiple signed-in
roles, such as verifying workflow handoff or checking which roles can see or
use an action. Use the checkout's selected Chrome or Firefox DevTools MCP for
interactive inspection and debugging. Follow project-owned browser rules.

1. Read the [Playwright guide](../../../docs/playwright-testing.md). Verify the
   exact DEV origin and application against trusted project configuration
   before sending credentials. Check redirects, and stop on an unexpected
   destination. Use dedicated test accounts and fixtures. Obtain authorization
   for any action that changes application data or workflow state.
2. Run the local script with `uv run --with playwright` and an installed
   Chrome or Chromium executable. No browser-binary download is needed.
3. Open a fresh `browser.new_context()` for each role. Read credentials and
   one-time codes from environment variables or an ignored local file inside
   the script. Never pass them in MCP tool arguments or on the command line.
4. Publish only sanitized results. Remove raw credentials, cookies, and
   session state. Sanitize APEX URLs with `sanitize_apex_url` and run
   `assert_sanitized` with the actual secrets and codes on report text before
   it leaves the process. Keep raw exceptions, HTML, traces, screenshots,
   and storage state out of reports. Close all contexts and the browser.

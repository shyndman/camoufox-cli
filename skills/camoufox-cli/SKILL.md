---
name: camoufox-cli
description: Anti-detect browser automation CLI & Skills for AI agents. Use when the user needs to interact with websites with bot detection, CAPTCHAs, or anti-bot blocks, including navigating pages, filling forms, clicking buttons, taking screenshots, extracting data, testing web apps, or automating any browser task that requires bypassing fingerprint checks.
---

# Anti-Detect Browser Automation with camou

## What Makes This Different

camou is built on Camoufox (anti-detect Firefox) with C++-level fingerprint spoofing:
- `navigator.webdriver` = `false`
- Real browser plugins, randomized canvas/WebGL/audio fingerprints
- Real Firefox UA string -- passes bot detection on sites that block Chromium automation

Use camou instead of agent-browser when the target site has bot detection.

## Core Workflow

Every browser automation follows this pattern:

1. **Navigate**: `camou open <url>`
2. **Snapshot**: `camou snapshot -i` (get element refs like `@e1`, `@e2`)
3. **Interact**: Use refs to click, fill, select
4. **Re-snapshot**: After navigation or DOM changes, get fresh refs
5. **Close**: `camou close` (close the browser when the entire task is fully complete; keep it open if the user may have follow-up instructions)

```bash
camou open https://example.com/form
camou snapshot -i
# Output: - textbox "Email" [ref=e1]
#         - textbox "Password" [ref=e2]
#         - button "Submit" [ref=e3]

camou fill @e1 "user@example.com"
camou fill @e2 "password123"
camou click @e3
camou snapshot -i  # Check result
```

## Command Chaining

Commands can be chained with `&&` in a single shell invocation. The browser persists between commands via a background daemon, so chaining is safe and more efficient than separate calls.

```bash
# Chain open + snapshot in one call
camou open https://example.com && camou snapshot -i

# Chain multiple interactions
camou fill @e1 "user@example.com" && camou fill @e2 "password123" && camou click @e3

# Navigate and capture
camou open https://example.com && camou screenshot page.png
```

**When to chain:** Use `&&` when you don't need to read the output of an intermediate command before proceeding (e.g., open + screenshot). Run commands separately when you need to parse the output first (e.g., snapshot to discover refs, then interact using those refs).

## Essential Commands

```bash
# Navigation
camou open <url>              # Navigate to URL (starts daemon if needed)
camou back                    # Go back
camou forward                 # Go forward
camou reload                  # Reload page
camou url                     # Print current URL
camou title                   # Print page title
camou close                   # Close browser and stop daemon
camou close --all             # Close all sessions

# Snapshot
camou snapshot                # Full aria tree of page
camou snapshot -i             # Interactive elements only (recommended)
camou snapshot -s "#selector" # Scope to CSS selector

# Interaction (use @refs from snapshot)
camou click @e1               # Click element
camou fill @e1 "text"         # Clear + type into input
camou type @e1 "text"         # Type without clearing (append)
camou select @e1 "option"     # Select dropdown option
camou check @e1               # Toggle checkbox
camou hover @e1               # Hover over element
camou press Enter             # Press keyboard key
camou press "Control+a"       # Key combination

# Data Extraction
camou text @e1                # Get text content of element
camou text body               # Get all page text (CSS selector)
camou eval "document.title"   # Execute JavaScript

# Capture
camou screenshot              # Screenshot as JSON {"base64": "..."}
camou screenshot page.png     # Screenshot to file
camou screenshot --full p.png # Full page screenshot
camou pdf output.pdf          # Save page as PDF

# Scroll & Wait
camou scroll down             # Scroll down 500px
camou scroll up               # Scroll up 500px
camou scroll left             # Scroll left 500px
camou scroll right            # Scroll right 500px
camou scroll down 1000        # Scroll down 1000px
camou scroll right 800        # Scroll right 800px
camou wait @e1                # Wait for element to appear
camou wait 2000               # Wait milliseconds
camou wait --url "*/dashboard" # Wait for URL pattern

# Tabs
camou tabs                    # List open tabs
camou switch 2                # Switch to tab by index
camou close-tab               # Close current tab

# Cookies & State
camou cookies                 # Dump cookies as JSON
camou cookies import file.json # Import cookies
camou cookies export file.json # Export cookies

# Sessions
camou sessions                # List active sessions
camou --session work open <url> # Use named session
camou close --all             # Close all sessions

# Setup
camou install                 # Download Camoufox browser
camou install --with-deps     # Download browser + system libs (Linux)
```

## Common Patterns

### Form Submission

```bash
camou open https://example.com/signup
camou snapshot -i
camou fill @e1 "Jane Doe"
camou fill @e2 "jane@example.com"
camou select @e3 "California"
camou check @e4
camou click @e5
camou snapshot -i  # Verify submission result
```

### Data Extraction

```bash
camou open https://example.com/products
camou snapshot -i
camou text @e5                # Get specific element text
camou eval "document.title"   # Get page title via JS
camou screenshot results.png  # Visual capture
```

### Cookie Management (Persist Login)

```bash
# Login and export cookies
camou open https://app.example.com/login
camou snapshot -i
camou fill @e1 "user"
camou fill @e2 "pass"
camou click @e3
camou cookies export auth.json

# Restore in future session
camou open https://app.example.com
camou cookies import auth.json
camou reload
```

For long-lived accounts where the site also verifies device stability (not just the cookie), combine this with `--persistent` so the fingerprint stays fixed alongside the cookies — see the Persistent Identity section below.

### Multiple Tabs

```bash
camou open https://site-a.com
camou eval "window.open('https://site-b.com')"
camou tabs                    # List tabs
camou switch 1                # Switch to second tab
camou snapshot -i
```

### Parallel Sessions

```bash
camou --session s1 open https://site-a.com
camou --session s2 open https://site-b.com
camou sessions                # List both
camou --session s1 snapshot -i
camou --session s2 snapshot -i
```

### Visual Browser (Debugging)

```bash
camou --headed open https://example.com
camou snapshot -i
camou screenshot debug.png
```

## Session Management and Cleanup

When running multiple agents or automations concurrently, always use named sessions to avoid conflicts:

```bash
camou --session agent1 open https://site-a.com
camou --session agent2 open https://site-b.com
camou sessions                  # Check active sessions
```

Always close your browser session when done to avoid leaked processes:

```bash
camou close                     # Close default session
camou --session agent1 close    # Close specific session
camou close --all               # Close all sessions
```

If a previous session was not closed properly, the daemon may still be running. Use `camou close` to clean it up before starting new work.

## Timeouts and Slow Pages

Some pages take time to fully load, especially those with dynamic content or heavy JavaScript. Use explicit waits before taking a snapshot:

```bash
# Wait for a specific element to appear
camou wait @e1
camou snapshot -i

# Wait for a URL pattern (useful after redirects)
camou wait --url "*/dashboard"
camou snapshot -i

# Wait a fixed duration as a last resort
camou wait 3000
camou snapshot -i
```

When dealing with slow pages, always wait before snapshotting. If you snapshot too early, elements may be missing from the output.

## Ref Lifecycle (Important)

Refs (`@e1`, `@e2`, etc.) are **temporary identifiers** assigned by sequential numbering during each snapshot. They are invalidated when the page changes.

**Always re-snapshot after:**

- Clicking links or buttons that navigate
- Form submissions
- Dynamic content loading (dropdowns, modals, lazy-loaded content)
- Scrolling that triggers new content

```bash
# CORRECT: re-snapshot after navigation
camou click @e5              # Navigates to new page
camou snapshot -i            # MUST re-snapshot
camou click @e1              # Use new refs

# CORRECT: re-snapshot after dynamic changes
camou click @e1              # Opens dropdown
camou snapshot -i            # See dropdown items
camou click @e7              # Select item

# WRONG: using refs without snapshot
camou open https://example.com
camou click @e1              # Ref doesn't exist yet!

# WRONG: using old refs after navigation
camou click @e5              # Navigates away
camou click @e3              # STALE REF - wrong element!
```

Always take a fresh snapshot before interacting with elements after navigation or page changes.

## Troubleshooting

### "Ref @eN not found"

The ref was invalidated. Re-snapshot to get fresh refs:

```bash
camou snapshot -i
```

### Element Not Visible in Snapshot

```bash
# Scroll down to reveal element
camou scroll down 1000
camou snapshot -i

# Or wait for dynamic content
camou wait 2000
camou snapshot -i
```

### Too Many Elements in Snapshot

```bash
# Scope to a specific container
camou snapshot -s "#main-content"
camou snapshot -i -s "form.login"
```

### Page Not Fully Loaded

```bash
# Wait for URL pattern after redirect
camou wait --url "*/dashboard"
camou snapshot -i

# Wait a fixed duration as last resort
camou wait 3000
camou snapshot -i
```

## Global Flags

```
--session <name>       Named session (default: "default")
--headed               Show browser window (default: headless)
--timeout <seconds>    Daemon idle timeout (default: 1800)
--json                 Output as JSON instead of human-readable
--persistent           Persistent identity at the default path (~/.camoufox-cli/profiles/<session>)
--user-data-dir <path> Persistent identity at an explicit directory
--clone-from <name>    Ephemeral session seeded from a persistent profile (discarded on close)
--proxy <url>          Proxy server (http:// or https://; auth: http://user:pass@host:port)
--no-geoip             Disable automatic GeoIP spoofing (auto-enabled with --proxy)
--locale <tag>         Force browser locale (e.g. "en-US" or "en-US,zh-CN")
```

## Persistent Identity

**Do not use `--persistent` or `--user-data-dir` unless the user explicitly asks for a saved/persistent identity.** They write a profile directory to disk that survives every run and is never cleaned up automatically; defaulting to them litters `~/.camoufox-cli/profiles/`. For ordinary navigation, scraping, form-filling, and debugging, omit both flags — the ephemeral default is correct.

By default, every launch gets a fresh random fingerprint. To reuse the same fingerprint + cookies across launches, use `--persistent` (default path `~/.camoufox-cli/profiles/<session>`) or `--user-data-dir <path>` for an explicit directory — fingerprint/OS/canvas+font seeds are frozen on first launch (delete the directory to reset); `--locale` and proxy-derived timezone/geolocation are stored but refreshed whenever you pass the flag; `--proxy` / `--no-geoip` are never stored, so pass them every launch.

**Use it only when** the same device should see the same fingerprint across visits (account-bound tasks, parallel independent identities, or when `cookies import/export` alone isn't enough because the site also checks device stability), and the user has asked for that persistence. **Skip it** for one-off scraping or quick debugging.

```bash
# Parallel identities, each with its own fingerprint + cookies
camou --session a --user-data-dir ~/.camoufox-cli/profiles/alice open https://app.example.com
camou --session b --user-data-dir ~/.camoufox-cli/profiles/bob   open https://app.example.com

# Reset an identity: just remove the directory
rm -rf ~/.camoufox-cli/profiles/alice
```

## Ephemeral Clones

`--clone-from <source>` starts a session whose profile is a throwaway copy of the
persistent profile `~/.camoufox-cli/profiles/<source>`. The session inherits the
source's cookies/login and frozen fingerprint but **writes nothing back** — the
copy is deleted when the session's daemon closes. Use it to give an automation
read-only access to a profile you logged into by hand, without risking the saved
state.

```bash
# Log in by hand once into a persistent profile
camou --session human --persistent --headed open https://app.example.com
camou --session human close

# Run automations off a throwaway copy — the original is never touched
camou --session bot --clone-from human open https://app.example.com
camou --session bot close   # clone discarded
```

`--clone-from` cannot be combined with `--persistent` or `--user-data-dir`.

## Documentation

- [camou documentation](https://github.com/shyndman/camoufox-cli) -- Full README, setup guide, installation, and command reference

# Command Reference

Complete reference for all camou commands. For quick start and common patterns, see SKILL.md.

## Navigation

```bash
camou open <url>              # Navigate to URL (starts daemon if needed)
                                     # Auto-prepends https:// if no protocol given
camou back                    # Go back
camou forward                 # Go forward
camou reload                  # Reload page
camou url                     # Print current URL
camou title                   # Print page title
camou close                   # Close browser and stop daemon
camou close --all             # Close all sessions
```

## Snapshot (Page Analysis)

```bash
camou snapshot                # Full accessibility tree
camou snapshot -i             # Interactive elements only (recommended)
camou snapshot -s "#main"     # Scope to CSS selector
camou snapshot -i -s "form"   # Interactive + scoped
```

## Interactions (use @refs from snapshot)

```bash
camou click @e1               # Click element
camou fill @e1 "text"         # Clear and type
camou type @e1 "text"         # Type without clearing (append)
camou select @e1 "value"      # Select dropdown option
camou check @e1               # Toggle checkbox
camou hover @e1               # Hover over element
camou press Enter             # Press key
camou press "Control+a"       # Key combination
```

## Get Information

```bash
camou text @e1                # Get element text (by ref)
camou text body               # Get all page text (by CSS selector)
camou url                     # Get current URL
camou title                   # Get page title
camou eval "document.title"   # Run JavaScript expression
```

## Screenshots and PDF

```bash
camou screenshot              # Screenshot to stdout (base64)
camou screenshot page.png     # Save to file
camou screenshot --full p.png # Full page screenshot
camou pdf output.pdf          # Save page as PDF
```

## Scroll

```bash
camou scroll down             # Scroll down 500px (default)
camou scroll up               # Scroll up 500px
camou scroll down 1000        # Scroll down 1000px
```

## Wait

```bash
camou wait @e1                # Wait for element to appear
camou wait 2000               # Wait milliseconds
camou wait --url "*/dashboard" # Wait for URL pattern
```

## Tabs

```bash
camou tabs                    # List open tabs
camou switch 2                # Switch to tab by index
camou close-tab               # Close current tab
```

## Cookies

```bash
camou cookies                 # Dump cookies as JSON
camou cookies import file.json # Import cookies from file
camou cookies export file.json # Export cookies to file
```

## Sessions

```bash
camou sessions                # List active sessions
camou --session <name> <cmd>  # Run command in named session
camou close --all             # Close all sessions
```

## JavaScript

```bash
camou eval "document.title"   # Simple expression
camou eval "document.querySelectorAll('img').length"
```

For complex JavaScript with nested quotes, use shell escaping carefully or pipe via stdin.

## Setup

```bash
camou install                 # Download Camoufox browser
camou install --with-deps     # Download browser + system libs (Linux)
```

## Global Options

```bash
camou --session <name> ...    # Isolated browser session
camou --headed ...            # Show browser window (not headless)
camou --json ...              # JSON output for parsing
camou --timeout <seconds> ... # Daemon idle timeout (default: 1800)
camou --persistent [path] ... # Persistent identity — reuse the same fingerprint + cookies
                                     # across launches (default: ~/.camoufox-cli/profiles/<session>)
camou --proxy <url> ...      # Proxy server (e.g. http://host:port or http://user:pass@host:port)
camou --no-geoip ...         # Disable automatic GeoIP spoofing (auto-enabled with --proxy)
camou --locale <tag> ...     # Force browser locale (e.g. "en-US" or "en-US,zh-CN")
```

### `--persistent` in detail

Stores fingerprint, OS, canvas/font seeds, locale, and proxy-derived timezone/geolocation in `<path>/camoufox-cli.json` and reloads it on every launch with the same path. Fingerprint/OS/seeds are frozen — delete the directory to reset. `--locale` overwrites the stored locale when passed; `--proxy` + GeoIP re-derives timezone/geolocation each launch and writes back. `--proxy` and `--no-geoip` themselves are never stored. See the README for the full mental model.

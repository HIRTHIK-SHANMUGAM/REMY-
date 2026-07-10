"""
Browser automation — Playwright-driven web control for REMY.

Design notes:
- Playwright's sync API is not event-loop-safe and its objects are not
  thread-safe, so a single dedicated worker thread owns the browser; tool
  calls submit closures to it and wait for the result.
- The permission engine escalates navigation to auth/financial URL patterns
  (BROWSER_APPROVAL_PATTERNS in remy.permissions.engine) to user approval.
- First navigation to any new domain is audit-logged and the user notified.
- Every navigate/fill/click is recorded to ACTIVE_MEMORY (tiered store) and
  the audit log (args included, so form fills are debuggable).
- Vision descriptions cost tokens: screenshot_and_describe only calls the
  vision model when is_visual_blocking=True; otherwise it saves the PNG and
  says so.
- Tests inject a fake session via set_session(); no live sites are touched.
"""

import json
import queue
import threading
from datetime import datetime
from urllib.parse import urlparse

from remy.config import DATA_DIR, config

DOMAINS_FILE = DATA_DIR / "browser_domains.json"


# ── session: one worker thread owns the real browser ─────────────────

class BrowserSession:
    """Owns a headless Chromium page on a dedicated thread."""

    def __init__(self) -> None:
        self._jobs: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._start_error: str | None = None
        self._ready = threading.Event()

    def _loop(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            import os
            exe = os.environ.get("REMY_CHROMIUM_PATH") or None
            browser = self._pw.chromium.launch(
                headless=True, executable_path=exe)
            self._page = browser.new_page()
        except Exception as exc:
            self._start_error = (
                f"Browser unavailable ({exc}). Install with: "
                'pip install "remy[browser]" && playwright install chromium')
            self._ready.set()
            return
        self._ready.set()
        while True:
            fn, out = self._jobs.get()
            if fn is None:
                break
            try:
                out["result"] = fn(self._page)
            except Exception as exc:
                out["error"] = str(exc)
            out["done"].set()

    def run(self, fn, timeout_s: float = 60):
        """Execute fn(page) on the browser thread and return its result."""
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, daemon=True,
                                            name="remy-browser")
            self._thread.start()
        self._ready.wait(timeout=120)
        if self._start_error:
            raise RuntimeError(self._start_error)
        out = {"done": threading.Event()}
        self._jobs.put((fn, out))
        if not out["done"].wait(timeout_s):
            raise TimeoutError("browser action timed out")
        if "error" in out:
            raise RuntimeError(out["error"])
        return out.get("result")


_session: BrowserSession | None = None


def get_session() -> BrowserSession:
    global _session
    if _session is None:
        _session = BrowserSession()
    return _session


def set_session(session) -> None:
    """Inject a fake session (tests) or reset with None."""
    global _session
    _session = session


# ── helpers ──────────────────────────────────────────────────────────

def _remember(action: str) -> None:
    """Record a browser action into hot episodic memory (best-effort)."""
    try:
        from remy.memory.tiered import get_memory
        get_memory().add_episode(f"[browser] {action}")
    except Exception:
        pass


def _note_domain_first_visit(url: str) -> None:
    """Audit + notify on the first navigation to a previously unseen domain."""
    host = urlparse(url).netloc.lower()
    if not host:
        return
    seen: list[str] = []
    if DOMAINS_FILE.exists():
        try:
            seen = json.loads(DOMAINS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            seen = []
    if host in seen:
        return
    seen.append(host)
    DOMAINS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DOMAINS_FILE.write_text(json.dumps(seen, indent=2))
    from remy.permissions import audit
    audit.log_event("browser_domain_first_visit", {"domain": host}, "auto",
                    "auto-approved", outcome="new domain recorded",
                    actor="browser")
    from remy.permissions.approvals import _notify_user
    _notify_user({"tool": "browser", "reason": f"first visit to {host}"})


# ── tool implementations (module-level for testability) ──────────────

def navigate_to_impl(url: str) -> str:
    if not urlparse(url).scheme:
        url = "https://" + url
    _note_domain_first_visit(url)

    def act(page):
        page.goto(url)
        return page.title()

    try:
        title = get_session().run(act)
    except (RuntimeError, TimeoutError) as exc:
        _remember(f"navigation to {url} failed: {exc}")
        return f"failure: {exc}"
    _remember(f"navigated to {url} — page title: {title!r}")
    return f"success — page_title: {title!r}"


def fill_form_impl(selectors_json: str) -> str:
    try:
        fields = json.loads(selectors_json)
        assert isinstance(fields, dict)
    except (json.JSONDecodeError, AssertionError):
        return 'failure: selectors_json must be a JSON object {"selector": "value"}'

    def act(page):
        count = 0
        for selector, value in fields.items():
            page.fill(selector, str(value))
            count += 1
        return count

    try:
        filled = get_session().run(act)
    except (RuntimeError, TimeoutError) as exc:
        _remember(f"form fill failed: {exc}")
        return f"failure: {exc}"
    _remember(f"filled {filled} form field(s): {list(fields.keys())}")
    return f"success — filled_count: {filled}"


def click_element_impl(selector: str, wait_ms: int = 0) -> str:
    def act(page):
        if wait_ms:
            page.wait_for_timeout(min(wait_ms, 10000))
        page.click(selector)
        return True

    try:
        get_session().run(act)
    except (RuntimeError, TimeoutError) as exc:
        _remember(f"click on {selector!r} failed: {exc}")
        return f"failure: {exc}"
    _remember(f"clicked element {selector!r}")
    return "success"


def extract_text_impl(selector: str) -> str:
    def act(page):
        el = page.query_selector(selector)
        return el.inner_text() if el else None

    try:
        text = get_session().run(act)
    except (RuntimeError, TimeoutError) as exc:
        return f"failure: {exc}"
    if text is None:
        return "not found"
    return text[:8000]


def screenshot_and_describe_impl(is_visual_blocking: bool = False) -> str:
    shots_dir = config.ALLOWED_DIRS[0] / "screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    path = shots_dir / f"browser-{datetime.now().strftime('%Y%m%d-%H%M%S')}.png"

    def act(page):
        page.screenshot(path=str(path))
        return str(path)

    try:
        saved = get_session().run(act)
    except (RuntimeError, TimeoutError) as exc:
        return f"failure: {exc}"

    if not is_visual_blocking:
        return (f"Screenshot saved: {saved}. Vision description skipped — "
                "pass is_visual_blocking=true only when the task cannot "
                "proceed without understanding the visuals (it costs tokens).")
    try:
        from remy.agents.base import describe_image
        description = describe_image(
            saved, "Describe the visible page UI: layout, key elements, "
                   "any prices/options/buttons relevant to acting on it.")
    except Exception as exc:
        description = f"(vision model unavailable: {exc})"
    _remember(f"described browser screenshot {saved}")
    return f"Screenshot: {saved}\n\n{description}"


def get_page_links_impl() -> str:
    def act(page):
        return page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({text: e.innerText.trim().slice(0,80), "
            "href: e.href}))")

    try:
        links = get_session().run(act)
    except (RuntimeError, TimeoutError) as exc:
        return f"failure: {exc}"
    if not links:
        return "no links found"
    return "\n".join(f"- {l['text'] or '(no text)'} → {l['href']}"
                     for l in links[:100])


def wait_for_element_impl(selector: str, timeout_ms: int = 5000) -> str:
    def act(page):
        try:
            page.wait_for_selector(selector, timeout=min(timeout_ms, 30000))
            return True
        except Exception:
            return False

    try:
        found = get_session().run(act, timeout_s=(timeout_ms / 1000) + 30)
    except (RuntimeError, TimeoutError) as exc:
        return f"failure: {exc}"
    return "true" if found else "false"


def get_current_url_impl() -> str:
    def act(page):
        return page.url

    try:
        return get_session().run(act)
    except (RuntimeError, TimeoutError) as exc:
        return f"failure: {exc}"


def record_task_outcome_impl(outcome: str) -> str:
    """Store a completed browser task's outcome as a high-confidence fact."""
    from remy.memory.tiered import get_memory
    fact = get_memory().add_fact(outcome, confidence=0.95)
    _remember(f"task outcome recorded: {outcome}")
    return f"Outcome stored as fact {fact['id']} (confidence 0.95)."


# ── MCP registration ─────────────────────────────────────────────────

def register(mcp, guard):

    @mcp.tool()
    def navigate_to(url: str) -> str:
        """Open a URL in REMY's browser. Auth/financial sites need approval."""
        return guard(navigate_to_impl, "navigate_to")(url)

    @mcp.tool()
    def fill_form(selectors_json: str) -> str:
        """Fill form fields. selectors_json: JSON object {css_selector: value}."""
        return guard(fill_form_impl, "fill_form")(selectors_json)

    @mcp.tool()
    def click_element(selector: str, wait_ms: int = 0) -> str:
        """Click an element by CSS selector, optionally waiting first."""
        return guard(click_element_impl, "click_element")(selector, wait_ms)

    @mcp.tool()
    def extract_text(selector: str) -> str:
        """Extract the inner text of the first element matching the selector."""
        return guard(extract_text_impl, "extract_text")(selector)

    @mcp.tool()
    def screenshot_and_describe(is_visual_blocking: bool = False) -> str:
        """
        Screenshot the current page. Only set is_visual_blocking=true when the
        task cannot proceed without a vision description (costs tokens).
        """
        return guard(screenshot_and_describe_impl,
                     "screenshot_and_describe")(is_visual_blocking)

    @mcp.tool()
    def get_page_links() -> str:
        """List all links on the current page (text + href)."""
        return guard(get_page_links_impl, "get_page_links")()

    @mcp.tool()
    def wait_for_element(selector: str, timeout_ms: int = 5000) -> str:
        """Wait for an element to appear; returns 'true' or 'false'."""
        return guard(wait_for_element_impl, "wait_for_element")(selector, timeout_ms)

    @mcp.tool()
    def get_current_url() -> str:
        """Return the browser's current page URL."""
        return guard(get_current_url_impl, "get_current_url")()

    @mcp.tool()
    def record_task_outcome(outcome: str) -> str:
        """
        After completing a web task (booking, purchase, submission), store the
        concrete outcome (ids, confirmations, dates) as a high-confidence fact.
        """
        return guard(record_task_outcome_impl, "record_task_outcome")(outcome)

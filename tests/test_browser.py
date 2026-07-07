"""
Browser automation tests — fake page fixture, no live sites (per spec).
The FakePage mimics the Playwright page surface the tools use; the FakeSession
runs closures inline exactly like the real single-owner browser thread.
"""

import json
import threading
import time

import pytest

from remy.memory.tiered import ACTIVE_FILE
from remy.permissions import approvals, audit
from remy.permissions.engine import (
    PermissionDenied,
    authorize,
    url_requires_approval,
)
from remy.tools import browser


class FakePage:
    """Backed by a parsed 'mock HTML' dict: selector → text."""

    def __init__(self):
        self.url = "about:blank"
        self._title = ""
        self.content = {}
        self.links = []
        self.filled: dict[str, str] = {}
        self.clicked: list[str] = []

    def goto(self, url):
        self.url = url
        # mock fixture: a tiny flight-results page
        self._title = "MockAir — Flight Results"
        self.content = {
            "h1": "Flights to Paris",
            ".result:nth-child(1)": "AC123 · 08:40 → 21:05 · $612",
            ".result:nth-child(2)": "AF356 · 11:20 → 23:45 · $658",
        }
        self.links = [
            {"text": "Book AC123", "href": f"{url}/book/AC123"},
            {"text": "Book AF356", "href": f"{url}/book/AF356"},
        ]

    def title(self):
        return self._title

    def fill(self, selector, value):
        if selector.startswith("#missing"):
            raise RuntimeError(f"no element matches {selector}")
        self.filled[selector] = value

    def click(self, selector):
        self.clicked.append(selector)

    def query_selector(self, selector):
        text = self.content.get(selector)
        if text is None:
            return None
        class El:
            def inner_text(self_inner):
                return text
        return El()

    def eval_on_selector_all(self, selector, js):
        return self.links

    def wait_for_selector(self, selector, timeout=0):
        if selector not in self.content:
            raise TimeoutError(f"{selector} never appeared")

    def wait_for_timeout(self, ms):
        pass

    def screenshot(self, path):
        with open(path, "wb") as f:
            f.write(b"\x89PNG fake")


class FakeSession:
    def __init__(self, page):
        self.page = page

    def run(self, fn, timeout_s=60):
        return fn(self.page)


@pytest.fixture()
def page():
    fake = FakePage()
    browser.set_session(FakeSession(fake))
    if browser.DOMAINS_FILE.exists():
        browser.DOMAINS_FILE.unlink()
    yield fake
    browser.set_session(None)


# ── mock-page behaviour ──────────────────────────────────────────

def test_navigate_and_extract(page):
    result = browser.navigate_to_impl("https://mockair.test/search?to=PAR")
    assert result.startswith("success")
    assert "MockAir" in result
    assert browser.get_current_url_impl() == "https://mockair.test/search?to=PAR"
    assert "Flights to Paris" == browser.extract_text_impl("h1")
    assert "AC123" in browser.extract_text_impl(".result:nth-child(1)")
    assert browser.extract_text_impl("#nonexistent") == "not found"


def test_fill_form_invokes_selectors(page):
    fields = {"#from": "Toronto", "#to": "Paris", "#date": "2026-07-20"}
    result = browser.fill_form_impl(json.dumps(fields))
    assert result == "success — filled_count: 3"
    assert page.filled == fields


def test_fill_form_bad_selector_reports_failure(page):
    result = browser.fill_form_impl(json.dumps({"#missing-field": "x"}))
    assert result.startswith("failure")


def test_fill_form_rejects_non_json(page):
    assert browser.fill_form_impl("not json").startswith("failure")


def test_click_and_links_and_wait(page):
    browser.navigate_to_impl("https://mockair.test/")
    assert browser.click_element_impl(".result:nth-child(1)") == "success"
    assert page.clicked == [".result:nth-child(1)"]
    links = browser.get_page_links_impl()
    assert "Book AC123" in links and "/book/AC123" in links
    assert browser.wait_for_element_impl("h1") == "true"
    assert browser.wait_for_element_impl("#never", timeout_ms=100) == "false"


def test_screenshot_gated_behind_visual_blocking_flag(page):
    result = browser.screenshot_and_describe_impl(is_visual_blocking=False)
    assert "Vision description skipped" in result
    assert "Screenshot saved" in result


# ── denylist ─────────────────────────────────────────────────────

def test_url_denylist_patterns():
    blocked = [
        "https://google.com/accounts/signin",
        "https://accounts.google.com/v3/signin",
        "https://github.com/login",
        "https://www.mybank.com/portal",
        "https://www.paypal.com/checkout",
    ]
    for url in blocked:
        needs, why = url_requires_approval(url)
        assert needs, url
        assert "pattern" in why
    for url in ["https://mockair.test/search", "https://github.com/anthropics"]:
        needs, _ = url_requires_approval(url)
        assert not needs, url


def test_navigate_to_auth_site_blocks_for_approval(page):
    """google.com/accounts must create an approval request, not just run."""
    def deny_soon():
        for _ in range(50):
            pend = approvals.pending_requests()
            if pend:
                assert pend[0]["tool"] == "navigate_to"
                approvals.resolve(pend[0]["id"], approve=False)
                return
            time.sleep(0.1)

    t = threading.Thread(target=deny_soon)
    t.start()
    with pytest.raises(PermissionDenied):
        authorize("navigate_to", {"url": "https://google.com/accounts/signin"})
    t.join()
    entries = audit.read_recent(10)
    assert any(e["tool"] == "navigate_to" and e["decision"] == "denied"
               for e in entries)


# ── audit + memory integration ───────────────────────────────────

def test_audit_trail_records_each_browser_action(page):
    before = len(audit.read_recent(1000))
    assert authorize("navigate_to", {"url": "https://mockair.test/"}) == "logged"
    assert authorize("fill_form", {"selectors_json": '{"#to": "Paris"}'}) == "logged"
    assert authorize("click_element", {"selector": ".book"}) == "logged"
    assert authorize("extract_text", {"selector": "h1"}) == "auto-approved"
    entries = audit.read_recent(1000)
    assert len(entries) == before + 4
    fill_entry = next(e for e in entries if e["tool"] == "fill_form")
    assert "Paris" in json.dumps(fill_entry["args"])  # selectors+values logged


def test_browser_actions_land_in_active_memory(page):
    if ACTIVE_FILE.exists():
        ACTIVE_FILE.unlink()
    browser.navigate_to_impl("https://mockair.test/search")
    browser.fill_form_impl(json.dumps({"#to": "Paris"}))
    browser.click_element_impl(".book")
    log = ACTIVE_FILE.read_text()
    assert "[browser] navigated to https://mockair.test/search" in log
    assert "[browser] filled 1 form field(s)" in log
    assert "[browser] clicked element '.book'" in log


def test_first_domain_visit_audited(page):
    browser.navigate_to_impl("https://mockair.test/")
    entries = audit.read_recent(20)
    assert any(e["tool"] == "browser_domain_first_visit"
               and e["args"].get("domain") == "mockair.test" for e in entries)
    # second visit: no new first-visit entry
    count = sum(1 for e in audit.read_recent(100)
                if e["tool"] == "browser_domain_first_visit"
                and e["args"].get("domain") == "mockair.test")
    browser.navigate_to_impl("https://mockair.test/other")
    count_after = sum(1 for e in audit.read_recent(100)
                      if e["tool"] == "browser_domain_first_visit"
                      and e["args"].get("domain") == "mockair.test")
    assert count_after == count


def test_task_outcome_stored_as_high_confidence_fact(page):
    from remy.memory.tiered import get_memory, FACTS_FILE
    if FACTS_FILE.exists():
        FACTS_FILE.unlink()
    result = browser.record_task_outcome_impl(
        "Successfully booked flight AC123 on Air Canada for July 20, "
        "seat 12A, confirmation #XYZ123")
    assert "confidence 0.95" in result
    hits = get_memory().recall("flight booking confirmation")
    assert any("XYZ123" in h["text"] for h in hits)
    fact = get_memory()._load_facts()[0]
    assert fact["confidence"] == 0.95

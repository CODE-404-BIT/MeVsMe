"""Manual browser verification: python tests/browser_dashboard_check.py (server must run)."""
from pathlib import Path
import re
from playwright.sync_api import sync_playwright, expect

output = Path("data/previews")
output.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 1100}, timezone_id="Australia/Sydney")
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:8765")
    expect(page.locator("#metric-matches")).to_have_text(re.compile(r"\d+"))
    page.screenshot(path=str(output / "dashboard-desktop.png"), full_page=True)
    count = page.locator("#metric-matches").inner_text()
    assert int(count) > 0
    page.locator("#search").fill("zz-no-match-zz")
    assert page.get_by_text("No fixtures match your filters").is_visible()
    page.locator("#search").fill("")
    page.locator('.segmented [data-tab="2"]').click()
    page.locator("#analyze").click()
    expect(page.locator("#notice-text")).to_contain_text("Analysis complete", timeout=30000)
    expect(page.locator("#results")).not_to_contain_text("Let’s look")
    page.screenshot(path=str(output / "dashboard-combinations.png"), full_page=True)
    page.locator('.segmented [data-tab="3"]').click()
    page.wait_for_timeout(300)
    assert page.locator("#section-title").inner_text() == "3× Combinations"
    page.locator(".settings-trigger").click()
    assert page.locator("#api-key").get_attribute("type") == "password"
    page.locator("#close-settings").click()
    page.locator('.segmented [data-tab="matches"]').click()
    page.set_viewport_size({"width":390,"height":844})
    page.screenshot(path=str(output / "dashboard-mobile.png"), full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert not errors, errors
    print(f"Browser checks passed: {count} fixtures, search, analysis, both combination tabs, settings and mobile layout.")
    browser.close()

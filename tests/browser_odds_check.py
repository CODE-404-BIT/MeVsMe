from pathlib import Path
from playwright.sync_api import sync_playwright, expect
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000},timezone_id='Australia/Sydney')
    errors=[]
    page.on('pageerror',lambda e: errors.append(str(e)))
    page.goto('http://127.0.0.1:8765')
    for target in ('2','3'):
        page.locator(f'.segmented [data-tab="{target}"]').click()
        expect(page.locator('.combo-card')).to_have_count(12,timeout=30000)
        expect(page.locator('.combo-card').first).to_contain_text('NOT MODEL-VALIDATED')
        expect(page.locator('.combo-card').first).not_to_contain_text('ESTIMATED EV')
        print(target,page.locator('#result-count').inner_text())
        page.locator('#next').click()
        expect(page.locator('.combo-card').first).to_contain_text('Combination 13',timeout=30000)
    page.screenshot(path='data/previews/odds-only-combinations.png')
    assert not errors,errors
    browser.close()

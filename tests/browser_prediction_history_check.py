from playwright.sync_api import sync_playwright, expect
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8765')
    page.locator('[data-tab="history"]').click()
    expect(page.locator('#section-title')).to_have_text('Prediction History')
    expect(page.locator('#results')).to_contain_text('SELECTED DATE',timeout=15000)
    expect(page.locator('.performance-heading')).to_contain_text('Overall win rate:')
    page.locator('#history-mode').select_option('odds-only')
    page.locator('#date').fill('2000-01-01');page.locator('#date').dispatch_event('change')
    expect(page.locator('#results')).to_contain_text('No predictions saved on this date',timeout=15000)
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    assert not errors,errors
    print('History navigation, date/cohort filtering, overall rate and mobile layout passed.')
    browser.close()

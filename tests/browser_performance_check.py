"""Manual real-browser smoke check against the running local dashboard."""
from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000},timezone_id='Australia/Sydney')
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8765')
    expect(page.locator('#performance-cards')).to_contain_text('generated',timeout=15000)
    expect(page.locator('#performance-cards')).to_contain_text('Awaiting results')
    page.get_by_text('Results, accuracy & model learning',exact=True).click()
    page.locator('#update-model').click()
    expect(page.locator('#notice-text')).to_contain_text('Model evaluation complete',timeout=60000)
    expect(page.locator('#learning-status')).to_contain_text('Over 2.5')
    page.screenshot(path='data/previews/performance-desktop.png',full_page=True)
    page.locator('#performance-mode').select_option('odds-only')
    expect(page.locator('#performance-cards')).to_contain_text('ODDS-ONLY')
    page.locator('.sidebar [data-tab="2"]').click()
    expect(page.locator('#results')).not_to_contain_text('Finding price combinations',timeout=30000)
    assert 'Could not' not in page.locator('#notice-text').inner_text()
    page.locator('[data-tab="recommendations"]').click()
    expect(page.locator('.recommendation-diagnostics')).to_be_visible(timeout=30000)
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(path='data/previews/performance-mobile.png',full_page=True)
    assert not errors,errors
    print('Performance cohorts, model evaluation, odds generation, recommendation diagnostics and mobile layout passed.')
    print(page.locator('#learning-status').inner_text())
    browser.close()

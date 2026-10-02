from playwright.sync_api import sync_playwright, expect

with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000},timezone_id='Australia/Sydney')
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8765')
    expect(page.locator('#day-basis')).to_be_visible()
    page.locator('#date').fill('2026-09-18')
    page.locator('#day-basis').select_option('utc')
    page.locator('[data-tab="recommendations"]').click()
    page.locator('#team-query').fill('Gandzasar vs FC Urartu')
    page.get_by_role('button',name='Search evidence').click()
    expect(page.locator('.daily-historical-evidence')).to_contain_text('Gandzasar vs FC Urartu',timeout=30000)
    expect(page.locator('.daily-historical-evidence')).to_contain_text('100% · 10/10')
    page.locator('.daily-historical-evidence summary').click()
    expect(page.locator('.daily-historical-evidence a').first).to_have_attribute('href',__import__('re').compile('https://www.live-result.com/football/matches/'))
    page.screenshot(path='data/previews/public-historical-evidence.png',full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    assert not errors,errors
    print('UTC date selector, Gandzasar/Urartu sourced 10/10 record, source links and mobile layout passed.')
    browser.close()

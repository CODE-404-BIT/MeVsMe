import json
from playwright.sync_api import sync_playwright,expect
from betmodel.accuracy_policy import select_combinations
from test_accuracy_policy import leg

with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000},timezone_id='Australia/Sydney')
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8765')
    page.locator('#day-basis').select_option('utc')
    page.locator('.sidebar [data-tab="2"]').click()
    expect(page.locator('#results')).to_contain_text('No combination meets the evidence requirements',timeout=60000)
    expect(page.locator('#results')).to_contain_text('65% per leg')
    # Exercise the positive rendering path with test-only, policy-generated fixtures.
    items=select_combinations([leg(1),leg(2),leg(3)])['2']
    analysis=page.evaluate('({...params(),valid_candidates:3,scanned_markets:3,search_candidates:3,limited:false,reason:"test"})')
    page.route('**/api/combinations?*',lambda route:route.fulfill(json={'items':items,'total':len(items),'analysis':analysis}))
    page.evaluate('renderCombos()')
    expect(page.locator('#results')).to_contain_text('Safety evidence')
    expect(page.locator('#results')).to_contain_text('not a calibrated safety probability')
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    assert not errors,errors
    print('Live rejection reasons and test-only recommendation score/evidence rendering passed.')
    browser.close()

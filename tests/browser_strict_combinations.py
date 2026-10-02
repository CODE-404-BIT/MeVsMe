"""Render real assets against deterministic API responses; never touches owner data."""
from pathlib import Path
from playwright.sync_api import sync_playwright

STATIC=Path(__file__).resolve().parents[1]/'src/betmodel/static'
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    page=browser.new_page()
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    def route_request(route):
        from urllib.parse import urlsplit
        path=urlsplit(route.request.url).path
        if path.startswith('/api/'):
            if path=='/api/status':payload={'job':{'state':'idle'},'token':'test','analysis':None,'key_configured':False}
            elif path=='/api/matches':payload={'matches':[],'coverage':'Test'}
            elif path=='/api/performance':payload={'cohorts':{},'learning':{}}
            elif path=='/api/combinations':payload={'items':[],'total':0,'analysis':{**page.evaluate('params()'),'reason':'No fresh exact odds','historical_slips':{'2':[],'3':[]}}}
            else:payload={}
            route.fulfill(json=payload)
        else:
            asset=STATIC/('index.html' if path=='/' else path.lstrip('/'))
            mime='text/html' if asset.suffix=='.html' else 'text/css' if asset.suffix=='.css' else 'text/javascript'
            route.fulfill(body=asset.read_bytes(),content_type=mime) if asset.is_file() else route.fulfill(status=404)
    page.route('**/*',route_request)
    page.goto('http://dashboard.test/')
    page.wait_for_function("typeof patternAnalyses !== 'undefined'")
    page.evaluate("state.status={analysis:params()}; state.busy=false; setTab('2')")
    page.wait_for_function("document.getElementById('results').textContent.includes('No fresh exact odds')")
    assert page.locator('.historical-slips').count()==0
    assert page.locator('#results .combo-card').count()==0
    page.route('**/api/recommendations?*',lambda route:route.fulfill(json={
        'items':[{'sport':'basketball','home':'Test Home','away':'Test Away','competition':'NBA',
            'start':'2099-10-02T20:00:00Z','market':'winner','selection':'Test Home','probability':.72,
            'evidence_confidence':8.2,'sample_home':20,'sample_away':21,'validated':True,
            'validation':{'matches':110,'brier':.19,'baseline_brier':.24},'form_home':[1,1,0],
            'form_away':[0,1,0],'latest_home':'2099-10-01','latest_away':'2099-10-01'}],
        'research_estimates':[],'stale':False,'coverage':{'tennis':{'status':'history_source_required'}}}))
    page.evaluate("setTab('recommendations')")
    page.wait_for_selector('.pick-scorecard')
    assert '72' in page.locator('.pick-scorecard').inner_text()
    assert '8.2' in page.locator('.pick-scorecard').inner_text()
    assert 'history' in page.locator('#sport-coverage').inner_text().lower()
    pattern={'hits':5,'trials':5,'label':'Over 0.5 goals','group':'All matches','from':'2026-09-01','to':'2026-10-01'}
    leg={'fixture':'A v B','market':'Goals','selection':'Over 0.5','odds':1.45,'bookmaker':'Book',
         'updated':'2026-10-02T10:00:00Z','patterns':[pattern],
         'window_records':[pattern,dict(pattern,hits=5,trials=10)]}
    page.route('**/api/combinations?*',lambda route:route.fulfill(json={'items':[{'total_odds':2.1025,
        'safety_rating':7,'legs':[leg,dict(leg,fixture='C v D')],'score_note':'Historical only'}],
        'total':1,'analysis':page.evaluate('params()')}))
    page.evaluate("setTab('2')")
    page.wait_for_selector('#results .combo-card')
    assert '5/10' in page.locator('#results').text_content()
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+1')
    assert not errors,errors
    print('Strict empty payout screen passed at desktop/mobile widths; no JS errors')
    browser.close()

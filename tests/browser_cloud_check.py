"""Real HTTPS/browser acceptance using a private SQLite backup; no provider calls."""
from pathlib import Path
import tempfile
import threading
from werkzeug.serving import make_server, WSGIRequestHandler
from werkzeug.security import generate_password_hash
from playwright.sync_api import sync_playwright
from betmodel.cloud import create_app
from betmodel.cloud_config import CloudSettings
from betmodel.dashboard import Dashboard
from betmodel.migrate_cloud import backup_sqlite

root=Path(__file__).resolve().parents[1]
origin='https://127.0.0.1:8769'
class Quiet(WSGIRequestHandler):
    def log_request(self,*args):pass

with tempfile.TemporaryDirectory(prefix='cloud-browser-',dir=root/'data') as folder:
    test_root=Path(folder)
    backup_sqlite(root/'data/app.db',test_root/'data/app.db')
    dashboard=Dashboard(test_root)
    config=CloudSettings('unused',origin,generate_password_hash('browser-test-only'),'s'*48)
    app=create_app(test_root,config,dashboard=dashboard)
    server=make_server('127.0.0.1',8769,app,threaded=True,ssl_context='adhoc',request_handler=Quiet)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='chrome',headless=True)
            context=browser.new_context(ignore_https_errors=True,bypass_csp=True,viewport={'width':1440,'height':1000})
            page=context.new_page();errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            assert context.request.get(origin+'/api/status').status==401
            page.on('request',lambda req:print('login origin',req.headers.get('origin')) if req.method=='POST' and req.url.endswith('/login') else None)
            page.goto(origin)
            page.locator('#password').fill('wrong')
            with page.expect_navigation():page.get_by_role('button',name='Sign in').click()
            assert 'Sign in required' in page.inner_text('body'),page.inner_text('body')
            page.goto(origin+'/login');page.locator('#password').fill('browser-test-only')
            with page.expect_navigation():page.get_by_role('button',name='Sign in').click()
            page.wait_for_function('state.token.length>0')
            page.locator('#date').fill('2026-09-19');page.locator('#date').dispatch_event('change')
            page.locator('#day-basis').select_option('utc')
            page.wait_for_function('state.matches.length>0')
            for target in ('2','3'):
                page.evaluate('setTab',target)
                page.get_by_role('heading',name=f'{target}-selection historical slips').wait_for(timeout=60000)
                assert page.locator('.historical-slips .combo-card').count()>0
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.screenshot(path=str(root/'data/cloud-mobile.png'))
            page.locator('#cloud-logout').click(force=True)
            page.locator('#password').wait_for()
            assert context.request.get(origin+'/api/status').status==401
            assert not errors,errors
            print('HTTPS login, private API, 2/3 selection views, mobile and logout passed; no JS errors')
            browser.close()
    finally:
        server.shutdown();server.server_close();worker.join();dashboard.engine.dispose()

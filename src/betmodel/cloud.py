"""Private single-owner cloud dashboard. No local-server security assumptions."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlsplit
from flask import Flask, request, session, redirect, render_template, jsonify, Response
from werkzeug.security import check_password_hash
from sqlalchemy import text
from .api_routes import dispatch_api, ASSETS
from .dashboard import Dashboard
from .state_store import load_state, save_state

CSP = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"


def create_app(root, config, *, dashboard=None):
    app=Flask(__name__,static_folder=None)
    app.config.update(SECRET_KEY=config.secret_key, MAX_CONTENT_LENGTH=4096,
        SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8), SESSION_REFRESH_EACH_REQUEST=False)
    dashboard=dashboard or Dashboard(Path(root),database_url=config.database_url)
    app.extensions['dashboard']=dashboard
    host=urlsplit(config.public_origin).netloc
    static=Path(__file__).parent/'static'
    # Global single-owner limit deliberately ignores forwarding headers. This avoids
    # trusting an undocumented proxy count and bounds memory even under spoofed IPs.
    attempts=[]; attempt_lock=threading.Lock()

    def error(code):
        return jsonify(error={400:'Invalid request',401:'Sign in required',403:'Access denied',
            404:'Not found',413:'Request too large',429:'Too many attempts. Try again later.',
            500:'The operation could not complete',503:'Service unavailable'}.get(code,'Request rejected')),code

    def authenticated():
        sid=session.get('sid')
        return bool(sid and load_state(dashboard.engine,'session:'+sid))

    @app.before_request
    def protect():
        if request.host != host:return error(403)
        if request.content_length and request.content_length>4096:return error(413)
        if request.headers.get('Origin') not in {None,config.public_origin}:return error(403)
        if request.path in {'/healthz','/login','/login.css'}:return None
        if not authenticated():
            return error(401) if request.path.startswith('/api/') or request.method!='GET' else redirect('/login')
        if request.method not in {'GET','HEAD'}:
            if request.headers.get('Origin') != config.public_origin:return error(403)
            supplied=request.headers.get('X-Dashboard-Token','')
            if not supplied or not secrets.compare_digest(supplied,session.get('csrf','')):return error(403)

    @app.after_request
    def headers(response):
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
            'Content-Security-Policy':CSP,'Referrer-Policy':'same-origin',
            'Strict-Transport-Security':'max-age=31536000'})
        return response

    @app.errorhandler(Exception)
    def failure(exc):
        from werkzeug.exceptions import HTTPException
        return error(exc.code if isinstance(exc,HTTPException) else 500)

    @app.get('/healthz')
    def health():
        try:
            with dashboard.engine.connect() as connection:connection.execute(text('SELECT 1'))
        except Exception:return error(503)
        return jsonify(status='ok')

    @app.route('/login',methods=['GET','POST'])
    def login():
        if request.method=='GET':
            session.setdefault('csrf',secrets.token_urlsafe(32))
            return render_template('login.html',csrf=session['csrf'])
        if request.headers.get('Origin')!=config.public_origin:return error(403)
        csrf=request.form.get('csrf','')
        if not csrf or not secrets.compare_digest(csrf,session.get('csrf','')):return error(403)
        with attempt_lock:
            now=time.monotonic()
            attempts[:]=[stamp for stamp in attempts if now-stamp<900]
            if len(attempts)>=10:return error(429)
            # Reserve a slot before expensive password hashing, including concurrent requests.
            attempts.append(now)
        if not check_password_hash(config.password_hash,request.form.get('password','')):return error(401)
        with attempt_lock:attempts.clear()
        old=session.get('sid')
        if old:save_state(dashboard.engine,'session:'+old,{},datetime.now(timezone.utc))
        session.clear(); session.permanent=True
        session['sid']=secrets.token_urlsafe(32); session['csrf']=secrets.token_urlsafe(32)
        save_state(dashboard.engine,'session:'+session['sid'],{'owner':True},datetime.now(timezone.utc)+timedelta(hours=8))
        return redirect('/')

    @app.post('/logout')
    def logout():
        save_state(dashboard.engine,'session:'+session['sid'],{},datetime.now(timezone.utc))
        session.clear()
        return jsonify(ok=True)

    @app.get('/login.css')
    def login_css():return Response((static/'login.css').read_bytes(),content_type='text/css')

    @app.route('/',defaults={'path':''},methods=['GET','POST'])
    @app.route('/<path:path>',methods=['GET','POST'])
    def route(path):
        path='/'+path
        if path in ASSETS and request.method=='GET':
            filename,mime=ASSETS[path]
            return Response((static/filename).read_bytes(),content_type=mime)
        if not path.startswith('/api/'):return error(404)
        try:
            data=request.get_json() if request.method=='POST' else None
            status,body=dispatch_api(dashboard,request.method,path,request.args,data)
            if path=='/api/status' and status==200:body={**body,'token':session['csrf'],'cloud':True}
            return jsonify(body),status
        except (ValueError,KeyError,TypeError):return error(400)
    return app

"""Transport-independent dashboard routes. Callers enforce authentication."""
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8')}
for name in ('app','odds-only','insights','performance','prediction-history','match-analysis','accuracy-policy'):
    ASSETS['/'+name+'.js'] = (name+'.js', 'text/javascript; charset=utf-8')
for name in ('app','insights','performance'):
    ASSETS['/'+name+'.css'] = (name+'.css', 'text/css; charset=utf-8')


def dispatch_api(app, method, path, args, data=None):
    if method == 'GET':
        if path == '/api/status':return 200, app.status()
        if path == '/api/performance':return 200, app.performance()
        if path == '/api/prediction-history':
            from .performance import prediction_history
            from .dashboard import utc_window
            return 200, prediction_history(app.engine, utc_window(args['date'],int(args.get('offset',0)),
                int(args.get('end_offset',0))),args.get('mode','model'),int(args.get('page',1)))
        if path == '/api/matches':
            return 200, app.matches(args['date'],int(args.get('offset',0)),int(args.get('end_offset',0)))
        if path == '/api/insights':
            return 200, app.insights(args['date'],int(args.get('offset',0)),int(args.get('end_offset',0)),
                args.get('query','')[:160],args.get('recommendations')=='true')
        if path == '/api/combinations':
            if args.get('mode') == 'odds-only':
                from .dashboard import utc_window
                from .odds_only import price_combinations
                target=args.get('target','2'); page=int(args.get('page',1))
                if target not in {'2','3'} or page<1:raise ValueError('Invalid page')
                result=price_combinations(app.engine,utc_window(args['date'],int(args.get('offset',0)),int(args.get('end_offset',0))),target)
                return 200, {**result,'items':result['items'][(page-1)*12:page*12],'total':len(result['items']),'page':page}
            return 200, app.combinations(args.get('target','2'),int(args.get('page',1)),int(args.get('size',12)),args.get('positive')=='true')
    if method == 'POST':
        if not isinstance(data,dict):raise ValueError('Invalid request')
        if path == '/api/settings':
            app.set_key(str(data.get('key','')))
            return 200, {'key_configured':bool(app.key)}
        if path == '/api/price-combinations':
            return 200, app.price_combinations(data['date'],int(data.get('offset',0)),int(data.get('end_offset',0)),str(data.get('target','2')),int(data.get('page',1)))
        if path == '/api/jobs':
            accepted=app.start(data['kind'],data['date'],int(data.get('offset',0)),int(data.get('end_offset',0)),str(data.get('query',''))[:160])
            return (202 if accepted else 409), {'accepted':accepted,'error':None if accepted else 'An operation is already running'}
    return 404, {'error':'Not found'}

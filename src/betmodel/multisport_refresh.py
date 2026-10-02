"""Automatic, quota-bounded discovery; absent feeds are reported, never fabricated."""
from datetime import timedelta
import httpx
from .multisport_store import SPORTS,utc,upsert_events,load_events,upsert_quotes
from .state_store import load_state,save_state
from .providers.sport_http import SportHTTP
from .providers.api_sports import fetch_games
from .providers.odds_api import sport_for,parse_odds


def _dates(window):
    day=window[0].date()
    while day<(window[1]-timedelta(microseconds=1)).date()+timedelta(days=1):
        yield day.isoformat()
        day+=timedelta(days=1)


def refresh_sports(engine,window,credentials,now,progress=lambda message:None,http=None):
    if http is None:
        with httpx.Client(timeout=20) as client:
            return refresh_sports(engine,window,credentials,now,progress,client)
    report={'updated_at':now.isoformat(),'sports':{s:{'status':'not_configured','discovered':0,
        'history_status':'unavailable','messages':[]} for s in SPORTS}}
    report['sports']['football']['status']='existing_football_feed'
    for sport in ('basketball','icehockey'):
        coverage=report['sports'][sport];key=credentials.get(sport,'')
        if not key:
            coverage['status']='missing_key';continue
        client=SportHTTP(engine,http,sport,key,now)
        try:
            progress(f'Discovering {sport} events')
            found=[]
            for day in _dates(window):found.extend(fetch_games(client,sport,{'date':day}))
            upsert_events(engine,found)
            coverage['discovered']=len(found);coverage['status']='available'
            leagues=sorted({(r['competition'],str(r['season'])) for r in found if r.get('season')})
            cursor_key='sports-history-cursor:'+sport
            cursor=(load_state(engine,cursor_key) or {}).get('cursor',0)
            if leagues:
                # At most two league histories per refresh; each full response covers a season.
                for n in range(min(2,len(leagues))):
                    league,season=leagues[(cursor+n)%len(leagues)]
                    history=fetch_games(client,sport,{'league':league,'season':season},ttl=timedelta(hours=6))
                    fresh_ids={r['provider_id'] for r in found}
                    upsert_events(engine,[r for r in history if r['status']=='FINISHED' and r['provider_id'] not in fresh_ids])
                save_state(engine,cursor_key,{'cursor':(cursor+min(2,len(leagues)))%len(leagues)})
            coverage['history_status']='available' if any(r['status']=='FINISHED' for r in load_events(engine,sport)) else 'no_results'
        except (ValueError,TypeError,KeyError):
            coverage['status']='partial_or_unavailable'
            coverage['messages'].append('Check sport entitlement, season coverage and request quota. Saved records are retained.')
    odds_key=credentials.get('odds','')
    if odds_key:
        client=SportHTTP(engine,http,'odds',odds_key,now)
        try:
            catalog=client.get('/sports',{},cost=0,ttl=timedelta(hours=6))
            if not isinstance(catalog,list):raise ValueError('Invalid catalogue')
            cursor=(load_state(engine,'sport-odds-cursor') or {}).get('cursor',0)
            selected=[]
            for sport in SPORTS:
                league_keys=sorted(r['key'] for r in catalog if sport_for(r.get('key',''))==sport
                                   and r.get('active') and not r.get('has_outrights') and 'doubles' not in r['key'])
                if league_keys:selected.append((sport,league_keys[cursor%len(league_keys)]))
            existing=load_events(engine)
            for sport,league in selected:
                try:
                    progress(f'Refreshing {sport} winner prices')
                    payload=client.get('/sports/'+league+'/odds',{'regions':'au','markets':'h2h','oddsFormat':'decimal',
                        'commenceTimeFrom':window[0].strftime('%Y-%m-%dT%H:%M:%SZ'),
                        'commenceTimeTo':window[1].strftime('%Y-%m-%dT%H:%M:%SZ')})
                    found,prices=parse_odds(payload,sport)
                    unmatched=[]
                    for event in found:
                        matches=[r for r in existing if r['sport']==sport and r['provider']!='odds-api'
                            and r['home'].casefold()==event['home'].casefold() and r['away'].casefold()==event['away'].casefold()
                            and abs((utc(r['start'])-utc(event['start'])).total_seconds())<=300 and r['scope']==event['scope']]
                        if len(matches)==1:
                            for price in prices:
                                if price['event_key']==event['event_key']:price['event_key']=matches[0]['event_key']
                        elif not matches:unmatched.append(event)
                        else:prices=[p for p in prices if p['event_key']!=event['event_key']]
                    upsert_events(engine,unmatched);upsert_quotes(engine,prices)
                    report['sports'][sport]['odds_status']='available'
                    report['sports'][sport]['odds_competition']=league
                except (ValueError,TypeError,KeyError):
                    report['sports'][sport]['odds_status']='unavailable'
            save_state(engine,'sport-odds-cursor',{'cursor':cursor+1})
        except (ValueError,TypeError,KeyError):
            for coverage in report['sports'].values():coverage['odds_status']='check_key_or_quota'
    else:
        for coverage in report['sports'].values():coverage['odds_status']='missing_key'
    report['sports']['tennis']['status']='history_source_required'
    report['sports']['tennis']['messages']=['Tennis odds discovery is supported; a permitted current singles-history source is still required for statistical picks.']
    report['partial']=True
    save_state(engine,'multisport-coverage',report)
    return report

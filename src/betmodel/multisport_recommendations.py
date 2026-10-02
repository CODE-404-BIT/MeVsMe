"""Evidence and ranking keep observed records distinct from future probabilities."""
from math import isfinite
from datetime import date,timedelta,timezone
from .multisport_store import utc, event_key


def rank_picks(rows, now, limit=10):
    eligible=[]
    for row in rows:
        p=row.get('probability')
        if not row.get('validated') or not isinstance(p,(int,float)) or not isfinite(p) or not 0<p<1:continue
        if row.get('status')!='SCHEDULED' or utc(row['start'])<=now:continue
        samples=min(row.get('sample_home',0),row.get('sample_away',0))
        if samples<10:continue
        if not row.get('latest_home') or not row.get('latest_away'):continue
        from datetime import date
        latest=min(date.fromisoformat(row['latest_home'][:10]),date.fromisoformat(row['latest_away'][:10]))
        age=(now.date()-latest).days
        if not 0<=age<=180:continue
        eligible.append(dict(row,evidence_confidence=round(min(9.9,7*min(samples/20,1)+3*max(0,1-age/180)),1),
                             history_age_days=age,sample_floor=samples))
    eligible.sort(key=lambda r:(-r['probability'],-r['sample_floor'],r['history_age_days'],r['event_key']))
    unique={}
    for row in eligible:unique.setdefault(row['event_key'],row)
    return list(unique.values())[:max(0,min(limit,10))]


def winner_evidence(event, results, now):
    """Fixed winner windows, using exactly the event's settlement scope."""
    cutoff=min(now,utc(event['start']))
    output=[]
    for side in ('home','away'):
        participant=event[side+'_id']
        relevant=[]
        for row in results:
            if (row.get('status')!='FINISHED' or row.get('sport')!=event['sport'] or
                row.get('competition')!=event['competition'] or row.get('scope')!=event['scope'] or
                row.get('provider')!=event['provider'] or utc(row['start']).date()>=cutoff.date()):continue
            if row.get('retirement') or row.get('walkover'):continue
            if event['sport']=='tennis' and row.get('surface')!=event.get('surface'):continue
            # Team sports use the upcoming venue; tennis has no home advantage.
            row_side=side if event['sport']!='tennis' else ('home' if row['home_id']==participant else 'away')
            if row.get(row_side+'_id')!=participant:continue
            a,b=row.get('home_score'),row.get('away_score')
            if not isinstance(a,(float,int)) or not isinstance(b,(float,int)):continue
            won=(a>b) if row_side=='home' else (b>a)
            relevant.append((utc(row['start']),won))
        relevant.sort()
        for window in (5,10,20):
            sample=relevant[-window:]
            if len(sample)<window:continue
            hits=sum(won for _,won in sample)
            output.append(dict(selection=event[side],participant_id=participant,market='winner',scope=event['scope'],
                hits=hits,trials=window,window=window,rate=hits/window,
                **{'from':sample[0][0].date().isoformat(),'to':sample[-1][0].date().isoformat()},
                perfect=hits==window))
    return output


def build_sport_combinations(rows,now):
    from collections import defaultdict
    from itertools import combinations
    from math import prod
    from datetime import date,timedelta
    groups=defaultdict(list);output={'2':[],'3':[]}
    for row in rows:
        perfect=[p for p in row.get('patterns',[]) if p.get('hits')==p.get('trials') and p.get('trials') in {5,10,20}
                 and date.fromisoformat(p['to'])<now.date()]
        if not perfect or utc(row['kickoff'])<=now or not row.get('bookmaker'):continue
        if not isfinite(row['odds']) or row['odds']<=1 or not timedelta(0)<=now-utc(row['updated'])<=timedelta(hours=24):continue
        groups[row['bookmaker']].append(dict(row,patterns=perfect))
    for book,legs in groups.items():
        # Round-robin by sport so a busy league cannot consume the whole bounded search.
        from itertools import zip_longest
        by_sport=defaultdict(list)
        for leg in sorted(legs,key=lambda l:(-max(p['trials'] for p in l['patterns']),l['event_key'])):
            by_sport[leg.get('sport','unknown')].append(leg)
        legs=[leg for group in zip_longest(*(by_sport[s] for s in sorted(by_sport))) for leg in group if leg is not None][:32]
        for count in range(2,min(4,len(legs))+1):
            for combo in combinations(legs,count):
                if len({l['event_key'] for l in combo})!=count:continue
                price=prod(l['odds'] for l in combo)
                target='2' if 1.8<=price<=2.3 else '3' if 2.6<=price<=3.5 else None
                if not target:continue
                samples=min(max(p['trials'] for p in l['patterns']) for l in combo)
                age=max(min((now.date()-date.fromisoformat(p['to'])).days for p in l['patterns']) for l in combo)
                output[target].append(dict(legs=list(combo),total_odds=price,bookmaker=book,
                    safety_rating=min(9.9,7*min(samples/20,1)+3*max(0,1-age/180)),joint_probability=None,ev=None,
                    score_note='Evidence confidence reflects historical sample and recency, not future win probability.'))
    for target in output:
        output[target]=sorted(output[target],key=lambda c:(-c['safety_rating'],abs(c['total_odds']-int(target))))[:20]
    return output


def sport_candidates(engine,window,now):
    from .multisport_store import load_events,load_quotes
    from .multisport_models import evaluate_winner_model,forecast_events
    from .state_store import load_state,save_state
    import hashlib,json
    events=load_events(engine);quotes=load_quotes(engine);forecasts=[];priced=[]
    upcoming=[r for r in events if r['status']=='SCHEDULED' and window[0]<=utc(r['start'])<window[1] and utc(r['start'])>now]
    groups={(r['sport'],r['provider'],r['competition'],r['scope']) for r in upcoming}
    for sport,provider,competition,scope in sorted(groups):
        selected=[r for r in upcoming if (r['sport'],r['provider'],r['competition'],r['scope'])==(sport,provider,competition,scope)]
        history=[r for r in events if (r['sport'],r['provider'],r['competition'],r['scope'])==(sport,provider,competition,scope)
                 and r['status']=='FINISHED' and utc(r['start']).date()<now.date()]
        if history:
            identity=hashlib.sha256(json.dumps([sport,provider,competition,scope,now.date().isoformat(),history],sort_keys=True).encode()).hexdigest()
            report=load_state(engine,'sport-model:'+identity)
            if report is None:
                report=evaluate_winner_model(history,sport,now)
                save_state(engine,'sport-model:'+identity,report)
            forecasts.extend(forecast_events(selected,history,report,now))
        for event in selected:
            evidence=winner_evidence(event,history,now)
            for quote in quotes:
                if quote['event_key']!=event['event_key'] or quote['scope']!=scope or quote['market']!='winner':continue
                perfect=[p for p in evidence if p['perfect'] and p['selection']==quote['selection']]
                if not perfect:continue
                priced.append(dict(quote,fixture=event['home']+' v '+event['away'],kickoff=event['start'],
                    window_records=[dict(p,label=p['selection']+' to win',group=event.get('competition_name',competition))
                        for p in evidence if p['selection']==quote['selection']],
                    patterns=[dict(p,label=p['selection']+' to win',group=event.get('competition_name',competition),
                        stale=(now.date()-date.fromisoformat(p['to'])).days>30) for p in perfect]))
    return forecasts,priced


def football_candidates(engine,window,now):
    from .team_insights import evidence_for,load_history,competition_history,validate_competition,predict_match
    evidence=evidence_for(engine,window,all_competitions=True)
    history=load_history(engine,min(window[0],now))
    forecasts=[]
    for match in evidence['matches']:
        forecast=match['forecast']
        if not forecast.get('available') or match['status']!='SCHEDULED' or not match.get('kickoff') or utc(match['kickoff'])<=now:continue
        pool=competition_history(history,match['competition'],match['home'],match['away'])
        if pool.empty:continue
        # Validate and forecast with the same baseline, rather than a separately promoted model.
        forecast=predict_match(pool,match['home'],match['away'])
        if not forecast.get('available'):continue
        report=validate_competition(pool[['date','home_team','away_team','home_goals','away_goals']].to_json(orient='records',date_format='iso'),window=200)
        p=forecast['probabilities']['TOTAL_GOALS_OVER:2.5']
        forecasts.append(dict(sport='football',event_key='football:'+str(match['fixture_id']),
            home=match['home'],away=match['away'],competition=match['competition'],start=match['kickoff'],status='SCHEDULED',
            market='Total goals 2.5',selection='Over 2.5' if p>=.5 else 'Under 2.5',probability=max(p,1-p),
            validated=bool(report['matches']>=100 and report['calibrated'] and report['brier']<report['baseline_brier']),
            validation=report,model_version='football-poisson-top10-v1',cutoff=evidence['cutoff'],
            sample_home=forecast['home_samples'],sample_away=forecast['away_samples'],
            latest_home=forecast['latest_home'],latest_away=forecast['latest_away'],
            form_home=[r['result'] for r in match['individual'][0]['recent'][:10]],
            form_away=[r['result'] for r in match['individual'][1]['recent'][:10]]))
    return forecasts


def prepare_recommendations(engine,window,now):
    from .state_store import save_state
    from .multisport_store import freeze_predictions
    forecasts,priced=sport_candidates(engine,window,now)
    forecasts.extend(football_candidates(engine,window,now))
    ranked=attach_prices(engine,rank_picks(forecasts,now),now)
    # Sport filters and later kickoffs can expose candidates below the initial top ten.
    eligible=[candidate for row in forecasts for candidate in rank_picks([row],now)]
    freeze_predictions(engine,attach_prices(engine,eligible,now),now)
    save_state(engine,'multisport-ranked:'+window[0].isoformat(),{'rows':forecasts,
        'research_estimates':[r for r in forecasts if not r['validated']],
        'updated_at':now.isoformat(),'window_end':window[1].isoformat()})
    save_state(engine,'multisport-priced:'+window[0].isoformat(),{'rows':priced})
    from .multisport_settlement import freeze_sport_combinations,settle_sports
    freeze_sport_combinations(engine,build_sport_combinations(priced,now),now)
    settle_sports(engine,now)
    return len(ranked)


def attach_prices(engine,rows,now):
    from .multisport_store import load_quotes
    from .models import OddsSnapshot
    from .db import session_factory
    from sqlalchemy import select
    quotes=load_quotes(engine);output=[]
    football_ids=[int(r['event_key'].split(':')[1]) for r in rows if r['event_key'].startswith('football:')]
    if football_ids:
        with session_factory(engine)() as session:
            latest=set()
            for odd in session.scalars(select(OddsSnapshot).where(OddsSnapshot.fixture_id.in_(football_ids))
                    .order_by(OddsSnapshot.received_timestamp.desc(),OddsSnapshot.id.desc())):
                identity=(odd.fixture_id,odd.bookmaker,odd.market_key,odd.line,odd.selection)
                if identity in latest:continue
                latest.add(identity)
                if odd.market_key not in {'TOTAL_GOALS_OVER','TOTAL_GOALS_UNDER'} or odd.line!=2.5:continue
                stamp=odd.source_timestamp or odd.received_timestamp
                if not stamp:continue
                quotes.append(dict(event_key='football:'+str(odd.fixture_id),market='Total goals 2.5',scope='regulation',
                    selection=odd.selection,odds=odd.decimal_odds,bookmaker=odd.bookmaker,
                    updated=stamp.replace(tzinfo=timezone.utc).isoformat()))
    for row in rows:
        clean={k:v for k,v in row.items() if k not in {'odds','bookmaker','odds_updated','implied_probability'}}
        candidates=[q for q in quotes if q['event_key']==row['event_key'] and q['market']==row['market']
                    and q['selection']==row['selection'] and q['scope']==row.get('scope','regulation')
                    and q.get('bookmaker') and isfinite(q['odds']) and q['odds']>1
                    and timedelta(0)<=now-utc(q['updated'])<=timedelta(hours=24)]
        if candidates:
            best=max(candidates,key=lambda q:(q['odds'],q['updated']))
            clean.update(odds=best['odds'],bookmaker=best['bookmaker'],odds_updated=best['updated'])
            if 'implied_probability' in best:clean['implied_probability']=best['implied_probability']
        output.append(clean)
    return output


def current_sport_combinations(engine,window,now):
    from .state_store import load_state
    from .multisport_store import load_events,load_quotes
    cached=load_state(engine,'multisport-priced:'+window[0].isoformat()) or {'rows':[]}
    events={r['event_key']:r for r in load_events(engine,window=window)}
    quotes={(r['event_key'],r['bookmaker'],r['market'],r['selection'],r['scope']):r for r in load_quotes(engine)}
    rows=[]
    for row in cached['rows']:
        event=events.get(row['event_key'])
        if not event or event['status']!='SCHEDULED' or utc(event['start'])<=now:continue
        quote=quotes.get((row['event_key'],row['bookmaker'],row['market'],row['selection'],row['scope']))
        if not quote or quote['odds']!=row['odds'] or quote['updated']!=row['updated']:continue
        rows.append(row)
    return build_sport_combinations(rows,now)


def recommendation_payload(engine,window,now,sport='all'):
    from datetime import timedelta
    from .multisport_store import SPORTS,load_events,load_quotes,freeze_predictions
    from .state_store import load_state
    if sport not in ('all',*SPORTS):raise ValueError('Unsupported sport')
    report=load_state(engine,'multisport-coverage') or {}
    coverage=report.get('sports',{s:{'status':'not_refreshed','discovered':0} for s in SPORTS})
    # GET is read-only: model fitting and snapshot writes happen in the refresh job.
    saved=load_state(engine,'multisport-ranked:'+window[0].isoformat()) or {'rows':[],'research_estimates':[]}
    current={r['event_key']:r for r in load_events(engine,window=window)}
    from .models import Fixture
    from sqlalchemy import select
    with engine.connect() as connection:
        for row in connection.execute(select(Fixture.id,Fixture.status,Fixture.kickoff).where(
            Fixture.kickoff>=window[0].replace(tzinfo=None),Fixture.kickoff<window[1].replace(tzinfo=None))):
            current['football:'+str(row.id)]={'status':row.status,'start':row.kickoff.replace(tzinfo=timezone.utc).isoformat()}
    def active(row):
        event=current.get(row['event_key'])
        return bool(event and event['status']=='SCHEDULED' and utc(event['start'])==utc(row['start']) and utc(event['start'])>now)
    rows=[r for r in saved['rows'] if (sport=='all' or r['sport']==sport) and active(r)]
    from .multisport_settlement import sport_performance
    return dict(items=attach_prices(engine,rank_picks(rows,now),now),performance=sport_performance(engine),research_estimates=[r for r in saved.get('research_estimates',[])
        if (sport=='all' or r['sport']==sport) and active(r)],coverage=coverage,
        updated_at=saved.get('updated_at'),stale=not saved.get('updated_at') or
        now-utc(saved['updated_at'])>timedelta(minutes=30))

"""Historical evidence, competition-scoped forecasts and priced single selections."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import json
import math
import pandas as pd
from scipy.stats import poisson
from sqlalchemy import select
from .db import session_factory
from .models import Fixture, TeamMatchStat, OddsSnapshot, ProviderMapping
from .models_goals import fit_poisson_goal_model
from .normalize import normalize_name
from .patterns import beta_posterior_mean, beta_interval

# Explicit spelling aliases only. No token removal that merges women/youth/reserve squads.
ALIASES={'manchester united':'man united','manchester city':'man city','tottenham hotspur':'tottenham',
    'newcastle united':'newcastle','west ham united':'west ham','wolverhampton wanderers':'wolves',
    'nottingham forest':'nott m forest','leicester city':'leicester','leeds united':'leeds',
    'brighton and hove albion':'brighton','bayern munchen':'bayern munich','borussia dortmund':'dortmund',
    'paris saint germain':'paris sg','atletico madrid':'ath madrid','atletico de madrid':'ath madrid',
    'urartu':'fc urartu','kaisar kyzylorda':'kaisar','tobol kostanay':'fk tobol kostanay'}
COMPETITIONS={'Championship':'E1','Premier League':'E0','English Premier League':'E0','La Liga':'SP1','Primera Division':'SP1',
    'Bundesliga':'D1','Serie A':'I1','Ligue 1':'F1','UEFA Champions League':'CL','Champions League':'CL',
    'Europa League':'EL','Primeira Liga':'PO1','Eredivisie':'NL1','Belgian Pro League':'BE1',
    'Scottish Premiership':'SC0','Turkish Super League':'TR1','Greek Super League':'GR1',
    'Austrian Bundesliga':'AT1','Swiss Super League':'CH1','Danish Superliga':'DK1',
    'Norwegian Eliteserien':'N1','Swedish Allsvenskan':'SW1','Ekstraklasa':'POL1',
    'Czech First League':'CZ1','Croatian Football League':'HR1','Serbian SuperLiga':'SRB1',
    'Ukrainian Premier League':'UKR1','Romanian Liga I':'RO1','Russian Premier League':'RUS1'}
LEAGUE_CODES={'40':'E1','39':'E0','140':'SP1','78':'D1','135':'I1','61':'F1','2':'CL','3':'CL','8':'EL',
    '94':'PO1','88':'NL1','144':'BE1','179':'SC0','203':'TR1','197':'GR1','218':'AT1',
    '207':'CH1','119':'DK1','103':'N1','113':'SW1','106':'POL1','345':'CZ1','210':'HR1',
    '286':'SRB1','333':'UKR1','283':'RO1','235':'RUS1'}


def team_key(name):
    value=normalize_name(name)
    return ALIASES.get(value,value)


def competition_history(history,competition,home,away,league_id=None):
    """A shared league name alone cannot identify a country or competition."""
    if history.empty:return history
    hk,ak=team_key(home),team_key(away)
    if league_id:
        exact=LEAGUE_CODES.get(league_id,'api:'+league_id)
        pool=history[history.competition==exact]
        if not pool.empty:return pool
    if competition:
        history=history[(history.competition==COMPETITIONS.get(competition,competition)) |
            (history.competition_name==competition) | history.competition.str.endswith(' / '+competition)]
    common=set(history.loc[(history.home_team==hk)|(history.away_team==hk),'competition']) & set(
        history.loc[(history.home_team==ak)|(history.away_team==ak),'competition'])
    expected=COMPETITIONS.get(competition,competition)
    if expected in common:return history[history.competition==expected]
    if len(common)==1:return history[history.competition.isin(common)]
    return history.iloc[:0]


def load_history(engine, cutoff):
    with session_factory(engine)() as s:
        fixtures=s.scalars(select(Fixture).where(Fixture.status=='FINISHED',Fixture.match_date<cutoff.date(),
            Fixture.match_date>=(cutoff-timedelta(days=730)).date())).all()
        stats=s.scalars(select(TeamMatchStat).join(Fixture).where(Fixture.status=='FINISHED',Fixture.match_date<cutoff.date(),
            Fixture.match_date>=(cutoff-timedelta(days=730)).date())).all()
        mapping={r.provider_key:r.canonical_key for r in s.scalars(select(ProviderMapping).where(ProviderMapping.entity_type=='fixture_league'))}
        by_fixture={}
        for stat in stats:by_fixture.setdefault(stat.fixture_id,{})[stat.is_home]=stat
        rows=[]
        for f in fixtures:
            pair=by_fixture.get(f.id,{})
            if 1 not in pair or 0 not in pair or pair[1].goals is None or pair[0].goals is None:continue
            league=mapping.get(f.provider_id) if f.source=='api-football' else None
            competition=LEAGUE_CODES.get(league, 'api:'+league) if league else f.competition
            row={'date':pd.Timestamp(f.match_date),'home_team':team_key(f.home_team),'away_team':team_key(f.away_team),
                 'home_display':f.home_team,'away_display':f.away_team,'competition':competition,'competition_name':f.competition,
                 'source':f.provider_id if f.source=='https://www.live-result.com' else f.source}
            for side,stat in [('home',pair[1]),('away',pair[0])]:
                for key,attr in [('goals','goals'),('corners','corners'),('shots','shots'),('sot','shots_on_target'),('cards','cards')]:
                    row[f'{side}_{key}']=getattr(stat,attr)
            rows.append(row)
    if not rows:return pd.DataFrame()
    frame=pd.DataFrame(rows).sort_values('date')
    # Mirrored/provider copies must not inflate evidence counts.
    frame['richness']=frame[[c for c in frame if c.startswith(('home_','away_'))]].notna().sum(axis=1)
    return frame.sort_values('richness',ascending=False).drop_duplicates(['date','competition','home_team','away_team']).sort_values('date')


def team_summary(frame, team):
    key=team_key(team)
    if frame.empty:return {'team':team,'matches':0,'recent':[]}
    own=frame[(frame.home_team==key)|(frame.away_team==key)].tail(20)
    recent=[]
    for _,r in own.iterrows():
        home=r.home_team==key;scored=float(r.home_goals if home else r.away_goals);conceded=float(r.away_goals if home else r.home_goals)
        recent.append({'date':r.date.date().isoformat(),'opponent':r.away_display if home else r.home_display,
            'venue':'home' if home else 'away','scored':scored,'conceded':conceded,
            'result':'W' if scored>conceded else 'D' if scored==conceded else 'L','source':r.source})
    return {'team':team,'matches':len(recent),'recent':recent[::-1],
        'goals_for':sum(r['scored'] for r in recent)/len(recent) if recent else None,
        'goals_against':sum(r['conceded'] for r in recent)/len(recent) if recent else None,
        'wins':sum(r['result']=='W' for r in recent)}


def historical_patterns(frame, home, away, include_all=False):
    if frame.empty:return []
    frame=frame.copy().sort_values('date')
    frame['home_team']=frame.home_team.map(team_key);frame['away_team']=frame.away_team.map(team_key)
    hk,ak=team_key(home),team_key(away)
    results=[]
    def add(series, rows, label, group):
        valid=series.dropna()
        for window in (5,10,20):
            sample=valid.tail(window)
            if len(sample)<window:continue
            hits=int(sample.sum());trials=len(sample)
            if hits/trials<.8 and not include_all:continue
            low,high=beta_interval(hits,trials)
            results.append({'group':group,'label':label,'window':window,'hits':hits,'trials':trials,
                'rate':hits/trials,'posterior_mean':beta_posterior_mean(hits,trials),'lower':low,'upper':high,
                'from':rows.loc[sample.index,'date'].min().date().isoformat(),
                'to':rows.loc[sample.index,'date'].max().date().isoformat()})
    for team,key in [(home,hk),(away,ak)]:
        own=frame[(frame.home_team==key)|(frame.away_team==key)]
        for venue,rows in [('all venues',own),('home',own[own.home_team==key]),('away',own[own.away_team==key])]:
            for stat,thresholds in [('goals',(1,2)),('corners',(3,5)),('shots',(8,10)),('sot',(2,3)),('cards',(1,2))]:
                hc,ac=f'home_{stat}',f'away_{stat}'
                if hc not in rows or ac not in rows:continue
                values=rows[hc].where(rows.home_team==key,rows[ac])
                values=pd.to_numeric(values,errors='coerce')
                for threshold in thresholds:
                    add((values>=threshold).where(values.notna()),rows,f'{team}: {threshold}+ {stat} ({venue})',team)
    combined=frame[frame.home_team.isin([hk,ak])|frame.away_team.isin([hk,ak])]
    h2h=frame[((frame.home_team==hk)&(frame.away_team==ak))|((frame.home_team==ak)&(frame.away_team==hk))]
    for group,rows in [('Combined unique matches',combined),('Head to head',h2h)]:
        goals=rows.home_goals+rows.away_goals
        for line in (.5,1.5,2.5,3.5):
            add((goals>line).where(goals.notna()),rows,f'Over {line} goals',group)
            add((goals<line).where(goals.notna()),rows,f'Under {line} goals',group)
        add(((rows.home_goals>0)&(rows.away_goals>0)).where(goals.notna()),rows,'Both teams scored',group)
    return sorted(results,key=lambda r:(r['rate'],r['lower'],r['trials']),reverse=True)


def predict_match(frame, home, away):
    home,away=team_key(home),team_key(away)
    if frame.empty:return {'available':False,'reason':'No historical results found.'}
    pool=frame.copy()
    pool['home_team']=pool.home_team.map(team_key);pool['away_team']=pool.away_team.map(team_key)
    home_rows=pool[(pool.home_team==home)|(pool.away_team==home)]
    away_rows=pool[(pool.home_team==away)|(pool.away_team==away)]
    if len(pool)<60 or len(home_rows)<10 or len(away_rows)<10:
        return {'available':False,'reason':f'Need 60 competition results and 10 per team; available {len(pool)}, {len(home_rows)}, {len(away_rows)}.'}
    if sum(pool.home_team==home)<5 or sum(pool.away_team==away)<5:
        return {'available':False,'reason':'Need at least five home/away venue observations for the respective teams.'}
    model=fit_poisson_goal_model(pool,cutoff=pool.date.max()+pd.Timedelta(days=1))
    probs=model.market_probabilities(home,away)
    lh,la=model.expected_goals(home,away)
    scorelines=[]
    for home_goals in range(7):
        for away_goals in range(7):
            scorelines.append({'score':f'{home_goals}-{away_goals}',
                'probability':float(poisson.pmf(home_goals,lh)*poisson.pmf(away_goals,la))})
    scorelines=sorted(scorelines,key=lambda row:row['probability'],reverse=True)[:5]
    for line in (.5,1.5,2.5,3.5,4.5):
        under=float(poisson.cdf(math.floor(line),lh+la))
        probs[f'TOTAL_GOALS_UNDER:{line}']=under
        probs[f'TOTAL_GOALS_OVER:{line}']=1-under
    return {'available':True,'probabilities':probs,'home_expected_goals':lh,'away_expected_goals':la,
        'correct_scores':scorelines,
        'home_samples':len(home_rows),'away_samples':len(away_rows),'competition_samples':len(pool),
        'latest_home':home_rows.date.max().date().isoformat(),'latest_away':away_rows.date.max().date().isoformat(),
        'method':'Competition-specific independent Poisson baseline; not a guaranteed or fully calibrated probability.'}


@lru_cache(maxsize=24)
def validate_competition(serialized, window=40):
    """Chronological out-of-sample checks; no evaluation match enters its model."""
    frame=pd.read_json(__import__('io').StringIO(serialized),orient='records')
    frame['date']=pd.to_datetime(frame.date)
    frame=frame.sort_values('date')
    errors=[];baseline_errors=[];calibration=[]
    for _,row in frame.tail(window).iterrows():
        training=frame[frame.date<row.date]
        if len(training)<60:continue
        pred=predict_match(training,row.home_team,row.away_team)
        if not pred['available']:continue
        p=pred['probabilities']['TOTAL_GOALS_OVER_2_5']
        actual=float(row.home_goals+row.away_goals>2.5)
        baseline=float((training.home_goals+training.away_goals>2.5).mean())
        errors.append((p-actual)**2);baseline_errors.append((baseline-actual)**2)
        calibration.append({'probability':p,'outcome':actual})
    n=len(errors)
    bins=[]
    for i in range(5):
        selected=[r for r in calibration if i/5<=r['probability']<(i+1)/5]
        if len(selected)>=20:
            bins.append({'count':len(selected),'gap':abs(sum(r['probability']-r['outcome'] for r in selected)/len(selected))})
    calibrated=bool(n and sum(b['count'] for b in bins)/n>=.8 and all(b['gap']<=.1 for b in bins))
    return {'matches':n,'market':'Over 2.5 goals','brier':sum(errors)/n if n else None,
        'calibration':bins,'calibrated':calibrated,
        'baseline_brier':sum(baseline_errors)/n if n else None,
        'passes':n>=20 and sum(errors)<=sum(baseline_errors),
        'note':'Chronological check for Over 2.5 only; other market probabilities remain unvalidated baselines.'}


def _forecast_model_cutoff(window, kickoff, now=None):
    now=now or datetime.now(timezone.utc)
    limit=kickoff if kickoff is not None else window[1]
    limit=limit.replace(tzinfo=timezone.utc) if limit.tzinfo is None else limit.astimezone(timezone.utc)
    return min(now,limit)


def evidence_for(engine, window, query='', forecasts=True, all_competitions=False):
    from .league_scope import in_scope,fixture_metadata
    history=load_history(engine,window[0])
    with session_factory(engine)() as s:
        metadata=fixture_metadata(s)
        matches=s.scalars(select(Fixture).where(Fixture.kickoff>=window[0].replace(tzinfo=None),
            Fixture.kickoff<window[1].replace(tzinfo=None)).order_by(Fixture.kickoff)).all()
        mappings={r.provider_key:r.canonical_key for r in s.scalars(select(ProviderMapping).where(ProviderMapping.entity_type=='fixture_league'))}
    if query.strip():
        import re
        parts=re.split(r'\s+(?:vs?\.?|versus)\s+',query.strip(),flags=re.I)
        if len(parts)!=2 or not all(parts):raise ValueError('Enter two teams as Team X vs Team Y.')
        home,away=parts
        matching=[f for f in matches if team_key(f.home_team)==team_key(home) and team_key(f.away_team)==team_key(away)]
        if matching:matches=matching
        else:matches=[Fixture(id=0,home_team=home,away_team=away,competition='',match_date=window[0].date(),status='SEARCH')]
    elif not all_competitions:
        matches=[f for f in matches if in_scope(f.competition,metadata.get(f.provider_id,{}).get('country'))]
    output=[]
    for f in matches:
        home,away=f.home_team,f.away_team;hk,ak=team_key(home),team_key(away)
        pool=history
        competition=f.competition
        if not history.empty:
            lid=mappings.get(f.provider_id)
            scope=LEAGUE_CODES.get(lid,'api:'+lid) if lid else COMPETITIONS.get(competition,competition)
            if scope:
                pool=history[history.competition==scope]
                if pool.empty and not lid:
                    named=history[history.competition_name==f.competition]
                    common=set(named.loc[(named.home_team==hk)|(named.away_team==hk),'competition']) & set(named.loc[(named.home_team==ak)|(named.away_team==ak),'competition'])
                    if len(common)==1:pool=named[named.competition.isin(common)]
            else:
                home_comps=set(history.loc[(history.home_team==hk)|(history.away_team==hk),'competition'])
                away_comps=set(history.loc[(history.home_team==ak)|(history.away_team==ak),'competition'])
                common=home_comps&away_comps
                pool=history[history.competition.isin(common)] if len(common)==1 else history.iloc[0:0]
                competition=next(iter(common)) if len(common)==1 else 'Unresolved competition'
        pool=competition_history(history,f.competition,home,away,mappings.get(f.provider_id))
        forecast=predict_match(pool,home,away) if forecasts else {'available':False,'reason':'Historical suggestions do not use a model forecast.'}
        if forecast['available']:
            recent=min(pd.Timestamp(forecast['latest_home']),pd.Timestamp(forecast['latest_away']))
            if (pd.Timestamp(window[0].date())-recent).days>180:
                forecast={'available':False,'reason':'Team history is older than 180 days; update it before forecasting.'}
            else:
                forecast['validation']=validate_competition(pool[['date','home_team','away_team','home_goals','away_goals']].to_json(orient='records',date_format='iso'))
        from .learning import apply_learned_forecast
        if forecasts:forecast=apply_learned_forecast(engine,pool,home,away,forecast,_forecast_model_cutoff(window,f.kickoff))
        own_home=team_summary(pool,home);own_away=team_summary(pool,away)
        h2h=[] if pool.empty else pool[((pool.home_team==hk)&(pool.away_team==ak))|((pool.home_team==ak)&(pool.away_team==hk))].tail(10)
        windows=historical_patterns(pool,home,away,include_all=True)
        output.append({'fixture_id':f.id,'home':home,'away':away,'competition':competition,'kickoff':f.kickoff.isoformat()+'Z' if f.kickoff else None,
            'status':f.status,'individual':[own_home,own_away], 'patterns':[p for p in windows if p['rate']>=.8], 'all_patterns':windows,
            'h2h_matches':len(h2h),'forecast':forecast})
    names=sorted(set(history.home_display)|set(history.away_display)) if not history.empty else []
    return {'matches':output,'historical_matches':len(history),'known_teams':names,
        'limitations':['100% describes observed records, not certainty about the next game.',
            'Injuries, lineups, weather, referee and news adjustments are not modeled. No values are invented.',
            'Sources may not cover every competition, women’s team or youth team.'],
        'cutoff':window[0].isoformat()}


def ranked_selections(engine, evidence, now=None, collapse_books=True):
    now=now or datetime.now(timezone.utc)
    output=[]
    with session_factory(engine)() as s:
        for match in evidence['matches']:
            pred=match['forecast']
            if not pred['available'] or match['status']!='SCHEDULED' or not match['kickoff']:continue
            if datetime.fromisoformat(match['kickoff'].replace('Z','+00:00'))<=now:continue
            odds=s.scalars(select(OddsSnapshot).where(OddsSnapshot.fixture_id==match['fixture_id']).order_by(OddsSnapshot.received_timestamp.desc(),OddsSnapshot.id.desc())).all()
            seen=set()
            for odd in odds:
                ident=(odd.bookmaker,odd.market_key,odd.selection,odd.line)
                if ident in seen:continue
                seen.add(ident)
                stamp=(odd.source_timestamp or odd.received_timestamp).replace(tzinfo=timezone.utc)
                if not timedelta(0)<=now-stamp<=timedelta(hours=24):continue
                key=odd.market_key
                if key.startswith('TOTAL_GOALS_'):
                    if odd.line not in {.5,1.5,2.5,3.5,4.5}:continue
                    key=f'{key}:{odd.line}'
                p=pred['probabilities'].get(key)
                if p is None or not math.isfinite(odd.decimal_odds) or odd.decimal_odds<=1:continue
                ev=p*odd.decimal_odds-1
                validated=odd.market_key=='TOTAL_GOALS_OVER' and odd.line==2.5 and pred['validation']['passes']
                output.append({'fixture':match['home']+' v '+match['away'],'market':odd.market_key.replace('_',' ').capitalize(),
                    'competition':match.get('competition',''),
                    'fixture_id':match['fixture_id'],'market_key':odd.market_key,'line':odd.line,'kickoff':match['kickoff'],
                    'model_version':pred.get('model_version','poisson-baseline-v1'),
                    'selection':odd.selection,'odds':odd.decimal_odds,'bookmaker':odd.bookmaker,'probability':p,'ev':ev,
                    'minimum_odds':1.05/p,'sample_home':pred['home_samples'],'sample_away':pred['away_samples'],
                    'status':'Evidence-supported value candidate' if validated and ev>=.05 else 'Research estimate — not a validated recommendation',
                    'recommended':bool(validated and ev>=.05),'validation':pred['validation'],'updated':stamp.isoformat()})
    if not collapse_books:return output
    best={}
    for row in output:
        key=(row['fixture_id'],row['market_key'],row['selection'],row['line'])
        if key not in best or row['odds']>best[key]['odds']:best[key]=row
    return sorted(best.values(),key=lambda r:(r['recommended'],r['probability'],r['ev']),reverse=True)

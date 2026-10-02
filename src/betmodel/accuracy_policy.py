"""Conservative dashboard recommendations, separate from exploratory price combinations."""
from itertools import combinations
from math import prod, isfinite

POLICY='accuracy-v2'
PERFECT_POLICY='perfect-pattern-v1'
MIN_PERFECT_SAMPLE=5
TOP_LEAGUES={
    'E0','SP1','D1','I1','F1','PO1','NL1','BE1','SC0','TR1','GR1','AT1','CH1',
    'DK1','N1','SW1','POL1','CZ1','HR1','SRB1','UKR1','RO1','RUS1','CL','EL',
    'Premier League','English Premier League','La Liga','Primera Division','Bundesliga',
    'Serie A','Ligue 1','Primeira Liga','Eredivisie','Belgian Pro League',
    'Scottish Premiership','Turkish Super League','Greek Super League','Austrian Bundesliga',
    'Swiss Super League','Danish Superliga','Norwegian Eliteserien','Swedish Allsvenskan',
    'Ekstraklasa','Czech First League','Croatian Football League','Serbian SuperLiga',
    'Ukrainian Premier League','Romanian Liga I','Russian Premier League',
    'UEFA Champions League','Champions League','Europa League','Championship','England Championship'
}

def has_perfect_record(row):
    return any(p.get('hits')==p.get('trials') and p.get('trials',0)>=MIN_PERFECT_SAMPLE
               for p in row.get('research_patterns',row.get('patterns',[])))

def top_league(row):
    return row.get('competition') in TOP_LEAGUES

def eligible(row):
    p=row['probability'];odds=row['odds'];validation=row.get('validation',{})
    return (isfinite(p) and isfinite(odds) and .65<=p<1 and odds>1 and bool(row.get('bookmaker'))
        and top_league(row) and has_perfect_record(row)
        and row['market_key']=='TOTAL_GOALS_OVER' and row.get('line')==2.5
        and validation.get('passes') and validation.get('matches',0)>=40
        and min(row.get('sample_home',0),row.get('sample_away',0))>=10 and p*odds-1>=.05)


def select_combinations(rows, limit=5):
    groups={};output={'2':[],'3':[]}
    for row in rows:
        if eligible(row):groups.setdefault(row['bookmaker'],[]).append(row)
    for book,legs in groups.items():
        # One eligible over-2.5 market per fixture/book; probability first, not EV.
        unique={}
        for leg in sorted(legs,key=lambda r:(r['probability'],r['odds']),reverse=True):unique.setdefault(leg['fixture_id'],leg)
        selected=list(unique.values())[:24]
        for n in range(2,min(4,len(selected))+1):
            for combo in combinations(selected,n):
                odds=prod(l['odds'] for l in combo);p=prod(l['probability'] for l in combo)
                target='2' if 1.8<=odds<=2.3 else '3' if 2.6<=odds<=3.5 else None
                if target is None or p<.5 or p*odds-1<.05:continue
                quality=min(min(l['sample_home'],l['sample_away'])/40 for l in combo)
                quality=min(1,quality)
                patterns=[r for l in combo for r in l.get('patterns',[])]
                # Nested rolling windows are not independent evidence; never sum their hit rates.
                evidence=min((max((r['lower'] for r in l.get('patterns',[])),default=0) for l in combo),default=0)
                components={'win_probability':6*p,'sample_coverage':2*quality,'historical_support':2*evidence}
                score=min(9.9,sum(components.values()))
                item={'legs':[dict(l,ev=l['probability']*l['odds']-1) for l in combo],
                    'total_odds':odds,'joint_probability':p,'risk':1-p,'ev':p*odds-1,
                    'minimum_odds':1.05/p,'safety_rating':score,'score_components':components,
                    'avg_data_quality':quality,'avg_pattern_strength':evidence,
                    'model_version':POLICY+'|'+','.join(sorted({l['model_version'] for l in combo})),
                    'policy':POLICY,'bookmaker':book,
                    'score_note':'Evidence score, not a calibrated safety probability. Joint probability assumes independent matches.'}
                output[target].append(item)
    other={'2':[],'3':[]}
    for target,items in output.items():
        items.sort(key=lambda c:(c['joint_probability'],c['safety_rating'],-len(c['legs']),c['ev']),reverse=True)
        unique={}
        for c in items:
            key=tuple(sorted((l['fixture_id'],l['market_key'],l['line']) for l in c['legs']))
            unique.setdefault(key,c)
        ranked=list(unique.values())
        output[target]=ranked if limit is None else ranked[:limit]
        other[target]=[] if limit is None else ranked[limit:]
    return output


def analyze_evidence(engine,window,now=None):
    from .team_insights import evidence_for
    from .historical_suggestions import suggestions,priced_patterns,build_combinations,POLICY
    evidence=evidence_for(engine,window,forecasts=False,all_competitions=True)
    from datetime import datetime,timezone
    now=now or datetime.now(timezone.utc)
    leads=suggestions(evidence,now)
    rows=priced_patterns(engine,evidence,now)
    result=build_combinations(rows)
    upcoming=[m for m in evidence['matches'] if m.get('status')=='SCHEDULED' and m.get('kickoff')
        and datetime.fromisoformat(m['kickoff'].replace('Z','+00:00'))>now]
    diagnostics=dict(loaded_fixtures=len(evidence['matches']),upcoming_fixtures=len(upcoming),
        historical_matches=evidence.get('historical_matches',0),
        fixtures_with_history=sum(any(t.get('matches',0) for t in m.get('individual',[])) for m in upcoming),
        fixtures_with_perfect_records=len(leads),priced_markets=len(rows))
    prefix=('No fixtures are loaded for the selected date. Refresh all sports. ' if not evidence['matches'] else
        'No future scheduled fixtures remain on the selected date. Choose an upcoming date. ' if not upcoming else
        f"Scanned {len(upcoming)} upcoming fixtures; {diagnostics['fixtures_with_history']} have matched team history. ")
    reason=(prefix+f'{len(leads)} fixtures have matching 100% historical records; {len(rows)} exact markets have fresh prices. '
        'Suggestions do not require a model forecast or EV. Priced combinations require separate fixtures, '
        'one bookmaker and prices near the selected target. Missing odds do not hide historical suggestions. '
        'Search is limited to 32 priced selections per bookmaker, up to four legs and 20 combinations per target.')
    return result,dict(valid_candidates=len(rows),scanned_markets=len(rows),search_candidates=min(32,len(rows)),
        limited=True,reason=reason,policy=POLICY,suggestions=leads,diagnostics=diagnostics,
        evidence_combinations={},other_combinations={})

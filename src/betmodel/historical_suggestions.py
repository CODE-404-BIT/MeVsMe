"""Observed records and exactly matching prices, independent of forecast gates."""
from datetime import datetime, timezone, timedelta
from itertools import combinations
from math import prod, isfinite
import re
from sqlalchemy import select
from .db import session_factory
from .models import OddsSnapshot
from .team_insights import team_key

POLICY = 'historical-pattern-v2'


def pattern_market(pattern, match):
    label=pattern['label']
    total=re.fullmatch(r'(Over|Under) ([0-9.]+) goals',label)
    if total:return ('TOTAL_GOALS_'+total[1].upper(),float(total[2]),None)
    if label=='Both teams scored':return ('BTTS_YES',None,None)
    own=re.fullmatch(r'(.+): (\d+)\+ (goals|corners|shots|sot|cards) \((all venues|home|away)\)',label)
    if not own:return None
    team,threshold,stat,venue=own.groups()
    actual='home' if team_key(team)==team_key(match['home']) else 'away' if team_key(team)==team_key(match['away']) else None
    if not actual or venue not in {'all venues',actual}:return None
    return ('TEAM_'+stat.upper()+'_OVER',int(threshold)-.5,match[actual])


def suggestions(evidence, now=None):
    now=now or datetime.now(timezone.utc)
    output=[]
    for m in evidence['matches']:
        if m.get('status') not in {'SCHEDULED','SEARCH'}:continue
        if m.get('kickoff') and datetime.fromisoformat(m['kickoff'].replace('Z','+00:00'))<=now:continue
        patterns=[]
        for p in m['patterns']:
            if p['hits']!=p['trials'] or p['trials']<5 or not pattern_market(p,m):continue
            age=(now.date()-datetime.fromisoformat(p['to']).date()).days
            patterns.append(dict(p,days_since_latest=age,stale=age>30))
        # Nested windows are shown as records, never added as independent evidence.
        patterns.sort(key=lambda p:(p['stale'],-p['trials'],p['label']))
        if patterns:output.append(dict(m,patterns=patterns))
    return output


def priced_patterns(engine,evidence,now=None):
    now=now or datetime.now(timezone.utc);rows=[]
    with session_factory(engine)() as s:
        for m in suggestions(evidence,now):
            if not m.get('kickoff') or m['status']!='SCHEDULED':continue
            odds=s.scalars(select(OddsSnapshot).where(OddsSnapshot.fixture_id==m['fixture_id'])
                .order_by(OddsSnapshot.received_timestamp.desc(),OddsSnapshot.id.desc())).all()
            seen=set()
            for odd in odds:
                ident=(odd.bookmaker,odd.market_key,odd.selection,odd.line)
                if ident in seen:continue
                seen.add(ident)
                stamp=odd.source_timestamp or odd.received_timestamp
                if not stamp:continue
                stamp=stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)
                if not timedelta(0)<=now-stamp<=timedelta(hours=24):continue
                if not odd.bookmaker or not isfinite(odd.decimal_odds) or odd.decimal_odds<=1:continue
                matching=[]
                for p in m['patterns']:
                    key,line,team=pattern_market(p,m)
                    if key!=odd.market_key or line!=odd.line:continue
                    if team and team_key(odd.selection)!=team_key(f'{team} Over {line:g}'):continue
                    matching.append(p)
                if not matching:continue
                rows.append(dict(fixture_id=m['fixture_id'],fixture=m['home']+' v '+m['away'],
                    competition=m['competition'],kickoff=m['kickoff'],market_key=odd.market_key,
                    market=odd.market_key.replace('_',' ').capitalize(),selection=odd.selection,line=odd.line,
                    odds=odd.decimal_odds,bookmaker=odd.bookmaker,updated=stamp.isoformat(),patterns=matching,
                    probability=None,ev=None,model_version=POLICY,
                    why='Exact market matched to the displayed historical records.'))
    return rows


def build_historical_slips(evidence,now=None,limit=20):
    """Two/three selections, never an asserted 2x/3x payout without prices."""
    legs={}
    for match in suggestions(evidence,now):
        if match['status']!='SCHEDULED' or not match.get('kickoff') or not match.get('fixture_id'):continue
        # Pick the largest recent sample for each fixture. Nested records are not separate legs.
        p=match['patterns'][0]
        key,line,team=pattern_market(p,match)
        selection=(f'{team} Over {line:g}' if team else
                   'Yes' if key=='BTTS_YES' else f'{key.rsplit("_",1)[1].title()} {line:g}')
        legs.setdefault(match['fixture_id'],dict(fixture_id=match['fixture_id'],
            fixture=match['home']+' v '+match['away'],competition=match['competition'],
            kickoff=match['kickoff'],market_key=key,market=key.replace('_',' ').capitalize(),
            selection=selection,line=line,patterns=[p],odds=None,bookmaker=None,probability=None))
    candidates=sorted(legs.values(),key=lambda l:(l['patterns'][0]['stale'],
        -l['patterns'][0]['trials'],l['patterns'][0]['days_since_latest'],l['fixture_id']))[:32]
    output={'2':[],'3':[]}
    for n in (2,3):
        for combo in combinations(candidates,n):
            sample=min(l['patterns'][0]['trials'] for l in combo)
            age=max(l['patterns'][0]['days_since_latest'] for l in combo)
            score=min(9.9,7*min(sample/20,1)+3*max(0,1-age/180))
            output[str(n)].append(dict(legs=list(combo),selection_count=n,total_odds=None,
                joint_probability=None,ev=None,safety_rating=score,unpriced=True,
                score_note='Evidence score reflects sample size and recency, not win probability.'))
        output[str(n)].sort(key=lambda s:-s['safety_rating'])
        output[str(n)]=output[str(n)][:limit]
    return output


def build_combinations(rows,limit=20):
    groups={};output={'2':[],'3':[]}
    for row in rows:groups.setdefault(row['bookmaker'],[]).append(row)
    for book,legs in groups.items():
        # Bounded search; prioritise larger, newer samples, never a fictitious win chance.
        legs=sorted(legs,key=lambda l:(min(p['days_since_latest'] for p in l['patterns']),
                    -max(p['trials'] for p in l['patterns'])))[:32]
        for n in range(2,min(4,len(legs))+1):
            for combo in combinations(legs,n):
                if len({l['fixture_id'] for l in combo})!=n:continue
                odds=prod(l['odds'] for l in combo)
                target='2' if 1.8<=odds<=2.3 else '3' if 2.6<=odds<=3.5 else None
                if target is None:continue
                sample=min(max(p['trials'] for p in l['patterns']) for l in combo)
                age=max(min(p['days_since_latest'] for p in l['patterns']) for l in combo)
                score=min(9.9,7*min(sample/20,1)+3*max(0,1-age/180))
                output[target].append(dict(legs=list(combo),total_odds=odds,bookmaker=book,
                    joint_probability=None,ev=None,risk=None,minimum_odds=None,safety_rating=score,
                    sample_floor=sample,latest_age=age,policy=POLICY,model_version=POLICY,
                    score_note='Evidence score = sample coverage (up to 7) + recency (up to 3). It is not a win probability or safety guarantee.'))
    for target,items in output.items():
        items.sort(key=lambda c:(-c['safety_rating'],len(c['legs']),abs(c['total_odds']-int(target))))
        unique={}
        for c in items:
            key=tuple(sorted((l['fixture_id'],l['market_key'],l['selection'],l['line']) for l in c['legs']))
            unique.setdefault(key,c)
        output[target]=list(unique.values())[:limit]
    return output

"""Immutable prospective combination snapshots and unit-stake settlement."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math

from sqlalchemy import Column, DateTime, Float, Integer, JSON, MetaData, String, Table, select
from .db import conflict_insert
from sqlalchemy.orm import Session

from .models import Fixture, TeamMatchStat, ProviderMapping

_metadata = MetaData()
saved_combinations = Table(
    'saved_combinations', _metadata,
    Column('id', Integer, primary_key=True), Column('identity', String, unique=True, nullable=False),
    Column('target', String, nullable=False), Column('mode', String, nullable=False),
    Column('created_at', DateTime, nullable=False), Column('legs', JSON, nullable=False),
    Column('joint_probability', Float), Column('model_version', String),
    Column('outcome', String), Column('payout', Float), Column('binary_outcome', Integer),
)


def _init(engine):
    _metadata.create_all(engine, checkfirst=True)


def _utc(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value


def _probability(value):
    try:
        value = float(value)
        return value if math.isfinite(value) and 0 <= value <= 1 else None
    except (TypeError, ValueError, OverflowError):
        return None


def record_combinations(engine, target, mode, items, now=None):
    """Save the first valid pre-kickoff snapshot, independent of price revisions."""
    _init(engine)
    target = str(target).removesuffix('x')
    if target not in {'2', '3'} or mode not in {'odds-only', 'model', 'historical'}:
        raise ValueError('Unknown performance cohort')
    now = _utc(now or datetime.now(timezone.utc))
    added = 0
    items = list(items)
    fixture_ids = set()
    for item in items:
        for leg in item.get('legs', []):
            try:
                fixture_ids.add(int(leg['fixture_id']))
            except (KeyError, TypeError, ValueError, OverflowError):
                pass
    with Session(engine) as session:
        fixtures = {}
        ordered_ids = sorted(fixture_ids)
        for start in range(0, len(ordered_ids), 500):
            fixtures.update((f.id, f) for f in session.scalars(select(Fixture).where(Fixture.id.in_(ordered_ids[start:start+500]))))
        for item in items:
            try:
                legs = []
                for leg in item['legs']:
                    fixture_id = int(leg['fixture_id'])
                    fixture = fixtures.get(fixture_id)
                    odds = float(leg['odds'])
                    line = None if leg.get('line') is None else float(leg['line'])
                    if (not fixture or fixture.status != 'SCHEDULED' or not fixture.kickoff
                            or _utc(fixture.kickoff) <= now or not math.isfinite(odds) or odds <= 1
                            or (line is not None and (not math.isfinite(line) or line < 0))):
                        raise ValueError('Invalid prospective leg')
                    if not all(isinstance(leg.get(key), str) and leg[key].strip()
                               for key in ('market_key', 'selection', 'bookmaker')):
                        raise ValueError('Missing selection identity')
                    legs.append(dict(fixture_id=fixture_id, market_key=leg['market_key'],
                                     selection=leg['selection'], line=line, odds=odds, bookmaker=leg['bookmaker']))
                    if mode == 'model':
                        legs[-1]['probability'] = _probability(leg.get('probability'))
                        legs[-1]['model_version'] = str(leg['model_version']) if leg.get('model_version') is not None else None
                    if mode == 'historical':
                        legs[-1]['patterns'] = leg.get('patterns', [])
                if not legs or len({leg['fixture_id'] for leg in legs}) != len(legs):
                    continue
                identities = [{key: value for key, value in leg.items() if key not in {'odds', 'probability', 'model_version', 'patterns'}} for leg in legs]
                identities.sort(key=lambda leg: json.dumps(leg, sort_keys=True))
                identity = hashlib.sha256(json.dumps([target, mode, identities], sort_keys=True).encode()).hexdigest()
                probability = _probability(item.get('joint_probability')) if mode == 'model' else None
                version = item.get('model_version')
                result = session.execute(conflict_insert(saved_combinations,engine).values(
                    identity=identity, target=target, mode=mode, created_at=now, legs=legs,
                    joint_probability=probability, model_version=str(version) if version is not None else None,
                ).on_conflict_do_nothing(index_elements=['identity']))
                added += result.rowcount
            except (KeyError, TypeError, ValueError, OverflowError):
                continue
        session.commit()
    return added


def _leg_result(session, leg, cache):
    fixture_id = leg['fixture_id']
    if fixture_id not in cache:
        fixture = session.get(Fixture, fixture_id)
        rows = session.scalars(select(TeamMatchStat).where(TeamMatchStat.fixture_id == fixture_id)).all()
        verified_cancel = False
        if fixture and fixture.source == 'api-football' and fixture.status == 'CANCELLED':
            verified_cancel = session.scalar(select(ProviderMapping.id).where(
                ProviderMapping.source == 'api-football', ProviderMapping.entity_type == 'fixture_final_status',
                ProviderMapping.provider_key == str(fixture.provider_id), ProviderMapping.canonical_key == 'CANC')) is not None
        cache[fixture_id] = fixture, rows, verified_cancel
    fixture, rows, verified_cancel = cache[fixture_id]
    if not fixture:
        return None
    if fixture.status == 'CANCELLED':
        return (1., 'void') if fixture.source != 'api-football' or verified_cancel else None
    if fixture.status != 'FINISHED':
        return None
    home = [r for r in rows if r.is_home == 1]
    away = [r for r in rows if r.is_home == 0]
    if len(home) != 1 or len(away) != 1:
        return None
    home, away = home[0], away[0]
    key, odds = leg['market_key'], leg['odds']
    def finite(value):
        return value is not None and math.isfinite(value) and value >= 0
    if key in {'MATCH_HOME', 'MATCH_DRAW', 'MATCH_AWAY', 'BTTS_YES', 'BTTS_NO'}:
        h, a = home.goals, away.goals
        if not finite(h) or not finite(a):
            return None
        won = {'MATCH_HOME': h > a, 'MATCH_DRAW': h == a, 'MATCH_AWAY': h < a,
               'BTTS_YES': h > 0 and a > 0, 'BTTS_NO': h == 0 or a == 0}[key]
        return (odds, 'won') if won else (0., 'lost')
    families = {'TOTAL_GOALS': 'goals', 'TOTAL_CORNERS': 'corners', 'TOTAL_CARDS': 'cards',
                'TEAM_GOALS':'goals','TEAM_CORNERS':'corners','TEAM_CARDS':'cards',
                'TEAM_SHOTS':'shots','TEAM_SOT':'shots_on_target'}
    family, _, side = key.rpartition('_')
    if family not in families or side not in {'OVER', 'UNDER'} or leg['line'] is None:
        return None
    if family.startswith('TEAM_'):
        from .normalize import normalize_name
        import re
        selection=re.fullmatch(r'(.+) (Over|Under) ([0-9.]+)',leg['selection'],re.I)
        if not selection or selection[2].upper()!=side or float(selection[3])!=leg['line']:return None
        team=normalize_name(selection[1])
        own=home if team==normalize_name(fixture.home_team) else away if team==normalize_name(fixture.away_team) else None
        if own is None:return None
        value=getattr(own,families[family])
        if not finite(value):return None
    else:
        h,a=getattr(home,families[family]),getattr(away,families[family])
        if not finite(h) or not finite(a):return None
        value=h+a
    line = leg['line']
    if not math.isclose(line * 4, round(line * 4), abs_tol=1e-8):
        return None
    lines = [line - .25, line + .25] if round(line * 4) % 2 else [line]
    payouts = []
    for threshold in lines:
        difference = (value - threshold) * (1 if side == 'OVER' else -1)
        payouts.append(odds if difference > 0 else 0. if difference < 0 else 1.)
    payout = sum(payouts) / len(payouts)
    outcome = 'won' if all(p == odds for p in payouts) else 'lost' if all(p == 0 for p in payouts) else 'void' if all(p == 1 for p in payouts) else 'partial'
    return payout, outcome


def settle_saved(engine):
    """Settle only when every leg has an explicit supported final result."""
    _init(engine)
    count = 0
    with Session(engine) as session:
        cache = {}
        for row in session.execute(select(saved_combinations).where(saved_combinations.c.outcome.is_(None))).mappings():
            results = [_leg_result(session, leg, cache) for leg in row['legs']]
            if any(result is None for result in results):
                continue
            payout = math.prod(result[0] for result in results)
            statuses = [result[1] for result in results]
            binary = all(status in {'won', 'lost'} for status in statuses)
            outcome = ('lost' if payout == 0 else 'won') if binary else 'void' if all(status == 'void' for status in statuses) else 'partial'
            session.execute(saved_combinations.update().where(saved_combinations.c.id == row['id']).values(
                outcome=outcome, payout=payout, binary_outcome=int(payout > 0) if binary else None))
            count += 1
        session.commit()
    return count


def pending_fixture_ids(engine):
    _init(engine)
    with engine.connect() as connection:
        rows = connection.execute(select(saved_combinations.c.legs).where(saved_combinations.c.outcome.is_(None)))
        return sorted({int(leg['fixture_id']) for row in rows for leg in row.legs})


def performance_summary(engine, window=None, current_policy=False):
    _init(engine)
    summary = {mode: {target: dict(generated=0, pending=0, settled=0, won=0, lost=0,
               partial=0, void=0, win_rate=None, roi=None, brier=None, brier_sample_size=0)
               for target in ('2', '3')} for mode in ('odds-only', 'model', 'historical')}
    with engine.connect() as connection:
        query=select(*(saved_combinations.c[key] for key in
                ('mode', 'target', 'outcome', 'payout', 'binary_outcome', 'joint_probability', 'model_version')))
        if window:query=query.where(saved_combinations.c.created_at>=_utc(window[0]),saved_combinations.c.created_at<_utc(window[1]))
        rows = list(connection.execute(query).mappings())
    for mode, targets in summary.items():
        for target, result in targets.items():
            cohort = [r for r in rows if r['mode'] == mode and r['target'] == target
                      and (not current_policy or mode != 'model' or str(r['model_version'] or '').startswith(('accuracy-v2','perfect-pattern-v1')))]
            settled = [r for r in cohort if r['outcome'] is not None]
            result.update(generated=len(cohort), settled=len(settled), pending=len(cohort)-len(settled))
            for row in settled:
                result[row['outcome']] += 1
            binary_count = result['won'] + result['lost']
            result['win_rate'] = result['won'] / binary_count if binary_count else None
            result['roi'] = sum(r['payout'] - 1 for r in settled) / len(settled) if settled else None
            scored = [r for r in settled if r['binary_outcome'] is not None and r['joint_probability'] is not None]
            result['brier_sample_size'] = len(scored)
            result['brier'] = sum((r['joint_probability']-r['binary_outcome'])**2 for r in scored)/len(scored) if scored else None
    return summary


def prediction_history(engine,window,mode='model',page=1,size=12):
    if mode not in {'model','odds-only','historical'} or page<1 or not 1<=size<=50:
        raise ValueError('Invalid history filter')
    summary=performance_summary(engine,window)[mode]
    query=select(saved_combinations).where(saved_combinations.c.mode==mode,
        saved_combinations.c.created_at>=_utc(window[0]),saved_combinations.c.created_at<_utc(window[1]))
    with Session(engine) as session:
        rows=session.execute(query.order_by(saved_combinations.c.created_at.desc(),saved_combinations.c.id.desc())
            .offset((page-1)*size).limit(size)).mappings().all()
        items=[]
        for row in rows:
            item=dict(row);item['created_at']=row['created_at'].replace(tzinfo=timezone.utc).isoformat()
            item['total_odds']=math.prod(leg['odds'] for leg in row['legs'])
            item['outcome']=row['outcome'] or 'pending'
            item['legs']=[dict(leg) for leg in row['legs']]
            for leg in item['legs']:
                fixture=session.get(Fixture,leg['fixture_id'])
                leg['fixture']=f'{fixture.home_team} v {fixture.away_team}' if fixture else 'Fixture unavailable'
            items.append(item)
    return {'items':items,'summary':summary,'total':sum(s['generated'] for s in summary.values()),'page':page,'size':size}

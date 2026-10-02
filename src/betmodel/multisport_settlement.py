"""Immutable selection snapshots and separate verified-result settlements."""
import hashlib
import json
from sqlalchemy import Table,Column,String,JSON,DateTime,select
from .db import conflict_insert
from .multisport_store import metadata,snapshots,load_events,utc

settlements=Table('sport_settlements',metadata,Column('key',String(240),primary_key=True),
    Column('settled_at',DateTime,nullable=False),Column('payload',JSON,nullable=False))


def freeze_sport_combinations(engine,groups,now):
    with engine.begin() as connection:
        for target,items in groups.items():
            for item in items:
                identity=sorted((leg['event_key'],leg.get('bookmaker',item.get('bookmaker','')),
                    leg['market'],leg['selection'],str(leg.get('line')),leg['scope'],leg['odds'],leg['updated']) for leg in item['legs'])
                key=hashlib.sha256(json.dumps(['historical',target,identity]).encode()).hexdigest()
                payload=dict(item,kind='historical',target=target)
                statement=conflict_insert(snapshots,engine).values(key=key,event_key=item['legs'][0]['event_key'],
                    created_at=utc(now).replace(tzinfo=None),payload=payload)
                connection.execute(statement.on_conflict_do_nothing(index_elements=['key']))


def settle_sports(engine,now):
    events={r['event_key']:r for r in load_events(engine)}
    from .models import Fixture,TeamMatchStat
    with engine.connect() as connection:
        football={row.id:row for row in connection.execute(select(Fixture.id,Fixture.status,Fixture.kickoff))}
        goals={}
        for row in connection.execute(select(TeamMatchStat.fixture_id,TeamMatchStat.is_home,TeamMatchStat.goals)):
            goals.setdefault(row.fixture_id,{})[row.is_home]=row.goals
    def outcome(leg):
        key=leg['event_key']
        if key.startswith('football:'):
            fid=int(key.split(':')[1]);fixture=football.get(fid);scores=goals.get(fid,{})
            if not fixture or fixture.status!='FINISHED' or len(scores)!=2 or any(v is None for v in scores.values()):return None
            if leg.get('market')!='Total goals 2.5':return None
            over=sum(scores.values())>2.5
            return over if leg['selection']=='Over 2.5' else not over if leg['selection']=='Under 2.5' else None
        event=events.get(key)
        if not event or event['status']!='FINISHED' or utc(event['start'])>=now:return None
        if event.get('retirement') or event.get('walkover') or leg.get('scope')!=event['scope']:return None
        if leg['market']!='winner':return None
        a,b=event.get('home_score'),event.get('away_score')
        if a is None or b is None or a==b:return None
        if leg['selection'] not in {event['home'],event['away']}:return None
        return leg['selection']==(event['home'] if a>b else event['away'])
    count=0
    with engine.begin() as connection:
        settled=set(connection.scalars(select(settlements.c.key)))
        for row in connection.execute(select(snapshots)).mappings():
            if row['key'] in settled:continue
            payload=row['payload'];legs=payload.get('legs',[payload])
            results=[outcome(leg) for leg in legs]
            if not results or any(value is None for value in results):continue
            result={'kind':payload.get('kind','model'),'outcome':'won' if all(results) else 'lost','leg_results':results}
            statement=conflict_insert(settlements,engine).values(key=row['key'],settled_at=utc(now).replace(tzinfo=None),payload=result)
            inserted=connection.execute(statement.on_conflict_do_nothing(index_elements=['key']))
            count+=max(0,inserted.rowcount)
    return count


def sport_performance(engine):
    totals={kind:{'generated':0,'won':0,'lost':0,'pending':0,'win_rate':None} for kind in ('model','historical')}
    with engine.connect() as connection:
        for payload in connection.scalars(select(snapshots.c.payload)):
            totals[payload.get('kind','model')]['generated']+=1
        for payload in connection.scalars(select(settlements.c.payload)):
            totals[payload['kind']][payload['outcome']]+=1
    for row in totals.values():
        settled=row['won']+row['lost'];row['pending']=row['generated']-settled
        if settled:row['win_rate']=row['won']/settled
    return totals

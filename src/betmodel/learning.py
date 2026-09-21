"""Persisted, competition-scoped Poisson updates with untouched later evaluation."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math

import numpy as np
import pandas as pd
from scipy.stats import poisson
from sqlalchemy import Column, Integer, MetaData, String, Table, Text, select
from .models_goals import GoalModel, fit_poisson_goal_model

BASELINE_VERSION = 'poisson-baseline-v1'
metadata = MetaData()
attempts = Table('learning_attempts', metadata,
    Column('id', Integer, primary_key=True), Column('competition', String, nullable=False),
    Column('payload', Text, nullable=False))


def load_history(engine, cutoff):
    from .team_insights import load_history as load
    return load(engine, cutoff)


def _records(engine):
    metadata.create_all(engine, checkfirst=True)
    with engine.connect() as connection:
        return [json.loads(row.payload) for row in connection.execute(select(attempts).order_by(attempts.c.id))]


def learning_summary(engine):
    records = _records(engine)
    latest_by_competition = {r['competition']:r for r in records}
    champions = {r['competition']:r['version'] for r in records if r['status']=='promoted'}
    public = lambda r: {k:v for k,v in r.items() if k!='model'}
    return {'attempts':len(records), 'promoted':sum(r['status']=='promoted' for r in records),
        'champions':len(champions), 'active_versions':champions,
        'latest':public(records[-1]) if records else None,
        'competitions':[public(r) for r in latest_by_competition.values()],
        'explanation':'Updates require 120 completed competition matches and 40 untouched evaluation matches; candidates must improve both Brier score and log loss against incumbent and historical frequency. Validation covers Over 2.5 only.'}


def _fit(frame, strength):
    raw = fit_poisson_goal_model(frame, frame.date.max()+pd.Timedelta(days=1))
    values = asdict(raw)
    for field, venue in [('home_attack','home'),('home_defence','home'),('away_attack','away'),('away_defence','away')]:
        counts = frame.groupby(venue+'_team').size()
        values[field] = {team:1+(ratio-1)*int(counts.get(team,0))/(int(counts.get(team,0))+strength)
            if int(counts.get(team,0))+strength else 1 for team,ratio in values[field].items() if counts.get(team,0)>0}
    return GoalModel(**values)


def _score(model, evaluation, constant=None):
    outcomes=(evaluation.home_goals+evaluation.away_goals>2.5).to_numpy(dtype=float)
    probabilities=np.array([float(poisson.sf(2,sum(model.expected_goals(r.home_team,r.away_team))))
        for r in evaluation.itertuples()]) if constant is None else np.full(len(evaluation),constant)
    probabilities=np.clip(probabilities,1e-9,1-1e-9)
    return {'brier':float(np.mean((probabilities-outcomes)**2)),
        'log_loss':float(-np.mean(outcomes*np.log(probabilities)+(1-outcomes)*np.log1p(-probabilities)))}


def update_models(engine, now=None):
    now=now or datetime.now(timezone.utc)
    now=now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
    frame=load_history(engine,now)
    records=_records(engine)
    waiting=[]
    if frame.empty:return learning_summary(engine)
    for competition,pool in frame.groupby('competition'):
        pool=pool.sort_values('date').copy()
        pool=pool[pool.date<pd.Timestamp(now.date())]
        if pool.empty:continue
        previous=[r for r in records if r['competition']==competition]
        fingerprint=hashlib.sha256(pool[['date','home_team','away_team','home_goals','away_goals']].to_json(orient='records',date_format='iso').encode()).hexdigest()
        if previous and previous[-1]['fingerprint']==fingerprint:continue
        record={'competition':str(competition),'created_at':now.isoformat(),'fingerprint':fingerprint,
            'samples':len(pool),'status':'retained','reason':'Insufficient completed history (minimum 120 matches).',
            'version':BASELINE_VERSION,'training_cutoff':pool.date.max().date().isoformat()}
        champions=[r for r in previous if r['status']=='promoted']
        incumbent=champions[-1] if champions else None
        record['version']=incumbent['version'] if incumbent else BASELINE_VERSION
        # A date belongs wholly to one partition, even when many matches share it.
        if len(pool)>=120:
            eval_start=pool.iloc[-40].date
            earlier=pool[pool.date<eval_start]
            evaluation=pool[pool.date>=eval_start]
            dev_start=earlier.iloc[-20].date if len(earlier)>=80 else None
            training=earlier[earlier.date<dev_start] if dev_start is not None else earlier.iloc[:0]
            development=earlier[earlier.date>=dev_start] if dev_start is not None else earlier.iloc[:0]
            evaluated=[r for r in previous if 'evaluation_end' in r]
            fresh=not evaluated or eval_start>pd.Timestamp(evaluated[-1]['evaluation_end'])
            if not fresh:
                # Do not keep reusing an old holdout to search for a winner.
                count=int((pool.date>pd.Timestamp(evaluated[-1]['evaluation_end'])).sum())
                waiting.append({'competition':str(competition),'new_matches':count,
                    'reason':f'Champion retained: waiting for 40 fresh evaluation matches after {evaluated[-1]["evaluation_end"]}; {count} available.'})
                continue
            if len(training)>=60 and len(development)>=20 and len(evaluation)>=40:
                try:
                    choices=[(strength,_score(_fit(training,strength),development)) for strength in (2,5,10,20,50)]
                    strength=min(choices,key=lambda item:(item[1]['log_loss'],item[1]['brier']))[0]
                    candidate=_fit(earlier,strength)
                    current=GoalModel(**incumbent['model']) if incumbent else _fit(earlier,0)
                    candidate_score=_score(candidate,evaluation)
                    incumbent_score=_score(current,evaluation)
                    baseline_score=_score(candidate,evaluation,float((earlier.home_goals+earlier.away_goals>2.5).mean()))
                    improves=all(candidate_score[metric]+1e-6<other[metric]
                        for other in (incumbent_score,baseline_score) for metric in ('brier','log_loss'))
                    record.update(training_end=training.date.max().date().isoformat(),
                        development_start=development.date.min().date().isoformat(),development_end=development.date.max().date().isoformat(),
                        evaluation_start=evaluation.date.min().date().isoformat(),evaluation_end=evaluation.date.max().date().isoformat(),
                        evaluation_matches=len(evaluation),shrinkage=strength,candidate=candidate_score,
                        incumbent=incumbent_score,baseline=baseline_score,
                        reason='Candidate improved both metrics against incumbent and baseline.' if improves else 'Champion retained: candidate did not improve both metrics against incumbent and baseline.')
                    if improves:
                        record.update(status='promoted',version=f'poisson-{competition}-{fingerprint[:12]}',model=asdict(_fit(pool,strength)))
                except ValueError as error:
                    record.update(status='failed',reason=f'Champion retained: {error}')
        with engine.begin() as connection:
            connection.execute(attempts.insert().values(competition=str(competition),payload=json.dumps(record)))
        records.append(record)
    summary=learning_summary(engine)
    summary['waiting']=waiting
    if waiting:summary['explanation']=' '.join(row['reason'] for row in waiting)+' '+summary['explanation']
    return summary


def apply_learned_forecast(engine, pool, home, away, forecast, cutoff):
    result=dict(forecast)
    result['model_version']=BASELINE_VERSION
    if not forecast.get('available') or pool.empty or 'competition' not in pool:return result
    competitions=pool.competition.unique()
    if len(competitions)!=1:return result
    cutoff_stamp=pd.Timestamp(cutoff)
    cutoff_stamp=cutoff_stamp.tz_localize('UTC') if cutoff_stamp.tzinfo is None else cutoff_stamp.tz_convert('UTC')
    usable=[r for r in _records(engine) if r['competition']==competitions[0] and r['status']=='promoted'
        and pd.Timestamp(r['training_cutoff']).date()<cutoff_stamp.date()
        and pd.Timestamp(r['created_at']).tz_convert('UTC')<=cutoff_stamp]
    if not usable:return result
    champion=usable[-1]
    from .team_insights import team_key
    home,away=team_key(home),team_key(away)
    model=GoalModel(**champion['model'])
    if home not in model.home_attack or home not in model.home_defence or away not in model.away_attack or away not in model.away_defence:
        return result
    lh,la=model.expected_goals(home,away)
    probabilities=model.market_probabilities(home,away)
    for line in (.5,1.5,2.5,3.5,4.5):
        under=float(poisson.cdf(math.floor(line),lh+la))
        probabilities[f'TOTAL_GOALS_UNDER:{line}']=under
        probabilities[f'TOTAL_GOALS_OVER:{line}']=1-under
    result.update(probabilities=probabilities,home_expected_goals=lh,away_expected_goals=la,
        model_version=champion['version'],training_cutoff=champion['training_cutoff'],
        method='Competition-specific shrinkage Poisson; selected chronologically and accepted on later held-out Over 2.5 evaluation.',
        validation={'matches':champion['evaluation_matches'],'market':'Over 2.5 goals',
            'brier':champion['candidate']['brier'],'baseline_brier':champion['baseline']['brier'],
            'log_loss':champion['candidate']['log_loss'],'passes':True,
            'note':'Held-out evaluation covers Over 2.5 only; other markets remain unvalidated.'})
    return result

"""Chronological winner forecasts; no promotion based on training accuracy."""
from collections import defaultdict
from itertools import groupby
import math
import numpy as np
from sklearn.linear_model import LogisticRegression
from .multisport_store import utc

VERSION='sport-winner-logistic-v1'


def _identity(row,side):
    return (row['provider'],row[side+'_id'],row.get('surface','') if row['sport']=='tennis' else '')


def _features(row,ratings,form):
    a,b=_identity(row,'home'),_identity(row,'away')
    def mean(key):return sum(form[key][-10:])/len(form[key][-10:]) if form[key] else .5
    return [(ratings[a]-ratings[b])/400,mean(a)-mean(b)]


def evaluate_winner_model(results, sport, cutoff):
    rows=[r for r in results if r.get('sport')==sport and r.get('status')=='FINISHED'
          and utc(r['start']).date()<cutoff.date() and not r.get('retirement') and not r.get('walkover')
          and isinstance(r.get('home_score'),(int,float)) and isinstance(r.get('away_score'),(int,float))
          and r['home_score']!=r['away_score']]
    rows.sort(key=lambda r:(utc(r['start']),str(r.get('provider_id',''))))
    # Callers must isolate a competition/settlement scope; reject accidental mixtures.
    scopes={(r['competition'],r['scope']) for r in rows}
    if len(scopes)>1:raise ValueError('Models require a single competition and settlement scope')
    ratings=defaultdict(lambda:1500.0);form=defaultdict(list)
    train_x=[];train_y=[];predictions=[];outcomes=[];baselines=[]
    model=None;last_fit=0
    for _,group in groupby(rows,key=lambda r:utc(r['start']).date()):
        group=list(group)
        if len(train_y)>=200 and len(set(train_y))==2 and (model is None or len(train_y)-last_fit>=50):
            model=LogisticRegression(C=1,max_iter=200,random_state=0).fit(train_x,train_y)
            last_fit=len(train_y)
        updates=[]
        for row in group:
            x=_features(row,ratings,form);y=int(row['home_score']>row['away_score'])
            if model is not None:
                predictions.append(float(model.predict_proba([x])[0,1]));outcomes.append(y)
                baselines.append(.5 if sport=='tennis' else (sum(train_y)+1)/(len(train_y)+2))
            updates.append((row,x,y))
        # Nothing on a day's slate learns from another result that same day.
        for row,x,y in updates:
            a,b=_identity(row,'home'),_identity(row,'away')
            expected=1/(1+10**((ratings[b]-ratings[a])/400))
            ratings[a]+=20*(y-expected);ratings[b]-=20*(y-expected)
            form[a].append(y);form[b].append(1-y)
            train_x.append(x);train_y.append(y)
    count=len(outcomes)
    brier=float(np.mean((np.array(predictions)-outcomes)**2)) if count else None
    baseline=float(np.mean((np.array(baselines)-outcomes)**2)) if count else None
    bins=[];covered=0
    for i in range(5):
        selected=[j for j,p in enumerate(predictions) if i/5<=p<(i+1)/5]
        if len(selected)<20:continue
        gap=abs(float(np.mean([predictions[j] for j in selected]))-float(np.mean([outcomes[j] for j in selected])))
        covered+=len(selected);bins.append({'count':len(selected),'gap':gap})
    calibrated=bool(count and covered/count>=.8 and bins and all(b['gap']<=.10 for b in bins))
    validated=bool(count>=100 and brier<baseline and calibrated)
    if len(train_y)>=200 and len(set(train_y))==2:
        model=LogisticRegression(C=1,max_iter=200,random_state=0).fit(train_x,train_y)
    return {'validated':validated,'matches':count,'brier':brier,'baseline_brier':baseline,
            'calibration':bins,'calibrated':calibrated,'model_version':VERSION,
            'coefficients':model.coef_[0].tolist() if model else None,
            'intercept':float(model.intercept_[0]) if model else None,
            'cutoff':cutoff.isoformat()}


def forecast_events(events,results,report,now):
    if report.get('coefficients') is None:return []
    ratings=defaultdict(lambda:1500.0);form=defaultdict(list);latest={}
    for row in sorted(results,key=lambda r:utc(r['start'])):
        if row['status']!='FINISHED' or utc(row['start']).date()>=now.date() or row.get('retirement') or row.get('walkover'):continue
        if row.get('home_score') is None or row.get('away_score') is None or row['home_score']==row['away_score']:continue
        a,b=_identity(row,'home'),_identity(row,'away');y=int(row['home_score']>row['away_score'])
        expected=1/(1+10**((ratings[b]-ratings[a])/400))
        ratings[a]+=20*(y-expected);ratings[b]-=20*(y-expected)
        form[a].append(y);form[b].append(1-y)
        latest[a]=latest[b]=utc(row['start']).date().isoformat()
    output=[]
    for row in events:
        if row['status']!='SCHEDULED' or utc(row['start'])<=now:continue
        a,b=_identity(row,'home'),_identity(row,'away');x=_features(row,ratings,form)
        logit=report['intercept']+sum(c*v for c,v in zip(report['coefficients'],x))
        p=1/(1+math.exp(-max(-30,min(30,logit))))
        output.append(dict(row,market='winner',selection=row['home'] if p>=.5 else row['away'],
            probability=max(p,1-p),validated=report['validated'],validation=report,
            model_version=VERSION,cutoff=report['cutoff'],sample_home=len(form[a]),sample_away=len(form[b]),
            latest_home=latest.get(a),latest_away=latest.get(b),form_home=form[a][-10:],form_away=form[b][-10:]))
    return output

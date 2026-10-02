"""Bounded provider requests with durable budgets and sanitized errors.

Call inside the dashboard's exclusive job guard; the cache/budget is shared across restarts.
"""
from datetime import timedelta
import hashlib
import json
import httpx
from ..state_store import load_state,save_state

BASES={'basketball':'https://v1.basketball.api-sports.io',
       'icehockey':'https://v1.hockey.api-sports.io','odds':'https://api.the-odds-api.com/v4'}


class SportHTTP:
    def __init__(self,engine,http,provider,key,now):
        self.engine,self.http,self.provider,self.key,self.now=engine,http,provider,key,now
        self.identity=hashlib.sha256((provider+':'+key).encode()).hexdigest()

    def get(self,path,params,cost=1,ttl=timedelta(minutes=30)):
        if not self.key:raise ValueError(f'{self.provider} key is not configured')
        if not path.startswith('/') or '://' in path:raise ValueError('Invalid provider path')
        cache='sports-cache:'+hashlib.sha256(json.dumps([self.identity,path,params],sort_keys=True).encode()).hexdigest()
        cached=load_state(self.engine,cache,self.now)
        if cached is not None:
            self.observed_at=cached.get('at',self.now.isoformat())
            return cached['data']
        day=self.now.date().isoformat();month=day[:7]
        budget_key='sports-budget:'+self.identity
        budget=load_state(self.engine,budget_key,self.now) or {}
        if budget.get('month')!=month:budget={'month':month,'monthly_used':0}
        if budget.get('day')!=day:
            budget.update(day=day,daily_used=0)
            if self.provider!='odds':budget.pop('remaining',None)
        daily_limit=14 if self.provider=='odds' else 80
        reserve=50 if self.provider=='odds' else 20
        if budget.get('daily_used',0)+cost>daily_limit:raise ValueError(f'{self.provider} daily request budget reached')
        if self.provider=='odds' and budget.get('monthly_used',0)+cost>450:raise ValueError('Odds monthly reserve reached')
        if budget.get('remaining',10**9)-cost<reserve:raise ValueError(f'{self.provider} provider reserve reached')
        if budget.get('blocked_until','')>self.now.isoformat():raise ValueError(f'{self.provider} requests temporarily paused')
        # Reserve before the call so an interrupted job cannot reset consumption.
        budget['daily_used']=budget.get('daily_used',0)+cost
        budget['monthly_used']=budget.get('monthly_used',0)+cost
        save_state(self.engine,budget_key,budget)
        parameters=dict(params)
        headers={}
        if self.provider=='odds':parameters['apiKey']=self.key
        else:headers['x-apisports-key']=self.key
        try:
            response=self.http.get(BASES[self.provider]+path,params=parameters,headers=headers)
            header='x-requests-remaining' if self.provider=='odds' else 'x-ratelimit-requests-remaining'
            try:budget['remaining']=int(response.headers[header])
            except (KeyError,ValueError):pass
            if response.status_code in {401,403,429}:
                budget['blocked_until']=(self.now+timedelta(minutes=30)).isoformat()
            save_state(self.engine,budget_key,budget)
            if response.status_code!=200:raise ValueError(f'{self.provider} returned HTTP {response.status_code}; check access and quota')
            data=response.json()
            if isinstance(data,dict) and data.get('errors'):raise ValueError(f'{self.provider} rejected the request; check sport/season access')
        except httpx.HTTPError:
            raise ValueError(f'{self.provider} could not be reached') from None
        except (json.JSONDecodeError,UnicodeDecodeError):
            raise ValueError(f'{self.provider} returned an unreadable response') from None
        self.observed_at=self.now.isoformat()
        save_state(self.engine,cache,{'data':data,'at':self.observed_at},self.now+ttl)
        return data

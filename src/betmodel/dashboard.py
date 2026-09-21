"""Local dashboard service. Credentials and job state stay in this process."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import os
import threading

import httpx
from sqlalchemy import select, func

from .config import Settings
from .db import create_engine_for, init_db, session_factory
from .models import Fixture, OddsSnapshot, TeamMatchStat
from .daily import run_daily_pipeline
from .free_data import sync_api_football
from .providers.api_football import ApiFootballClient
from .reporting import _combo_view


def utc_window(day: str, offset: int, end_offset: int) -> tuple[datetime, datetime]:
    local = datetime.combine(date.fromisoformat(day), datetime.min.time())
    if not -840 <= offset <= 840 or not -840 <= end_offset <= 840:
        raise ValueError("Invalid timezone offset")
    start = (local + timedelta(minutes=offset)).replace(tzinfo=timezone.utc)
    end = (local + timedelta(days=1, minutes=end_offset)).replace(tzinfo=timezone.utc)
    return start, end


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class Dashboard:
    def __init__(self, root: Path, *, database_url=None):
        self.settings = Settings(root.resolve(),database_url=database_url)
        self.engine = create_engine_for(self.settings)
        init_db(self.engine)
        self.key = os.getenv("API_FOOTBALL_KEY", "").strip()
        self.lock = threading.RLock()
        self.job = {"state": "idle", "message": "Ready. Load matches to get started.", "kind": None}
        self.quota = None
        self.last_sync = None
        self.analysis = None
        self.results = {"2": [], "3": []}
        self.worker = None
        self.odds_attempts = {}
        self.result_attempts = {}
        self._job_guard = None
        from .state_store import load_state, job_guard
        checkpoint = load_state(self.engine, 'dashboard-checkpoint') or {}
        self.last_sync = checkpoint.get('last_sync')
        self.odds_attempts = {k:datetime.fromisoformat(v) for k,v in checkpoint.get('odds_attempts',{}).items()}
        self.result_attempts = {int(k):v for k,v in checkpoint.get('result_attempts',{}).items()}
        self._restore_quota()
        with job_guard(self.engine) as acquired:
            previous = load_state(self.engine, 'dashboard-job')
            if previous:
                self.job = previous
                if acquired and previous.get('state') == 'running':
                    self.job = dict(previous, state='interrupted', message='The server restarted during this operation. You can retry it.')

    def _restore_quota(self):
        from .state_store import load_state, quota_key
        saved = load_state(self.engine, quota_key(self.key)) if self.key else None
        self.quota = dict(saved['quota']) if saved else None
        if saved and datetime.now(timezone.utc)-datetime.fromisoformat(saved['observed']) > timedelta(minutes=1):
            self.quota['minute_remaining'] = None

    def _restore_checkpoint(self):
        from .state_store import load_state
        checkpoint=load_state(self.engine,'dashboard-checkpoint') or {}
        self.last_sync=checkpoint.get('last_sync',self.last_sync)
        self.odds_attempts.update({k:datetime.fromisoformat(v) for k,v in checkpoint.get('odds_attempts',{}).items()})
        self.result_attempts.update({int(k):v for k,v in checkpoint.get('result_attempts',{}).items()})

    def _reconcile_job(self):
        if self.worker and self.worker.is_alive():return
        from .state_store import job_guard,load_state,save_state
        with job_guard(self.engine) as acquired:
            previous=load_state(self.engine,'dashboard-job')
            if previous:
                if acquired and previous.get('state')=='running':
                    previous=dict(previous,state='interrupted',message='The server restarted during this operation. You can retry it.')
                    save_state(self.engine,'dashboard-job',previous)
                self.job=previous
            self._restore_checkpoint()
            self._restore_quota()

    def _checkpoint(self):
        from .state_store import save_state, quota_key
        now = datetime.now(timezone.utc)
        save_state(self.engine, 'dashboard-job', self.job)
        save_state(self.engine, 'dashboard-checkpoint', {
            'last_sync':self.last_sync, 'odds_attempts':{str(k):v.isoformat() for k,v in self.odds_attempts.items()},
            'result_attempts':{str(k):v for k,v in self.result_attempts.items()}})

    def performance(self):
        from .performance import performance_summary
        from .learning import learning_summary
        return {'cohorts':performance_summary(self.engine, current_policy=True), 'learning':learning_summary(self.engine)}

    def learn(self):
        from .learning import update_models, learning_summary
        previous = learning_summary(self.engine)['promoted']
        result = update_models(self.engine)
        return f"Model evaluation complete. {result.get('promoted', 0)-previous} new accepted model updates. " + result.get('explanation', '')

    def refresh_results(self):
        from .performance import settle_saved, pending_fixture_ids
        from .result_refresh import refresh_results
        settled = settle_saved(self.engine)
        ids = sorted(pending_fixture_ids(self.engine), key=lambda fid:self.result_attempts.get(fid, ''))
        detail = ''
        if ids and self.key:
            with httpx.Client(timeout=20) as http:
                report = refresh_results(self.engine, ApiFootballClient(self.key, http=http,checkpoint_engine=self.engine), ids, known_quota=self.quota)
            stamp = datetime.now(timezone.utc).isoformat()
            self.result_attempts.update({fid:stamp for fid in report['attempted']})
            if report['quota']:self.quota = report['quota']
            settled += settle_saved(self.engine)
            detail = f" Checked {report['requests']} fixtures."
            if report['limited']:detail += ' Request limit reached; refresh results later to continue.'
        elif ids:
            detail = ' Add your API key in Settings to fetch outstanding results.'
        learning = self.learn()
        return f"Results updated: {settled} combinations settled." + detail + ' ' + learning

    def price_combinations(self, day, offset, end_offset, target, page=1, now=None):
        from .odds_only import price_combinations
        from .performance import record_combinations
        if target not in {'2','3'} or page < 1:raise ValueError('Invalid combination page')
        with self.lock:
            result = price_combinations(self.engine, utc_window(day,offset,end_offset), target, now=now)
            record_combinations(self.engine, target, 'historical', result['items'], now=now)
        return {**result, 'items':result['items'][(page-1)*12:page*12], 'total':len(result['items']), 'page':page}

    def set_key(self, value: str):
        value = value.strip()
        if len(value) > 256 or any(ord(ch) < 33 or ord(ch) > 126 for ch in value):
            raise ValueError("The key must contain only printable characters with no spaces.")
        with self.lock:
            self.key = value
            self._restore_quota()

    def status(self):
        with self.lock:
            self._reconcile_job()
            return {"app": "daily-model-dashboard", "job": dict(self.job), "quota": self.quota,
                    "last_sync": self.last_sync, "analysis": self.analysis,
                    "key_configured": bool(self.key)}

    def matches(self, day, offset, end_offset):
        start, end = utc_window(day, offset, end_offset)
        from .league_scope import in_scope,fixture_metadata,is_top_division
        from .team_insights import load_history,competition_history,team_key,predict_match
        history=load_history(self.engine,start)
        Session = session_factory(self.engine)
        with Session() as session:
            metadata=fixture_metadata(session)
            fixtures = session.scalars(select(Fixture).where(
                Fixture.kickoff >= start.replace(tzinfo=None), Fixture.kickoff < end.replace(tzinfo=None)
            ).order_by(Fixture.kickoff)).all()
            counts = dict(session.execute(select(TeamMatchStat.team_name, func.count()).join(
                Fixture, TeamMatchStat.fixture_id == Fixture.id).where(
                Fixture.status == "FINISHED", Fixture.match_date < start.date(),
                TeamMatchStat.goals.is_not(None)
            ).group_by(TeamMatchStat.team_name)).all())
            odds = {row[0]: (row[1], row[2]) for row in session.execute(select(
                OddsSnapshot.fixture_id, func.count(), func.max(OddsSnapshot.received_timestamp)
            ).group_by(OddsSnapshot.fixture_id)).all()}
            rows = []
            unresolved=0
            for f in fixtures:
                info=metadata.get(f.provider_id,{}) if f.source=='api-football' else {}
                if not in_scope(f.competition,info.get('country')):
                    if f.source=='api-football' and not info.get('country'):unresolved+=1
                    continue
                count, timestamp = odds.get(f.id, (0, None))
                pool=competition_history(history,f.competition,f.home_team,f.away_team,info.get('league_id'))
                def samples(team):
                    return int(((pool.home_team==team_key(team))|(pool.away_team==team_key(team))).sum()) if not pool.empty else 0
                history_home = samples(f.home_team)
                history_away = samples(f.away_team)
                if (not history_home or not history_away) and not is_top_division(f.competition,info.get('country')):
                    continue
                forecast=predict_match(pool,f.home_team,f.away_team)
                confidence=None;confidence_selection=None
                if forecast['available']:
                    choices={key:forecast['probabilities'][key] for key in ('MATCH_HOME','MATCH_DRAW','MATCH_AWAY')}
                    confidence_selection=max(choices,key=choices.get)
                    confidence=choices[confidence_selection]
                rows.append({"id": f.id, "home": f.home_team, "away": f.away_team,
                             "competition": f.competition, "status": f.status,
                             "kickoff": aware(f.kickoff).isoformat(), "odds_count": count,
                             "odds_updated": aware(timestamp).isoformat() if timestamp else None,
                             "history_home": history_home, "history_away": history_away,
                             "confidence":confidence,"confidence_selection":confidence_selection,
                             "confidence_reason":forecast.get('reason','Uncalibrated match-result model estimate; not a guarantee.')})
        now=datetime.now(timezone.utc)
        rows.sort(key=lambda r:(datetime.fromisoformat(r['kickoff'])<=now, r['kickoff']))
        coverage='European top domestic divisions plus the Championship. Provider coverage varies.'
        if unresolved:coverage+=f' Refresh fixtures to resolve country metadata for {unresolved} older entries.'
        return {"date": day, "matches": rows, "coverage": coverage}

    def start(self, kind, day, offset, end_offset, query=''):
        utc_window(day, offset, end_offset)
        if kind not in {"sync", "analyze", "research", "results", "learn"}:
            raise ValueError("Unknown action")
        with self.lock:
            if self.job["state"] == "running":
                if self.worker and self.worker.is_alive():return False
            if kind == "sync" and not self.key:
                raise ValueError("Add your API-FOOTBALL key in Settings to refresh. Saved matches are available without a key.")
            from .state_store import job_guard
            guard = job_guard(self.engine)
            if not guard.__enter__():
                guard.__exit__(None,None,None)
                return False
            self._job_guard = guard
            try:
                self._restore_quota()
                self._restore_checkpoint()
                messages = {'research':'Researching historical data…','sync':'Refreshing fixtures…',
                            'results':'Checking saved predictions against final results…','learn':'Evaluating model updates on later unseen results…',
                            'analyze':'Analyzing saved markets…'}
                self.job = {"state": "running", "message":messages[kind], "kind": kind}
                self.job['started_at'] = datetime.now(timezone.utc).isoformat()
                self._checkpoint()
                self.worker = threading.Thread(target=self._work, args=(kind, day, offset, end_offset, query), daemon=True)
                self.worker.start()
            except Exception:
                self.job={'state':'error','kind':kind,'message':'Could not start the operation. Please retry.'}
                try:
                    from .state_store import save_state
                    save_state(self.engine,'dashboard-job',self.job)
                finally:
                    guard.__exit__(None,None,None)
                    self._job_guard=None
                raise
            return True

    def _work(self, kind, day, offset, end_offset, query=''):
        try:
            if kind == 'results':message = self.refresh_results()
            elif kind == 'learn':message = self.learn()
            elif kind == 'research':message = self.research(day, offset, end_offset, query)
            elif kind == 'sync':message = self.sync(day, offset, end_offset)
            else:message = self.analyze(day, offset, end_offset)
            with self.lock:
                self.job = {"state": "done", "message": message, "kind": kind}
        except Exception as exc:
            if isinstance(exc, httpx.HTTPStatusError):
                code = exc.response.status_code
                message = ("Provider rate limit reached. Wait before refreshing again." if code == 429
                           else f"Provider returned HTTP {code}. Check your key, plan and quota in the provider dashboard.")
            elif isinstance(exc, httpx.RequestError):
                message = "Could not connect to the provider. Check your internet connection and try again."
            elif isinstance(exc, ValueError):
                message = str(exc)
            else:
                message = "The operation could not complete. Check provider access and available historical data."
            with self.lock:
                self.job = {"state": "error", "message": message.replace(self.key, "[redacted]") if self.key else message, "kind": kind}
        finally:
            try:
                self._restore_quota()
                self._checkpoint()
            finally:
                if self._job_guard:
                    self._job_guard.__exit__(None,None,None)
                    self._job_guard = None

    def research(self, day, offset, end_offset, query=''):
        from .history_research import research_history
        def progress(message):
            with self.lock:self.job['message'] = message
        report = research_history(self.engine, self.settings.root_dir, self.key,
                                  utc_window(day, offset, end_offset), progress, self.quota, query)
        total = sum(item['matches'] for item in report['sources'])
        with self.lock:
            if report.get('quota'):self.quota=report['quota']
            self.analysis = None
            self.results = {'2': [], '3': []}
        from .performance import settle_saved
        settle_saved(self.engine)
        learning = self.learn()
        return f"Research complete: {total} historical results processed. " + ' '.join(report['messages']) + ' ' + learning

    def insights(self, day, offset, end_offset, query='', recommendations=False):
        from .team_insights import evidence_for, ranked_selections
        import json
        evidence = evidence_for(self.engine, utc_window(day, offset, end_offset), query)
        from .historical_suggestions import suggestions
        evidence['suggestions']=suggestions(evidence)
        report = self.settings.raw_dir / 'research' / 'report.json'
        from .state_store import load_state
        evidence['research'] = load_state(self.engine, 'research-report') or (json.loads(report.read_text(encoding='utf-8')) if report.exists() else None)
        if recommendations:
            evidence['selections'] = ranked_selections(self.engine, evidence)
            from .recommendation_diagnostics import diagnostics
            evidence['diagnostics'] = diagnostics(self.engine, evidence)
        return evidence

    def sync(self, day, offset, end_offset):
        start, end = utc_window(day, offset, end_offset)
        dates = sorted({start.date(), (end - timedelta(microseconds=1)).date()})
        Session = session_factory(self.engine)
        with Session() as session:
            existing = {row[0]: row[1] for row in session.execute(select(Fixture.provider_id,
                func.max(OddsSnapshot.received_timestamp)).join(OddsSnapshot, Fixture.id == OddsSnapshot.fixture_id)
                .where(Fixture.source == "api-football").group_by(Fixture.provider_id)).all()}
        now = datetime.now(timezone.utc)
        def priority(fixture):
            from .league_scope import in_scope
            stamp = self.odds_attempts.get(fixture.provider_id) or existing.get(fixture.provider_id)
            in_window = start <= aware(fixture.kickoff) < end
            return (not in_scope(fixture.competition,fixture.country),not in_window,
                    stamp is not None and now - aware(stamp) < timedelta(hours=6))
        totals = [0, 0]
        partial = False
        pending = 0
        with httpx.Client(timeout=20) as http:
            client = ApiFootballClient(self.key, http=http,checkpoint_engine=self.engine)
            for index, utc_day in enumerate(dates):
                # The prior UTC date may already be over, but its fixtures still belong to the local day.
                result = sync_api_football(self.engine, client, utc_day.isoformat(), fixture_priority=priority)
                totals[0] += result.summary.fixtures
                totals[1] += result.summary.odds_rows
                pending += result.pending_odds
                self.odds_attempts.update({fixture_id: now for fixture_id in result.attempted_fixture_ids})
                with self.lock:
                    self.quota = asdict(result.quota)
                    self.last_sync = datetime.now(timezone.utc).isoformat()
                    self.analysis = None
                    self.results = {"2": [], "3": []}
                if result.rate_limited or (result.quota.remaining is not None and result.quota.remaining <= 20):
                    partial = True
                    break
        return f"Saved {totals[0]} fixtures and {totals[1]} odds records." + (
            f" Partial odds coverage: {pending} upcoming fixtures not checked; refresh later to continue." if pending or partial
            else " Refresh complete. Provider odds may not be available for every match.")

    def analyze(self, day, offset, end_offset, now=None):
        from .accuracy_policy import analyze_evidence
        from .performance import record_combinations
        with self.lock:
            self.results={'2':[],'3':[]};self.analysis=None
        results,analysis=analyze_evidence(self.engine,utc_window(day,offset,end_offset),now)
        with self.lock:
            self.results=results
            self.analysis=dict(analysis,date=day,offset=offset,end_offset=end_offset)
            for target,items in results.items():record_combinations(self.engine,target,'historical',items,now=now)
        return f"Analysis complete: {len(results['2'])} recommendations near 2× and {len(results['3'])} near 3×. " + analysis['reason']

    def combinations(self, target, page=1, size=12, positive=False):
        if target not in {"2", "3"} or page < 1 or not 1 <= size <= 50:
            raise ValueError("Invalid results page")
        with self.lock:
            rows = self.results[target]
            if positive:
                rows = [r for r in rows if r.get("ev") is not None and r["ev"] >= 0.05]
            return {"items": rows[(page-1)*size:page*size], "total": len(rows), "page": page,
                    "size": size, "analysis": self.analysis}

"""Verified result ingestion and quota-bounded historical research."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import io
import json
import base64
import httpx
import pandas as pd
from sqlalchemy import select, delete, func
from .db import session_factory
from .models import Fixture, TeamMatchStat, OddsSnapshot, ProviderMapping
from .ingest import ingest_football_data_uk
from .providers.api_football import ApiFootballClient, _quota
from .state_store import load_state, save_state, cached_provider_request, quota_key

ARCHIVES = {
    'premier-league': 'E0', 'la-liga': 'SP1', 'bundesliga': 'D1',
    'serie-a': 'I1', 'ligue-1': 'F1',
}


def ingest_results(engine, payload, cutoff):
    """Only finished regulation-time results; extra-time scores are not goals data."""
    count = 0
    with session_factory(engine).begin() as s:
        for row in payload:
            info, league, teams = row.get('fixture', {}), row.get('league', {}), row.get('teams', {})
            if info.get('status', {}).get('short') not in {'FT', 'AET', 'PEN'}:
                continue
            try:
                kickoff = datetime.fromisoformat(info['date'].replace('Z', '+00:00')).astimezone(timezone.utc)
                score = row.get('score', {}).get('fulltime', {})
                hg, ag = score.get('home'), score.get('away')
                if hg is None or ag is None or kickoff >= cutoff:
                    continue
                if not all(isinstance(v, (int, float)) and 0 <= v <= 50 for v in (hg, ag)):
                    continue
                home, away = teams['home']['name'], teams['away']['name']
                provider_id = str(info['id'])
            except (ValueError, KeyError, TypeError):
                continue
            f = s.scalar(select(Fixture).where(Fixture.source == 'api-football', Fixture.provider_id == provider_id))
            if f is None:
                f = Fixture(source='api-football', provider_id=provider_id, competition=str(league.get('name', '')),
                    season=str(league.get('season', '')), home_team=home, away_team=away)
                s.add(f);s.flush()
            f.kickoff = kickoff.replace(tzinfo=None)
            f.match_date = kickoff.date()
            f.status = 'FINISHED'
            for is_home, name, goals in [(1, home, hg), (0, away, ag)]:
                stat = s.scalar(select(TeamMatchStat).where(TeamMatchStat.fixture_id == f.id, TeamMatchStat.is_home == is_home))
                if stat is None:
                    stat = TeamMatchStat(fixture_id=f.id, team_name=name, is_home=is_home)
                    s.add(stat)
                stat.goals = goals
            mapping = s.scalar(select(ProviderMapping).where(ProviderMapping.source == 'api-football',
                ProviderMapping.entity_type == 'fixture_league', ProviderMapping.provider_key == provider_id))
            if mapping is None:
                s.add(ProviderMapping(source='api-football', entity_type='fixture_league', provider_key=provider_id,
                    canonical_key=str(league.get('id', ''))))
            count += 1
    return count


def import_archives(engine, root, http=None):
    folder = Path(root) / 'data' / 'raw' / 'research'
    folder.mkdir(parents=True, exist_ok=True)
    output = []
    own = http is None
    http = http or httpx.Client(timeout=30, follow_redirects=True)
    try:
        for league, code in ARCHIVES.items():
            url = f'https://raw.githubusercontent.com/datasets/football-datasets/main/datasets/{league}/season-2526.csv'
            cached = folder / f'{code}-2526.csv'
            stored = load_state(engine,'archive:'+code+':2526')
            if stored:
                output.append(stored)
                continue
            try:
                if not cached.exists():
                    try:
                        response = http.get(url);response.raise_for_status()
                        content = response.content
                    except httpx.HTTPError:
                        api_url=f'https://api.github.com/repos/datasets/football-datasets/contents/datasets/{league}/season-2526.csv?ref=main'
                        response=http.get(api_url);response.raise_for_status()
                        content=base64.b64decode(response.json()['content'])
                    frame = pd.read_csv(io.BytesIO(content))
                    if not {'Date','HomeTeam','AwayTeam','FTHG','FTAG'}.issubset(frame.columns):
                        raise ValueError('Missing required match columns')
                    dates = pd.to_datetime(frame['Date'], format='%Y-%m-%d', errors='raise')
                    if not len(frame) or dates.min() < pd.Timestamp('2025-07-01') or dates.max() >= pd.Timestamp('2026-07-01'):
                        raise ValueError('Unexpected season dates')
                    frame['Date'] = dates.dt.strftime('%d/%m/%Y')
                    frame.to_csv(cached, index=False)
                summary = ingest_football_data_uk(engine, cached, code, '2025-26')
                entry={'source': url, 'competition': code, 'matches': summary.fixtures, 'status': 'loaded'}
                output.append(entry)
                save_state(engine,'archive:'+code+':2526',entry)
            except (httpx.HTTPError, ValueError, OSError, KeyError):
                output.append({'source': url, 'competition': code, 'matches': 0, 'status': 'unavailable'})
    finally:
        if own:http.close()
    return output


def import_current_season(engine, root, http=None, now=None, codes=None):
    """Refresh published completed results, with a six-hour cache and visible freshness."""
    now=now or datetime.now(timezone.utc)
    year=now.year if now.month>=7 else now.year-1
    season=f'{year%100:02}{(year+1)%100:02}'
    folder=Path(root)/'data/raw/research';folder.mkdir(parents=True,exist_ok=True)
    codes=codes or ['E0','E1','SC0','SP1','D1','I1','F1','P1','N1','B1','T1','G1']
    own=http is None;http=http or httpx.Client(timeout=20,follow_redirects=True)
    report=[]
    try:
        for code in codes:
            url=f'https://www.football-data.co.uk/mmz4281/{season}/{code}.csv'
            cache=folder/f'{code}-{season}-current.csv'
            stored=load_state(engine,f'current:{code}:{season}',now)
            if stored:
                report.append(stored)
                continue
            status='loaded';latest=None;count=0
            try:
                if not cache.exists() or now.timestamp()-cache.stat().st_mtime>21600:
                    response=http.get(url);response.raise_for_status()
                    if response.url.host not in {'www.football-data.co.uk','football-data.co.uk'}:
                        raise ValueError('Unexpected results source')
                    frame=pd.read_csv(io.BytesIO(response.content))
                    if not {'Date','HomeTeam','AwayTeam','FTHG','FTAG'}.issubset(frame.columns):
                        raise ValueError('Missing result columns')
                    if 'Div' in frame and not frame.Div.dropna().eq(code).all():raise ValueError('Unexpected league')
                    dates=pd.to_datetime(frame.Date,dayfirst=True,errors='raise')
                    mask=(dates>=pd.Timestamp(year,7,1))&(dates<=pd.Timestamp(now.date()))&frame.FTHG.notna()&frame.FTAG.notna()
                    frame=frame.loc[mask].copy()
                    if frame.empty:raise ValueError('No completed results published')
                    frame['Date']=dates[mask].dt.strftime('%d/%m/%Y')
                    frame.to_csv(cache,index=False)
            except (httpx.HTTPError,ValueError,OSError):
                status='refresh unavailable; using cached results' if cache.exists() else 'current-season source unavailable'
            if cache.exists():
                frame=pd.read_csv(cache)
                latest=pd.to_datetime(frame.Date,dayfirst=True).max().date().isoformat()
                canonical={'P1':'PO1','N1':'NL1','B1':'BE1','T1':'TR1','G1':'GR1'}.get(code,code)
                count=ingest_football_data_uk(engine,cache,canonical,f'{year}-{str(year+1)[2:]}').fixtures
            entry=dict(source=url,competition=code,matches=count,status=status,latest_result=latest)
            report.append(entry)
            if count and status=='loaded':save_state(engine,f'current:{code}:{season}',entry,now+timedelta(hours=6))
    finally:
        if own:http.close()
    return report


def research_history(engine, root, key, window, progress=lambda message: None, known_quota=None, query=''):
    """Bulk history uses at most eight API requests per run and preserves a daily reserve."""
    progress('Loading public historical archives for five major leagues…')
    report = {'updated': datetime.now(timezone.utc).isoformat(), 'sources': import_archives(engine, root), 'messages': []}
    progress('Refreshing current-season completed results, including the Championship…')
    report['sources'].extend(import_current_season(engine,root))
    from .public_history import research_public_history
    progress('Checking verified public result pages for covered teams…')
    report['sources'].extend(research_public_history(engine,root,window))
    folder = Path(root) / 'data' / 'raw' / 'research'
    requested=[]
    if query.strip():
        import re
        requested=re.split(r'\s+(?:vs?\.?|versus)\s+',query.strip(),flags=re.I)
        if len(requested)!=2:raise ValueError('Enter two teams as Team X vs Team Y.')
    if not key:
        report['messages'].append('Add an API key to research the selected day’s other competitions.')
    else:
        with session_factory(engine)() as s:
            targets = s.scalars(select(Fixture).outerjoin(OddsSnapshot).where(
                Fixture.source == 'api-football', Fixture.kickoff >= window[0].replace(tzinfo=None),
                Fixture.kickoff < window[1].replace(tzinfo=None)).group_by(Fixture.id)
                .order_by(func.count(OddsSnapshot.id).desc(), Fixture.kickoff)).all()
            if requested:
                from .team_insights import team_key
                all_fixtures=s.scalars(select(Fixture).where(Fixture.source=='api-football').order_by(Fixture.kickoff.desc())).all()
                targets=[f for f in all_fixtures if {team_key(f.home_team),team_key(f.away_team)}=={team_key(t) for t in requested}][:1]
        client = ApiFootballClient(key,checkpoint_engine=engine)
        requests = 0
        seen = set()
        from .providers.api_football import ApiQuota
        quota = ApiQuota(known_quota.get('limit'),known_quota.get('remaining'),None,None) if known_quota else None
        def live_request(params, path):
            nonlocal requests, quota
            if requests >= 8 or (quota and ((quota.remaining is not None and quota.remaining <= 20)
                    or (quota.minute_remaining is not None and quota.minute_remaining <= 0))):
                raise StopIteration('API request budget reached; run research again later to continue.')
            requests += 1
            response = client._get(path, params)
            quota = _quota(response)
            now=datetime.now(timezone.utc)
            from dataclasses import asdict
            save_state(engine,quota_key(key),{'quota':asdict(quota),'observed':now.isoformat()},
                       (now+timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0))
            return response.json().get('response', [])
        def request(params, path='/fixtures'):
            return cached_provider_request(engine,key,path,params,lambda:live_request(params,path))
        try:
            if requested and not targets:
                from .team_insights import team_key
                for name in requested:
                    progress(f'Resolving provider identity for {name}…')
                    teams=request({'search':name},'/teams')
                    exact=[r['team'] for r in teams if team_key(r.get('team',{}).get('name',''))==team_key(name)]
                    if len(exact)!=1:
                        report['messages'].append(f'{name}: exact provider identity is missing or ambiguous. No team was guessed.')
                        continue
                    team=exact[0]
                    rows=request({'team':str(team['id']),'season':str(window[0].year),'status':'FT-AET-PEN'})
                    count=ingest_results(engine,rows,window[0])
                    report['sources'].append({'source':f"https://v3.football.api-sports.io/fixtures?team={team['id']}&season={window[0].year}",
                        'competition':name,'matches':count,'status':'loaded' if count else 'no accessible results'})
                    for row in rows[-1:]:
                        fid=str(row['fixture']['id'])
                        (folder/f'fixture-{fid}.json').write_text(json.dumps([row]),encoding='utf-8')
                        targets.append(Fixture(provider_id=fid,competition=row['league']['name'],season=str(row['league']['season'])))
            for fixture in targets:
                if (fixture.competition, fixture.season) in seen:continue
                seen.add((fixture.competition, fixture.season))
                meta_path = folder / f'fixture-{fixture.provider_id}.json'
                try:
                    meta = json.loads(meta_path.read_text()) if meta_path.exists() else request({'id': fixture.provider_id})
                    if not meta:continue
                    meta_path.write_text(json.dumps(meta), encoding='utf-8')
                    league = meta[0]['league']
                    lid, season = int(league['id']), int(league['season'])
                    with session_factory(engine).begin() as s:
                        old=s.scalar(select(ProviderMapping).where(ProviderMapping.source=='api-football',ProviderMapping.entity_type=='fixture_league',ProviderMapping.provider_key==fixture.provider_id))
                        if old is None:s.add(ProviderMapping(source='api-football',entity_type='fixture_league',provider_key=fixture.provider_id,canonical_key=str(lid)))
                    for year in (season, season-1):
                        cache = folder / f'league-{lid}-{year}.json'
                        blocked = folder / f'league-{lid}-{year}.blocked'
                        if blocked.exists() and datetime.now().timestamp()-blocked.stat().st_mtime<86400:
                            report['messages'].append(f'{fixture.competition} {year}: provider access unavailable (cached).')
                            continue
                        progress(f'Researching {fixture.competition}, season {year}…')
                        if cache.exists() and datetime.now().timestamp()-cache.stat().st_mtime < 86400:
                            rows=json.loads(cache.read_text())
                        else:
                            try:
                                rows=request({'league':str(lid),'season':str(year),'status':'FT-AET-PEN'})
                            except RuntimeError as exc:
                                if 'season' not in str(exc).lower():raise StopIteration('Provider request rejected; check quota or access before retrying.')
                                blocked.write_text('Provider rejected this season query.',encoding='utf-8')
                                report['messages'].append(f'{fixture.competition} {year}: provider rejected the season query.')
                                continue
                            cache.write_text(json.dumps(rows),encoding='utf-8')
                        count=ingest_results(engine,rows,window[0])
                        report['sources'].append({'source':f'https://v3.football.api-sports.io/fixtures?league={lid}&season={year}',
                            'competition':fixture.competition,'matches':count,'status':'loaded' if count else 'no completed results'})
                except StopIteration as exc:
                    report['messages'].append(str(exc));break
                except (httpx.HTTPError, RuntimeError, ValueError, KeyError):
                    report['messages'].append(f'{fixture.competition}: history unavailable under the current provider access or rate limit.')
                    # Avoid repeating a blocked API request across the entire slate.
                    break
        except StopIteration as exc:
            report['messages'].append(str(exc))
        except (httpx.HTTPError, RuntimeError, ValueError, KeyError):
            report['messages'].append('Team research could not complete under the current provider access. Imported results were retained.')
        finally:
            client.http.close()
        if quota:report['quota']={'limit':quota.limit,'remaining':quota.remaining,'minute_limit':quota.minute_limit,'minute_remaining':quota.minute_remaining}
    (folder / 'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    save_state(engine,'research-report',report)
    return report

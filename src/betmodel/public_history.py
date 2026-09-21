"""Verified public result-page fallback. No predicted scores or inferred squad aliases."""
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path
import re
import httpx
from sqlalchemy import select
from .db import session_factory
from .models import Fixture, TeamMatchStat

BASE='https://www.live-result.com'
# Links verified against the site's country league directory. Youth identities stay separate.
TEAM_PAGES={'gandzasar':'Gandzasar','fc urartu':'Urartu','urartu':'Urartu',
    'kyzyl zhar':'Kyzyl-Zhar','kaisar':'Kaisar-Kyzylorda','fc astana':'FC-Astana',
    'kairat almaty':'Kairat-Almaty','fk tobol kostanay':'Tobol-Kostanay',
    'yelimay semey':'Yelimay-Semey'}


class ResultParser(HTMLParser):
    def __init__(self):
        super().__init__();self.rows=[];self.row=None;self.stack=[]

    def handle_starttag(self,tag,attrs):
        a=dict(attrs);classes=set(a.get('class','').split())
        if tag=='a' and 'matches-list-match' in classes:
            self.row={'url':BASE+a.get('href',''),'home':'','away':'','score':'','finished':False};self.stack=[]
        if self.row is None:return
        if 'match-result-status' in classes:self.row['finished']=bool(classes & {'winner','loser','draw'})
        if tag=='time':self.row['timestamp']=a.get('datetime','')
        if tag=='abbr':self.row['competition']=a.get('title','')
        if tag not in {'img','br','input','hr','meta','link'}:self.stack.append((tag,classes))

    def handle_data(self,data):
        if self.row is None:return
        classes=set().union(*(c for _,c in self.stack)) if self.stack else set()
        key='home' if 'team1' in classes else 'away' if 'team2' in classes else 'score' if 'score' in classes else None
        if key:self.row[key]+=data

    def handle_endtag(self,tag):
        if self.row is None:return
        if tag=='a':self.rows.append(self.row);self.row=None;self.stack=[];return
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:self.stack=self.stack[:i];break


def parse_results(html,cutoff):
    parser=ResultParser();parser.feed(html);output={}
    for row in parser.rows:
        try:
            stamp=datetime.fromisoformat(row['timestamp']).astimezone(timezone.utc)
            score=re.fullmatch(r'\s*(\d{1,2}):(\d{1,2})\s*',row['score'])
            if not row['finished'] or not score or not cutoff-timedelta(days=730)<=stamp<cutoff:continue
            if not row.get('competition') or not row['url'].startswith(BASE+'/football/matches/'):continue
            row.update(home=row['home'].strip(),away=row['away'].strip(),date=stamp.date().isoformat(),
                home_goals=int(score[1]),away_goals=int(score[2]))
            if row['home'] and row['away']:output[row['url']]=row
        except (KeyError,ValueError):continue
    return list(output.values())


def import_public_results(engine,rows):
    # Only league results are used; cup pages can include extra time in final scores.
    allowed={'Armenia / Premier League','Kazakhstan / Premier League'}
    count=0
    with session_factory(engine).begin() as s:
        for row in rows:
            if row['competition'] not in allowed:continue
            f=s.scalar(select(Fixture).where(Fixture.source==BASE,Fixture.provider_id==row['url']))
            if f is None:
                f=Fixture(source=BASE,provider_id=row['url'],competition='public:'+row['competition'],
                    season=row['date'][:4],match_date=datetime.fromisoformat(row['date']).date(),
                    home_team=row['home'],away_team=row['away'],status='FINISHED')
                s.add(f);s.flush()
                for home,name,goals in [(1,row['home'],row['home_goals']),(0,row['away'],row['away_goals'])]:
                    s.add(TeamMatchStat(fixture_id=f.id,team_name=name,is_home=home,goals=goals))
            count+=1
    return count


def research_public_history(engine,root,window,http=None):
    from .team_insights import team_key
    folder=Path(root)/'data/raw/research/public';folder.mkdir(parents=True,exist_ok=True)
    with session_factory(engine)() as s:
        fixtures=s.scalars(select(Fixture).where(Fixture.kickoff>=window[0].replace(tzinfo=None),
            Fixture.kickoff<window[1].replace(tzinfo=None))).all()
    pages=sorted({TEAM_PAGES[key] for f in fixtures for name in (f.home_team,f.away_team)
                  if (key:=team_key(name)) in TEAM_PAGES})
    own=http is None;http=http or httpx.Client(timeout=20,follow_redirects=True)
    reports=[]
    try:
        for slug in pages[:8]:
            url=BASE+'/football/teams/'+slug;cache=folder/(slug+'.html')
            from .state_store import load_state, save_state
            checkpoint_key='public:'+slug+':'+window[0].date().isoformat()
            stored=load_state(engine,checkpoint_key)
            if stored:
                reports.append(stored)
                continue
            try:
                if not cache.exists() or datetime.now().timestamp()-cache.stat().st_mtime>86400:
                    response=http.get(url);response.raise_for_status()
                    if response.url.host!='www.live-result.com':raise ValueError('Unexpected result source')
                    cache.write_text(response.text,encoding='utf-8')
                rows=parse_results(cache.read_text(encoding='utf-8'),window[0])
                count=import_public_results(engine,rows)
                entry={'source':url,'competition':slug,'matches':count,'status':'public results loaded' if count else 'no usable completed league results'}
                reports.append(entry)
                save_state(engine,checkpoint_key,entry,datetime.now(timezone.utc)+timedelta(hours=24))
            except (httpx.HTTPError,OSError,ValueError):
                reports.append({'source':url,'competition':slug,'matches':0,'status':'public source unavailable'})
    finally:
        if own:http.close()
    return reports

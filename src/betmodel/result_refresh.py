"""Fetch outcomes for saved predictions, independently of the displayed match day."""
from dataclasses import asdict
from datetime import datetime, timezone
import httpx
from sqlalchemy import select
from .db import session_factory
from .models import Fixture, ProviderMapping
from .history_research import ingest_results
from .providers.api_football import _quota


def refresh_results(engine, client, fixture_ids, now=None, known_quota=None, max_requests=8):
    now = now or datetime.now(timezone.utc)
    report = {'requests':0, 'updated':0, 'attempted':[], 'quota':known_quota, 'limited':False}
    with session_factory(engine)() as s:
        fixtures = {f.id:f for f in s.scalars(select(Fixture).where(Fixture.id.in_(fixture_ids)))}
    for fid in fixture_ids:
        quota = report['quota'] or {}
        if (report['requests'] >= max_requests or
                (quota.get('remaining') is not None and quota['remaining'] <= 20) or
                (report['requests'] and quota.get('minute_remaining') == 0)):
            report['limited'] = True
            break
        f = fixtures.get(fid)
        if not f or f.source != 'api-football' or not f.provider_id or not f.kickoff:
            continue
        if f.kickoff.replace(tzinfo=timezone.utc) >= now:
            continue
        report['requests'] += 1
        report['attempted'].append(fid)
        try:
            response = client._get('/fixtures', {'id':f.provider_id})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429:raise
            report['limited'] = True
            break
        report['quota'] = asdict(_quota(response))
        rows = [r for r in response.json().get('response', [])
                if str(r.get('fixture', {}).get('id')) == f.provider_id]
        report['updated'] += ingest_results(engine, rows, now)
        for row in rows:
            status = row.get('fixture', {}).get('status', {}).get('short')
            # Abandonments and awarded results depend on bookmaker rules: never infer a refund.
            mapped = {'CANC':'CANCELLED','PST':'POSTPONED','ABD':'ABANDONED',
                      'AWD':'AWARDED','WO':'WALKOVER','1H':'LIVE','HT':'LIVE','2H':'LIVE'}.get(status)
            if mapped:
                with session_factory(engine).begin() as s:
                    s.get(Fixture, fid).status = mapped
                    marker = s.scalar(select(ProviderMapping).where(ProviderMapping.source=='api-football',
                        ProviderMapping.entity_type=='fixture_final_status',ProviderMapping.provider_key==f.provider_id))
                    if marker is None:
                        s.add(ProviderMapping(source='api-football',entity_type='fixture_final_status',
                            provider_key=f.provider_id,canonical_key=status))
                    else:marker.canonical_key=status
    return report

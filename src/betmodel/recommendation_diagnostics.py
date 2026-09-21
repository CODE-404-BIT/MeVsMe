"""Explain why each selected fixture lacks a supported priced recommendation."""
from datetime import datetime, timedelta, timezone
from math import isfinite
from sqlalchemy import select
from .db import session_factory
from .models import OddsSnapshot


def diagnostics(engine, evidence, now=None):
    now = now or datetime.now(timezone.utc)
    result = []
    with session_factory(engine)() as s:
        for match in evidence['matches']:
            forecast = match['forecast']
            name = match['home'] + ' v ' + match['away']
            kickoff = datetime.fromisoformat(match['kickoff'].replace('Z','+00:00')) if match['kickoff'] else None
            if match['status'] != 'SCHEDULED' or not kickoff or kickoff <= now:
                reason = 'Not an upcoming scheduled fixture; no new prediction is issued.'
            elif not forecast['available']:
                reason = forecast['reason']
            else:
                prices = s.scalars(select(OddsSnapshot).where(OddsSnapshot.fixture_id == match['fixture_id'])).all()
                fresh = [o for o in prices if isfinite(o.decimal_odds) and o.decimal_odds > 1 and
                         timedelta(0) <= now - (o.source_timestamp or o.received_timestamp).replace(tzinfo=timezone.utc) <= timedelta(hours=24)]
                rows = [r for r in evidence.get('selections',[]) if r.get('fixture_id') == match['fixture_id']]
                if not prices:reason = 'No bookmaker odds loaded. Refresh Matches of the Day.'
                elif not fresh:reason = 'Saved odds are stale or invalid. Refresh prices before comparing value.'
                elif not rows:reason = 'No fresh price matches a supported model market (1X2, BTTS or half-line goals).'
                elif any(r['recommended'] for r in rows):reason = 'Evidence-supported priced selections are available below.'
                elif not forecast.get('validation',{}).get('passes'):
                    reason = 'Chronological Over 2.5 checks have not established an advantage over the baseline. Other markets remain research estimates.'
                else:reason = 'No validated market clears the +5% estimated value threshold at current prices.'
            result.append({'fixture':name, 'reason':reason})
    return result

"""Documented v4 event/odds adapter. Prices do not provide historical evidence."""
from math import isfinite
from ..multisport_store import event_key,validate_event,utc

PREFIXES={'soccer_':'football','basketball_':'basketball','tennis_':'tennis','icehockey_':'icehockey'}


def sport_for(key):
    return next((sport for prefix,sport in PREFIXES.items() if key.startswith(prefix)),None)


def parse_odds(rows,sport):
    events=[];quotes=[]
    for raw in rows:
        try:
            if sport_for(raw['sport_key'])!=sport:continue
            scope='regulation' if sport=='football' else 'match' if sport=='tennis' else 'including_overtime'
            row=dict(sport=sport,provider='odds-api',provider_id=raw['id'],competition=raw['sport_key'],
                competition_name=raw.get('sport_title',raw['sport_key']),home=raw['home_team'],away=raw['away_team'],
                home_id=raw['home_team'],away_id=raw['away_team'],start=raw['commence_time'],status='SCHEDULED',
                scope=scope,source='https://the-odds-api.com/')
            validate_event(row);row['event_key']=event_key(row);events.append(row)
            for book in raw.get('bookmakers',[]):
                for market in book.get('markets',[]):
                    if market.get('key')!='h2h':continue
                    outcomes=market.get('outcomes',[])
                    expected={row['home'],row['away']}|({'Draw'} if sport=='football' else set())
                    if len(outcomes)!=len(expected) or {o.get('name') for o in outcomes}!=expected:continue
                    prices=[o.get('price') for o in outcomes]
                    if any(not isinstance(p,(int,float)) or not isfinite(p) or p<=1 for p in prices):continue
                    stamp=market.get('last_update',book.get('last_update'));utc(stamp)
                    denominator=sum(1/p for p in prices)
                    for outcome in outcomes:
                        quotes.append(dict(event_key=row['event_key'],sport=sport,bookmaker=book['key'],market='winner',
                            selection=outcome['name'],line=None,scope=scope,odds=outcome['price'],updated=stamp,
                            implied_probability=(1/outcome['price'])/denominator))
        except (KeyError,TypeError,ValueError,AttributeError):continue
    return events,quotes

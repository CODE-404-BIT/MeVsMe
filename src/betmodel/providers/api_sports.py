"""API-Sports basketball/hockey adapters; retain full-game overtime semantics."""
from ..multisport_store import validate_event


def parse_games(sport,rows):
    if sport not in {'basketball','icehockey'}:raise ValueError('Unsupported API-Sports adapter')
    output=[]
    for raw in rows:
        try:
            short=raw['status']['short']
            if short in {'FT','AOT','AP'}:status='FINISHED'
            elif short=='NS':status='SCHEDULED'
            elif short in {'PST','POST'}:status='POSTPONED'
            elif short in {'CANC','ABD','AWD','WO'}:status='CANCELLED'
            elif short in {'Q1','Q2','Q3','Q4','OT','HT','BT','P1','P2','P3','PT'}:status='LIVE'
            else:continue
            teams=raw['teams'];scores=raw.get('scores',{})
            row=dict(sport=sport,provider='api-sports',provider_id=str(raw['id']),
                competition=str(raw['league']['id']),competition_name=raw['league']['name'],
                season=raw['league'].get('season'),home=teams['home']['name'],away=teams['away']['name'],
                home_id=str(teams['home']['id']),away_id=str(teams['away']['id']),
                start=raw['date'],status=status,scope='including_overtime',
                source='https://api-sports.io/sports/'+('hockey' if sport=='icehockey' else sport))
            if status=='FINISHED':
                for side in ('home','away'):
                    score=scores.get(side)
                    row[side+'_score']=score.get('total') if isinstance(score,dict) else score
            validate_event(row)
            output.append(row)
        except (KeyError,TypeError,ValueError):continue
    return output


def fetch_games(client,sport,params,**options):
    payload=client.get('/games',params,**options)
    if not isinstance(payload,dict) or not isinstance(payload.get('response'),list):
        raise ValueError(f'{sport} returned an unexpected game list')
    return [dict(row,observed_at=client.observed_at) for row in parse_games(sport,payload['response'])]

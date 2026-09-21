"""Country-qualified domestic top divisions, plus England's Championship."""
LEAGUES={
 'England':{'Premier League','Championship'},'Scotland':{'Premiership'},
 'Wales':{'Premier League'},'Northern-Ireland':{'Premiership'},'Ireland':{'Premier Division'},
 'Spain':{'La Liga','Primera Division'},'Germany':{'Bundesliga'},'Italy':{'Serie A'},
 'France':{'Ligue 1'},'Portugal':{'Primeira Liga'},'Netherlands':{'Eredivisie'},
 'Belgium':{'Jupiler Pro League','Pro League'},'Austria':{'Bundesliga'},
 'Switzerland':{'Super League'},'Denmark':{'Superliga'},'Sweden':{'Allsvenskan'},
 'Norway':{'Eliteserien'},'Finland':{'Veikkausliiga'},'Iceland':{'Úrvalsdeild','Urvalsdeild'},
 'Poland':{'Ekstraklasa'},'Czech-Republic':{'Czech Liga','First League'},
 'Slovakia':{'Super Liga'},'Hungary':{'NB I'},'Romania':{'Liga I'},'Bulgaria':{'First League'},
 'Croatia':{'HNL'},'Slovenia':{'1. SNL'},'Serbia':{'Super Liga'},
 'Bosnia':{'Premijer Liga'},'Montenegro':{'First League'},'Macedonia':{'First League'},
 'Albania':{'Superliga'},'Kosovo':{'Superliga'},'Greece':{'Super League 1'},
 'Turkey':{'Süper Lig','Super Lig'},'Cyprus':{'1. Division'},'Malta':{'Premier League'},
 'Ukraine':{'Premier League'},'Russia':{'Premier League'},'Belarus':{'Premier League'},
 'Lithuania':{'A Lyga'},'Latvia':{'Virsliga'},'Estonia':{'Meistriliiga'},
 'Moldova':{'Super Liga','Super Liga Moldova'},'Georgia':{'Erovnuli Liga'},
 'Armenia':{'Premier League'},'Azerbaidjan':{'Premyer Liqa'},'Kazakhstan':{'Premier League'},
 'Israel':{'Ligat Ha\'al'},'Luxembourg':{'National Division'},'Andorra':{'Primera Divisió'},
 'San-Marino':{'Campionato'},'Gibraltar':{'Premier Division'},
 'Faroe-Islands':{'Meistaradeildin'},
}
ARCHIVE_CODES={'E0','E1','SP1','D1','I1','F1','P1','PO1','N1','NL1','B1','BE1','SC0','T1','TR1','G1','GR1'}


def in_scope(competition,country=None):
    if country:return competition in LEAGUES.get(country,set())
    # Generic names occur worldwide. A fresh provider sync resolves legacy rows.
    return competition in ARCHIVE_CODES or competition in {
        'Championship','La Liga','Eredivisie','Primeira Liga','Scottish Premiership',
        'Allsvenskan','Eliteserien','Veikkausliiga','Ekstraklasa','Jupiler Pro League',
        'NB I','HNL','1. SNL','A Lyga','Virsliga','Meistriliiga','Erovnuli Liga',
        'Süper Lig','Ligat Ha\'al','Premyer Liqa'}


def is_top_division(competition,country=None):
    return competition not in {'E1','Championship','England Championship'} and in_scope(competition,country)


def fixture_metadata(session):
    import json
    from sqlalchemy import select
    from .models import ProviderMapping
    result={r.provider_key:json.loads(r.canonical_key) for r in session.scalars(select(ProviderMapping)
        .where(ProviderMapping.source=='api-football',ProviderMapping.entity_type=='fixture_competition'))}
    countries={'39':'England','40':'England','140':'Spain','78':'Germany','135':'Italy','61':'France',
        '94':'Portugal','88':'Netherlands','144':'Belgium','179':'Scotland','203':'Turkey','197':'Greece',
        '218':'Austria','207':'Switzerland','119':'Denmark','103':'Norway','113':'Sweden','106':'Poland',
        '345':'Czech-Republic','210':'Croatia','286':'Serbia','333':'Ukraine','283':'Romania','235':'Russia'}
    for r in session.scalars(select(ProviderMapping).where(ProviderMapping.source=='api-football',ProviderMapping.entity_type=='fixture_league')):
        if r.provider_key not in result and r.canonical_key in countries:
            result[r.provider_key]={'country':countries[r.canonical_key],'league_id':r.canonical_key}
    return result

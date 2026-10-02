from betmodel.accuracy_policy import select_combinations

def leg(i,p=.8,odds=1.45,book='A'):
    return dict(fixture_id=i,fixture=str(i),market_key='TOTAL_GOALS_OVER',market='Total goals over',selection='Over 2.5',line=2.5,
        probability=p,odds=odds,bookmaker=book,recommended=True,model_version='test',sample_home=20,sample_away=20,
        competition='E0',validation={'passes':True,'matches':40},
        patterns=[{'hits':5,'trials':5,'rate':1.0,'lower':.55,'label':'Over 2.5 goals','group':'Home','from':'2026-01-01','to':'2026-02-01'}])

def test_recommendations_use_correct_targets_single_book_and_high_probability():
    rows=[leg(1),leg(2),leg(3),leg(4,.05,3.8),leg(5,book='B')]
    result=select_combinations(rows)
    assert result['2'] and result['3']
    for target,items in result.items():
        assert len(items)<=5
        for c in items:
            assert len({l['bookmaker'] for l in c['legs']})==1
            assert all(l['probability']>=.65 for l in c['legs'])
            assert (1.8<=c['total_odds']<=2.3) if target=='2' else (2.6<=c['total_odds']<=3.5)
            assert 0<=c['safety_rating']<10

def test_unvalidated_or_negative_value_legs_are_not_recommended():
    a=leg(1);a['validation']['passes']=False
    assert not select_combinations([a,leg(2)])['2']
    assert not select_combinations([leg(1,.7,1.2),leg(2)])['2']


def test_requires_perfect_record_and_top_tier_league():
    no_perfect=leg(1);no_perfect['patterns'][0]['hits']=4
    outside=leg(1);outside['competition']='Test League'
    assert not select_combinations([no_perfect,leg(2)])['2']
    assert not select_combinations([outside,leg(2)])['2']

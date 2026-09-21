// Historical records are not forecast probabilities.
modeSelect.innerHTML='<option value="model">Historical-pattern combinations</option>';
$('positive').checked=false;
$('positive').closest('label').hidden=true;
const historicalRender=renderCombos;
const historicalDraw=drawInsights;
const patternAnalyses=new Set();
let patternRequest=0;
function patternRows(patterns){
  return patterns.map(p=>`<p><b>100% historical · ${p.hits}/${p.trials}</b> — ${esc(p.label)}<br><small>${esc(p.group)} · ${esc(p.from)} to ${esc(p.to)}${p.stale?' · STALE: latest observation over 30 days old':''}</small></p>`).join('');
}
function suggestionCards(matches){
  return matches.map(m=>`<article class="match-evidence"><small>${esc(m.competition)}</small><h3>${esc(m.home)} vs ${esc(m.away)}</h3>${patternRows(m.patterns)}<details><summary>Match history and sources</summary>${(m.individual||[]).map(t=>`<h4>${esc(t.team)}</h4>${t.recent.map(r=>`<p>${esc(r.date)} · ${esc(r.venue)} vs ${esc(r.opponent)} · ${r.scored}–${r.conceded} · ${esc(r.source)}</p>`).join('')}`).join('')}</details></article>`).join('');
}
drawInsights=function(data){
  if(state.tab!=='recommendations'){
    historicalDraw(data);
    if(state.tab==='insights'){
      const section=document.createElement('section');section.className='historical-suggestions';
      section.innerHTML='<h2>Suggestions from historical records</h2><p>Only records matching the team’s home/away role are used. These are past observations, not a predicted win percentage.</p>'+(data.suggestions?.length?suggestionCards(data.suggestions):'<p>No matching 100% records with five observations are loaded.</p>');
      $('results').prepend(section);
    }
    return;
  }
  const matches=data.suggestions||[];
  $('results').className='insights-list';$('pagination').hidden=true;
  $('result-count').textContent=`${matches.length} fixtures with historical suggestions`;
  $('result-context').textContent='100% refers to the displayed past sample';
  $('results').innerHTML='<p class="evidence-note">Suggestions use matching historical records with at least five observations. Model forecasts and EV do not filter them. A 20/20 record does not guarantee the next result. Stale records are marked; odds are only required to build priced combinations.</p>'+(matches.length?suggestionCards(matches):empty('No matching historical records loaded','Click Research & load history. Fixtures remain visible even when their history is missing.'));
  if(data.research){const sources=document.createElement('details');sources.innerHTML='<summary>Sources and latest published results</summary>'+data.research.sources.map(s=>`<p>${esc(s.competition)} · ${s.matches} results · ${esc(s.status)}${s.latest_result?' · latest '+esc(s.latest_result):''}<br><a href="${esc(s.source)}" target="_blank" rel="noopener noreferrer">Source</a></p>`).join('')+data.research.messages.map(m=>`<p>${esc(m)}</p>`).join('');$('results').append(sources);}
};
renderCombos=async function(){
  if(!['2','3'].includes(state.tab))return historicalRender();
  $('positive').checked=false;$('positive').closest('label').hidden=true;
  $('analyze').hidden=false;
  $('combo-controls').querySelector('p').textContent='Matching historical records · Same bookmaker · Separate fixtures';
  const tab=state.tab;const request=++patternRequest;
  const key=JSON.stringify(params())+'|'+(state.status?.last_sync||'');
  if(!sameAnalysis(state.status?.analysis)&&!state.busy&&!patternAnalyses.has(key)){
    patternAnalyses.add(key);await run('analyze');
  }
  if(state.busy){$('results').innerHTML=empty('Matching records to available prices…','No model or EV threshold is required.');return;}
  const data=await api('/api/combinations?'+new URLSearchParams({target:tab,page:state.page,size:12}));
  if(request!==patternRequest||state.tab!==tab)return;
  if(!sameAnalysis(data.analysis)){$('results').innerHTML=empty('Analyze the selected date','Click Analyze saved matches to build historical-pattern combinations.');return;}
  $('results').className='match-grid combo-grid';
  $('result-context').textContent=tab==='2'?'Combined odds 1.80–2.30':'Combined odds 2.60–3.50';
  const slips=data.analysis.historical_slips?.[tab]||[];
  $('result-count').textContent=`${data.total} priced combinations · ${slips.length} unpriced historical slips`;
  $('results').innerHTML=data.items.length?data.items.map(c=>`<article class="combo-card"><div class="combo-top"><strong>${c.total_odds.toFixed(2)}×</strong><span class="badge">Evidence ${c.safety_rating.toFixed(1)}/10</span></div><div class="combo-legs">${c.legs.map(l=>`<div class="combo-leg"><b>${esc(l.fixture)}</b><p>${esc(l.market)} · ${esc(l.selection)} · ${l.odds.toFixed(2)}</p>${patternRows(l.patterns)}<small>${esc(l.bookmaker)} · Price updated ${esc(new Date(l.updated).toLocaleString())}</small></div>`).join('')}</div><div class="combo-foot">${esc(c.score_note)}<br>No future win probability or EV is assigned. Confirm prices and availability with the bookmaker.</div></article>`).join(''):slips.length?'<p class=hint>No confirmed payout prices yet. Historical slips are available below.</p>':empty('No matching priced combinations',data.analysis.reason);
  paginate(data.total,12);
  const section=document.createElement('section');section.className='historical-slips insights-list';
  section.innerHTML=`<h2>${tab}-selection historical slips</h2><p>Selection count is not payout: these are ${tab} selections, not confirmed ${tab}× odds. Up to 20 slips from 32 fixtures, one historical selection per match. Unpriced drafts are excluded from priced-bet performance tracking.</p>`+(slips.length?slips.map((c,i)=>`<article class="combo-card"><div class="combo-top"><strong>${c.selection_count} selections · Slip ${i+1}</strong><span class="badge">Evidence ${c.safety_rating.toFixed(1)}/10</span></div><p><b>Odds needed — payout unconfirmed</b></p><div class="combo-legs">${c.legs.map(l=>`<div class="combo-leg"><b>${esc(l.fixture)}</b><p>${esc(l.market)} · ${esc(l.selection)}</p>${patternRows(l.patterns)}</div>`).join('')}</div><div class="combo-foot">${esc(c.score_note)}<br>Matching fresh bookmaker prices are required before confirming a 2× or 3× payout. Historical records do not guarantee a win.</div></article>`).join(''):`<p>At least ${tab} different upcoming fixtures with matching historical records are needed. Load matches and research history for this date.</p>`);
  $('results').append(section);
};
openCombinationReview=function(card){cardReview(card);};

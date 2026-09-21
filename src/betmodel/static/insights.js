const insightsStyle=document.createElement('link');insightsStyle.rel='stylesheet';insightsStyle.href='/insights.css';document.head.append(insightsStyle);
const insightsNav=document.querySelector('.sidebar nav');
for(const [tab,title,icon] of [['insights','Team Insights','◎'],['recommendations','Recommended Picks','☆']]){
  const button=document.createElement('button');button.className='nav-item';button.dataset.tab=tab;
  button.innerHTML=`<span>${icon}</span>${title}`;button.addEventListener('click',()=>setTab(tab));insightsNav.append(button);
}
const controls=document.createElement('form');controls.id='insights-controls';controls.className='filters';controls.hidden=true;
controls.innerHTML='<label class="search"><span>⌕</span><input id="team-query" placeholder="Team X vs Team Y — leave blank for today’s matches" aria-label="Team X vs Team Y" list="team-examples"><datalist id="team-examples"></datalist></label><button class="secondary" type="submit">Search evidence →</button><button class="primary compact" type="button" id="research-history">Research & load history ↻</button><label class="check"><input type="checkbox" id="perfect-only" checked>100% historical records only</label>';
document.querySelector('.results-caption').before(controls);
const originalSetTab=setTab;
const originalRefreshStatus=refreshStatus;
let insightRequest=0;
let insightData=null;
function isInsights(){return state.tab==='insights'||state.tab==='recommendations';}
setTab=function(tab){
  controls.hidden=!['insights','recommendations'].includes(tab);
  document.querySelector('.hero').hidden=['insights','recommendations'].includes(tab);
  if(!['insights','recommendations'].includes(tab)){originalSetTab(tab);return;}
  state.tab=tab;state.page=1;
  document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));
  $('match-controls').hidden=true;$('combo-controls').hidden=true;$('pagination').hidden=true;
  $('section-title').textContent=tab==='insights'?'Team Insights':'Recommended Picks';
  $('section-eyebrow').textContent='EVIDENCE, NOT CERTAINTY';$('crumb').textContent=tab==='insights'?'TEAM INSIGHTS':'RECOMMENDED PICKS';
  $('perfect-only').closest('label').hidden=tab!=='insights';
  renderInsights().catch(e=>notice(e.message,true));
};
const formerRenderCombos=renderCombos;
renderCombos=async function(){if(isInsights())return renderInsights();return formerRenderCombos();};
refreshStatus=async function(){const data=await originalRefreshStatus();$('research-history').disabled=state.busy;return data;};
controls.addEventListener('submit',e=>{e.preventDefault();renderInsights().catch(err=>notice(err.message,true));});
$('perfect-only').addEventListener('change',()=>{if(insightData)drawInsights(insightData);});
$('research-history').addEventListener('click',async()=>{try{await refreshStatus();if(state.busy)return;await api('/api/jobs',{kind:'research',...params(),query:$('team-query').value});state.busy=true;await refreshStatus();}catch(e){notice(e.message,true);}});
function individual(team){return `<div class="team-evidence"><h3>${esc(team.team)}</h3><div class="evidence-numbers"><div><strong>${team.matches}</strong><small>RECENT MATCHES</small></div><div><strong>${team.goals_for===undefined||team.goals_for===null?'—':team.goals_for.toFixed(2)}</strong><small>GOALS FOR / MATCH</small></div><div><strong>${team.goals_against===undefined||team.goals_against===null?'—':team.goals_against.toFixed(2)}</strong><small>GOALS AGAINST / MATCH</small></div></div><div class="form-strip">${team.recent.slice(0,10).map(r=>`<span class="form-${r.result}" title="${esc(r.date+' · '+r.opponent+' · '+r.scored+'–'+r.conceded)}">${r.result}</span>`).join('')||'<span class="coverage-warning">No verified history loaded</span>'}</div><details><summary>Results and sources</summary>${team.recent.map(r=>`<p>${esc(r.date)} · ${esc(r.venue)} vs ${esc(r.opponent)} · ${r.scored}–${r.conceded}<small>${esc(r.source)}</small></p>`).join('')||'<p>Use Research & load history. Provider coverage may be limited.</p>'}</details></div>`;}
function drawInsights(data){
  if(!isInsights())return;
  $('results').className='insights-list';$('pagination').hidden=true;
  $('result-count').textContent=`${data.historical_matches} verified historical matches · ${data.matches.length} matchups`;
  $('result-context').textContent='History cutoff: '+new Date(data.cutoff).toLocaleDateString();
  const sourceNote=`<div class="evidence-note"><b>What these numbers mean</b><p>A 100% record means every match in that historical sample met the condition. It is not a guaranteed future result. Combined records pool unique matches; they are not a same-game betting probability.</p><p>${esc(data.limitations.slice(1).join(' '))}</p><details><summary>Research sources and coverage</summary>${data.research?data.research.sources.map(s=>`<p>${esc(s.competition)} · ${s.matches} results · ${esc(s.status)}<br><a href="${esc(s.source)}" target="_blank" rel="noopener noreferrer">Source</a></p>`).join('')+data.research.messages.map(m=>`<p>${esc(m)}</p>`).join(''):'<p>No research run yet. The button loads public archives and, when a key is configured, researches provider league histories.</p>'}</details></div>`;
  if(state.tab==='recommendations'){
    const rows=(data.selections||[]).filter(r=>r.recommended);const recommended=rows;
    $('result-count').textContent=`${recommended.length} deeply researched value candidates`;
    $('results').innerHTML=sourceNote+(rows.length?`<p class="hint">Only selections that pass the full evidence policy are shown. Baseline estimates and unvalidated prices are hidden.</p><div class="match-grid combo-grid">${rows.slice(0,100).map(r=>`<article class="combo-card"><div class="combo-top"><strong>${pct(r.probability)}</strong><span class="badge ready">RESEARCHED BET</span></div><div class="combo-legs"><div class="combo-leg"><b>${esc(r.market)} · ${esc(r.selection)}</b><p>${esc(r.fixture)}</p><p>${esc(r.bookmaker)} · Odds ${r.odds.toFixed(2)} · ${r.sample_home}/${r.sample_away} historical matches</p></div></div><div class="combo-stats"><div><span>ESTIMATED EV</span><b class="${r.ev<0?'negative':'positive'}">${pct(r.ev)}</b></div><div><span>MINIMUM +5% ODDS</span><b>${r.minimum_odds.toFixed(2)}</b></div><div><span>VALIDATION MATCHES</span><b>${r.validation.matches}</b></div></div><div class="combo-foot"><b>Why this bet qualified</b><br>${esc(r.status)}<br>${esc(r.validation.note)}<br>${r.sample_home}/${r.sample_away} team-history samples · ${r.validation.matches} chronological validation matches · Over 2.5 market · +5% EV gate passed<br>Brier: ${r.validation.brier===null?'unavailable':r.validation.brier.toFixed(3)} · Baseline: ${r.validation.baseline_brier===null?'unavailable':r.validation.baseline_brier.toFixed(3)}</div></article>`).join('')}</div>`:empty('No deeply researched bets yet','Research history first. A bet appears only when fresh odds, enough same-competition history, chronological validation, probability and EV gates all pass. Unvalidated estimates are intentionally hidden.'));
    const diagnosticBox=document.createElement('details');diagnosticBox.className='recommendation-diagnostics';diagnosticBox.open=!rows.length;
    diagnosticBox.innerHTML=`<summary>Why picks are available or missing · ${(data.diagnostics||[]).length} matches checked</summary>${(data.diagnostics||[]).map(d=>`<p><b>${esc(d.fixture)}</b><br>${esc(d.reason)}</p>`).join('')||'<p>No fixtures loaded for this date. Load Matches of the Day first.</p>'}`;
    $('results').prepend(diagnosticBox);
    const evidenceCards=data.matches.filter(m=>m.patterns.some(p=>p.hits===p.trials&&p.trials>=5));
    const dailyEvidence=document.createElement('section');dailyEvidence.className='daily-historical-evidence';
    dailyEvidence.innerHTML=`<h2>Today's historical evidence</h2><p class="hint">100% means every match in the stated past sample met the condition. These records are available even when odds or a model recommendation are missing.</p>${evidenceCards.length?evidenceCards.map((m,i)=>`<article class="match-evidence"><h3>Match ${i+1} · ${esc(m.home)} vs ${esc(m.away)}</h3>${m.patterns.filter(p=>p.hits===p.trials&&p.trials>=5).sort((a,b)=>b.trials-a.trials).slice(0,6).map(p=>`<p><b>100% · ${p.hits}/${p.trials}</b> — ${esc(p.label)}<br><small>${esc(p.group)} · ${esc(p.from)} to ${esc(p.to)}</small></p>`).join('')}<details><summary>Check match results and sources</summary>${m.individual.map(t=>`<b>${esc(t.team)}</b>${t.recent.slice(0,20).map(r=>`<p>${esc(r.date)} · ${esc(r.venue)} vs ${esc(r.opponent)} · ${r.scored}–${r.conceded}${r.source.startsWith('https://www.live-result.com/')?` · <a href="${esc(r.source)}" target="_blank" rel="noopener noreferrer">Result source</a>`:` · ${esc(r.source)}`}</p>`).join('')}`).join('')}</details></article>`).join(''):'<p>No qualifying 100% historical records are loaded for these fixtures yet. Research & load history checks the available public sources.</p>'}`;
    $('results').prepend(dailyEvidence);
    return;
  }
  $('results').innerHTML=sourceNote+(data.matches.length?data.matches.map(m=>{
    const patterns=m.patterns.filter(r=>!$('perfect-only').checked||r.hits===r.trials);
    const forecast=m.forecast;
    return `<article class="match-evidence"><div class="evidence-title"><div><small>${esc(m.competition||'Team comparison')}</small><h2>${esc(m.home)} <span>vs</span> ${esc(m.away)}</h2></div><span class="badge">${m.h2h_matches} H2H RESULTS</span></div><div class="individual-grid">${m.individual.map(individual).join('')}</div><div class="forecast-block"><b>Match forecast</b>${forecast.available?`<p>Home ${pct(forecast.probabilities.MATCH_HOME)} · Draw ${pct(forecast.probabilities.MATCH_DRAW)} · Away ${pct(forecast.probabilities.MATCH_AWAY)}</p><p>Expected goals: ${forecast.home_expected_goals.toFixed(2)} / ${forecast.away_expected_goals.toFixed(2)} · ${forecast.competition_samples} competition results</p><small>${esc(forecast.method)}<br>Chronological Over 2.5 check: ${forecast.validation.matches} matches; ${forecast.validation.passes?'beat the baseline':'has not established an advantage over baseline'}.</small>`:`<p class="coverage-warning">${esc(forecast.reason)}</p>`}</div><h3>Historical patterns <small>${patterns.length} found</small></h3>${patterns.length?`<div class="patterns-table">${patterns.map(r=>`<div class="pattern-row"><div><span class="badge ${r.rate===1?'ready':''}">${pct(r.rate)} HISTORICAL</span><b>${esc(r.label)}</b><small>${esc(r.group)} · ${esc(r.from)} to ${esc(r.to)}</small></div><div><strong>${r.hits}/${r.trials}</strong><small>Observed matches</small></div><div><strong>${pct(r.posterior_mean)}</strong><small>Smoothed historical rate<br>95% interval ${pct(r.lower)}–${pct(r.upper)}</small></div></div>`).join('')}</div>`:'<p class="hint">No qualifying patterns with at least five observations. Uncheck “100% historical records only” to inspect 80%+ patterns.</p>'}</article>`;
  }).join(''):empty('No matches for this date','Enter Team X vs Team Y above, or load fixtures for another day.'));
}
async function renderInsights(){
  if(!isInsights())return;
  const req=++insightRequest;const tab=state.tab;
  $('results').className='insights-list';$('results').innerHTML=empty('Checking historical evidence…','Matching teams, scanning past results and checking competition-specific forecasts.');
  const data=await api('/api/insights?'+new URLSearchParams({...params(),query:$('team-query').value,recommendations:true}));
  if(req!==insightRequest||state.tab!==tab)return;
  insightData=data;
  $('team-examples').innerHTML=data.known_teams.slice(0,100).map(t=>`<option value="${esc(t+' vs ')}"></option>`).join('');
  drawInsights(data);
}

const originalDrawInsights=drawInsights;
drawInsights=function(data){
  originalDrawInsights(data);
  if(state.tab!=='insights'||data.suggestions)return;
  document.querySelectorAll('.match-evidence').forEach((card,index)=>{
    const match=data.matches[index];
    const forecast=match?.forecast;
    if(!forecast?.available)return;
    const probabilities=forecast.probabilities||{};
    const options=[['MATCH_HOME',match.home],['MATCH_DRAW','Draw'],['MATCH_AWAY',match.away]]
      .filter(([key])=>Number.isFinite(probabilities[key]))
      .sort((a,b)=>probabilities[b[0]]-probabilities[a[0]]);
    if(!options.length)return;
    const [key,selection]=options[0];
    const recommendation=document.createElement('div');
    recommendation.className='forecast-recommendation';
    recommendation.innerHTML=`<b>Recommended angle</b><p>${esc(selection)} · ${pct(probabilities[key])} model probability</p><small>Based on the available history and forecast. Check current odds before considering it.</small>`;
    card.append(recommendation);
  });
};

document.addEventListener('click',event=>{
  const team=event.target.closest('.match-card .team-name');
  if(!team||typeof setTab!=='function')return;
  const card=team.closest('.match-card');
  const teams=[...card.querySelectorAll('.team-name')].map(node=>node.textContent.trim());
  if(teams.length!==2)return;
  $('team-query').value=`${teams[0]} vs ${teams[1]}`;
  setTab('insights');
});

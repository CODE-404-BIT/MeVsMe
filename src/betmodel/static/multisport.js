// Discovery is automatic on access; provider work always uses the authenticated job route.
const sportsControls=document.createElement('div');
sportsControls.className='filters';sportsControls.hidden=true;
sportsControls.innerHTML='<label for="sport-filter">Sport</label><select id="sport-filter"><option value="all">All sports</option><option value="football">Football</option><option value="basketball">Basketball</option><option value="tennis">Tennis</option><option value="icehockey">Ice hockey</option></select><button id="discover-sports" class="primary compact">Refresh all sports</button>';
document.querySelector('.results-caption').before(sportsControls);
let sportsRequest=0;
const attemptedDiscovery=new Map();
const priorSportTab=setTab;
setTab=function(tab){
  sportsControls.hidden=tab!=='recommendations';
  priorSportTab(tab);
  if(tab==='recommendations'){
    controls.hidden=true;
    $('section-title').textContent='Top 10 picks';
    $('section-eyebrow').textContent='AUTOMATIC DISCOVERY';
  }
};
const priorSportInsights=renderInsights;
renderInsights=async function(){
  if(state.tab!=='recommendations')return priorSportInsights();
  return renderSportPicks();
};
function displayForm(values){
  return (values||[]).map(value=>value===1?'W':value===0?'L':String(value)).join(' ')||'Not available';
}
function confidenceCard(row){
  const validation=row.validation||{};
  return `<article class="sport-pick"><div class="pick-details"><small>${esc(row.sport)} · ${esc(row.competition_name||row.competition)}</small><h3>${esc(row.home)} vs ${esc(row.away)}</h3><p>${esc(new Date(row.start).toLocaleString())}</p><h4>${esc(row.market)} · ${esc(row.selection)}</h4><p>Recent form: ${esc(displayForm(row.form_home))} / ${esc(displayForm(row.form_away))}</p><p>${row.sample_home} / ${row.sample_away} historical observations<br>Latest results: ${esc(row.latest_home)} / ${esc(row.latest_away)}</p><p>${row.odds?`Odds ${Number(row.odds).toFixed(2)} · ${esc(row.bookmaker)}`:'No matching current price attached'}</p><details><summary>How this estimate was checked</summary><p>${validation.matches||0} chronological validation matches. Brier score ${Number.isFinite(validation.brier)?validation.brier.toFixed(3):'unavailable'}; baseline ${Number.isFinite(validation.baseline_brier)?validation.baseline_brier.toFixed(3):'unavailable'}.</p><p>Model ${esc(row.model_version||'')} · Results after the prediction cutoff are excluded.</p></details></div><aside class="pick-scorecard"><span>ESTIMATED WIN PROBABILITY</span><strong>${pct(row.probability)}</strong><span>EVIDENCE CONFIDENCE</span><b>${Number(row.evidence_confidence).toFixed(1)}/10</b><small>Confidence reflects sample coverage and recency. It is not a second win probability or a guarantee.</small></aside></article>`;
}
async function renderSportPicks(){
  const request=++sportsRequest;
  const query={...params(),sport:$('sport-filter').value};
  const data=await api('/api/recommendations?'+new URLSearchParams(query));
  if(request!==sportsRequest||state.tab!=='recommendations')return;
  $('results').className='insights-list';$('pagination').hidden=true;
  $('result-count').textContent=`${(data.items||[]).length} supported picks · maximum 10`;
  $('result-context').textContent=data.updated_at?'Updated '+new Date(data.updated_at).toLocaleString():'No discovery completed yet';
  const coverage=Object.entries(data.coverage||{}).map(([sport,c])=>`<p><b>${esc(sport)}</b> · ${esc((c.status||'unknown').replaceAll('_',' '))} · ${c.discovered||0} events checked${c.odds_status?' · Odds: '+esc(c.odds_status.replaceAll('_',' ')):''}${c.history_status?' · History: '+esc(c.history_status.replaceAll('_',' ')):''}${(c.messages||[]).map(m=>'<br>'+esc(m)).join('')}</p>`).join('');
  $('results').innerHTML='<p class="evidence-note">Ranked picks require tested probability estimates and sufficient recent history. A 100% historical record is shown separately in Team Insights and does not guarantee a future win. Coverage depends on connected providers and free quotas.</p>'+
    `<details id="sport-coverage" open><summary>Sources and coverage by sport</summary>${coverage}</details>`+
    ((data.items||[]).length?data.items.map(confidenceCard).join(''):empty('No validated picks available','Refresh all sports to discover upcoming events. Missing history or failed validation will not be replaced by invented percentages.'))+
    ((data.historical_suggestions||[]).length?`<section class="historical-suggestions"><h2>100% historical suggestions</h2><p>Individual selections from observed records, independent of model validation. These are not priced 2x/3x combinations or guaranteed wins.</p>${suggestionCards(data.historical_suggestions)}</section>`:'')+
    ((data.research_estimates||[]).length?`<details><summary>${data.research_estimates.length} research estimates — not validated picks</summary>${data.research_estimates.slice(0,20).map(r=>`<p>${esc(r.home)} vs ${esc(r.away)} · ${esc(r.selection)} · ${pct(r.probability)} baseline estimate. Validation has not passed.</p>`).join('')}</details>`:'');
  const key=JSON.stringify(params());
  if(data.stale&&!state.busy&&Date.now()-(attemptedDiscovery.get(key)||0)>1800000){
    attemptedDiscovery.set(key,Date.now());
    await run('discover');
  }
}
$('sport-filter').addEventListener('change',()=>renderSportPicks().catch(e=>notice(e.message,true)));
$('discover-sports').addEventListener('click',()=>run('discover'));

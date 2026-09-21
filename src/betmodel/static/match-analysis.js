// History-only match browsing and direct access to the evidence for each fixture.
const confidenceFilter=$('safest-only');
if(confidenceFilter){confidenceFilter.checked=false;const label=confidenceFilter.closest('label');for(const n of label.childNodes)if(n.nodeType===3)n.textContent=' Model result probability ≥70%';}
renderMatches=function(){
  const query=$('search').value.toLowerCase().trim();
  const rows=state.matches.filter(m=>(!query||`${m.home} ${m.away} ${m.competition}`.toLowerCase().includes(query))&&(!$('league').value||m.competition===$('league').value)&&(!$('match-status').value||m.status===$('match-status').value)&&(!confidenceFilter?.checked||(m.confidence??0)>=.7));
  const size=18;state.page=Math.min(state.page,Math.max(1,Math.ceil(rows.length/size)));
  $('results').className='match-grid';$('result-count').textContent=`${rows.length} fixtures`;
  $('result-context').textContent=state.coverage||'Click a team to view stats and historical suggestions';
  const labels={MATCH_HOME:'Home win',MATCH_DRAW:'Draw',MATCH_AWAY:'Away win'};
  $('results').innerHTML=rows.length?rows.slice((state.page-1)*size,state.page*size).map(m=>`<article class="match-card"><div class="card-header"><span class="league-name">${esc(m.competition)}</span><span class="badge">${esc(m.status)}</span></div><div class="card-body">${[m.home,m.away].map(t=>`<button class="team match-team-button" data-match-id="${m.id}">${esc(t)} ↗</button>`).join('')}<div class="match-time">${esc(new Date(m.kickoff).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}))} · ${m.odds_count} odds records</div><p>${m.confidence==null?'Research needed: no full team forecast yet':`${esc(labels[m.confidence_selection])}: <b>${pct(m.confidence)}</b> model estimate`}</p><small>${esc(m.confidence_reason||'Run Research & load history for this fixture.')}</small></div><div class="card-footer">History: ${m.history_home} / ${m.history_away} matches <button class="secondary" data-match-id="${m.id}">Stats & bets →</button></div></article>`).join(''):empty('No top-league fixtures for this date','Refresh fixtures or choose UTC football date.');
  paginate(rows.length,size);
};
$('results').addEventListener('click',e=>{const button=e.target.closest('[data-match-id]');if(!button)return;const m=state.matches.find(r=>String(r.id)===button.dataset.matchId);if(!m)return;$('team-query').value=`${m.home} vs ${m.away}`;setTab('insights');$('section-title').scrollIntoView({block:'start',behavior:'smooth'});});
const matchDrawInsights=drawInsights;
drawInsights=function(data){
  matchDrawInsights(data);
  if(state.tab!=='insights'||!$('team-query').value.trim()||data.suggestions)return;
  const selections=data.selections||[];
  const section=document.createElement('section');section.className='match-evidence';
  section.innerHTML='<h2>Bet analysis for this match</h2>'+(selections.length?`<p>Supported value candidates first, then highest estimated probability. Baseline estimates are not validated recommendations.</p>${selections.slice(0,5).map(r=>`<p><b>${esc(r.market)} · ${esc(r.selection)}</b><br>${pct(r.probability)} estimated probability · odds ${r.odds.toFixed(2)} · EV ${pct(r.ev)}<br>${esc(r.bookmaker)} · ${esc(r.status)}</p>`).join('')}`:'<p>No supported priced selection is available. Team statistics and historical records are shown below; a bet needs fresh odds and sufficient model evidence.</p>');
  $('results').prepend(section);
};
if(state.tab==='matches')renderMatches();

function openCombinationReview(card){
  let dialog=$('combination-research');
  if(!dialog){dialog=document.createElement('dialog');dialog.id='combination-research';document.body.append(dialog);}
  const copy=card.cloneNode(true);copy.removeAttribute('tabindex');copy.removeAttribute('data-combination-index');
  dialog.innerHTML=`<form method="dialog"><div class="dialog-head"><div><div class="eyebrow">RESEARCH REVIEW</div><h2>Why this combination was selected</h2></div><button class="icon-button" aria-label="Close research">×</button></div><p>Each leg shown below passed the available evidence policy. This review explains the research behind the combination; it does not place a bookmaker bet automatically.</p><div class="combination-review-content"></div></form>`;
  dialog.querySelector('.combination-review-content').append(copy);dialog.showModal();
}
document.addEventListener('click',event=>{
  const card=event.target.closest('.combo-card');
  if(card&&!event.target.closest('button,a,details,summary'))openCombinationReview(card);
});
document.addEventListener('keydown',event=>{
  const card=event.target.closest('.combo-card');
  if(card&&(event.key==='Enter'||event.key===' ')){event.preventDefault();openCombinationReview(card);}
});

const cardReview=openCombinationReview;
openCombinationReview=async function(card){
  const index=[...document.querySelectorAll('.combo-card')].indexOf(card);
  if(index<0)return cardReview(card);
  try{
    const data=modeSelect?.value==='odds-only'
      ? await api('/api/price-combinations',{target:state.tab,page:state.page,...params()})
      : await api('/api/combinations?'+new URLSearchParams({target:state.tab,page:state.page,size:12}));
    const combo=data.items[index];
    if(!combo)return cardReview(card);
    const complete=modeSelect?.value==='odds-only'
      ? Boolean(data.researched&&data.research_policy&&combo.legs?.length)
      : Boolean(combo.policy&&combo.score_components&&combo.legs?.length);
    if(!complete){
      let dialog=$('combination-research');
      if(!dialog){dialog=document.createElement('dialog');dialog.id='combination-research';document.body.append(dialog);}
      dialog.innerHTML='<form method="dialog"><div class="dialog-head"><div><div class="eyebrow">RESEARCH REPORT</div><h2>Research data unavailable</h2></div><button class="icon-button" aria-label="Close research">×</button></div><p>This combination is not being presented as a researched bet because its response is missing the required evidence fields. Restart the dashboard server and press Ctrl + F5 to clear the old browser payload.</p><p>Required evidence includes team-history samples, model probability, validation results, historical patterns, research policy and source coverage.</p></form>';
      dialog.showModal();return;
    }
    let dialog=$('combination-research');
    if(!dialog){dialog=document.createElement('dialog');dialog.id='combination-research';document.body.append(dialog);}
    const score=Number.isFinite(Number(combo.safety_rating))?`${Number(combo.safety_rating).toFixed(1)}/10`:'Not available';
    const components=combo.score_components?`Probability ${combo.score_components.win_probability.toFixed(2)}/6 · Sample coverage ${combo.score_components.sample_coverage.toFixed(2)}/2 · Historical support ${combo.score_components.historical_support.toFixed(2)}/2`:'Research policy passed';
    dialog.innerHTML=`<form method="dialog"><div class="dialog-head"><div><div class="eyebrow">RESEARCH REPORT</div><h2>${combo.total_odds.toFixed(2)}x combination</h2></div><button class="icon-button" aria-label="Close research">×</button></div><p><b>Selection basis:</b> ${esc(combo.score_note||'Every leg passed the current research and validation policy.')}</p><p><b>Research policy:</b> ${esc(combo.policy||data.research_policy||'accuracy-v2')} · <b>Safety evidence:</b> ${score} · <b>Bookmaker:</b> ${esc(combo.bookmaker)}</p><p><b>Score components:</b> ${esc(components)}</p><div class="research-detail-legs">${combo.legs.map(leg=>`<section><h3>${esc(leg.fixture)}</h3><p><b>${esc(leg.market)} · ${esc(leg.selection)}</b> at ${leg.odds.toFixed(2)}</p><p>Model probability ${pct(leg.probability)} · EV ${pct(leg.ev)} · Team samples ${leg.sample_home}/${leg.sample_away}</p><p>Chronological validation: ${leg.validation.matches} matches · ${leg.validation.passes?'passed':'not passed'}</p>${leg.why?`<p><b>Why this leg:</b> ${esc(leg.why)}</p>`:''}${leg.correct_scores?.length?`<p><b>Top correct scores:</b> ${leg.correct_scores.slice(0,5).map(s=>`${esc(s.score)} (${pct(s.probability)})`).join(' · ')}</p>`:''}${leg.patterns?.length?`<details open><summary>Historical patterns used</summary>${leg.patterns.map(p=>`<p>${p.hits}/${p.trials} (${pct(p.rate)}) · ${esc(p.label)}<br>${esc(p.group)} · ${esc(p.from)} to ${esc(p.to)}<br>95% interval ${pct(p.lower)}–${pct(p.upper)}</p>`).join('')}</details>`:'<p>No qualifying pattern was used beyond the validated model evidence.</p>'}</section>`).join('')}</div><p class="hint">This is the research behind the displayed candidate. It is not an automatic bet placement and is not a guarantee of the outcome.</p></form>`;
    dialog.showModal();
  }catch(error){notice(`Could not load the research report: ${error.message}`,true);}
};

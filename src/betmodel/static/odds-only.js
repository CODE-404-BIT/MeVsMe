// Keep model-backed analysis available while making price combinations directly browsable.
const modelCombinationRenderer = renderCombos;
const modeSelect = document.createElement('select');
modeSelect.id = 'combination-mode';
modeSelect.setAttribute('aria-label','Combination mode');
modeSelect.innerHTML = '<option value="model">Model-backed combinations</option><option value="odds-only">Odds-only combinations</option>';
$('combo-controls').prepend(modeSelect);
modeSelect.addEventListener('change',()=>{state.page=1;renderCombos().catch(e=>notice(e.message,true));});
let priceRequest = 0;
const automaticAnalyses=new Set();
renderCombos = async function(){
  const oddsOnly=modeSelect.value==='odds-only';
  $('positive').closest('label').hidden=oddsOnly;
  $('analyze').hidden=oddsOnly;
  $('combo-controls').querySelector('p').textContent=oddsOnly?'Research-gated prices · Same bookmaker · Separate matches':'Ranked by model score · Up to 4 legs';
  if(!oddsOnly){
    const key=JSON.stringify(params())+'|'+(state.status?.last_sync||'');
    if(['2','3'].includes(state.tab)&&!sameAnalysis(state.status?.analysis)&&!state.busy&&!automaticAnalyses.has(key)){
      automaticAnalyses.add(key);await run('analyze');
      if(state.busy){$('results').innerHTML=empty('Analyzing saved matches…','Checking history and prices for your selected date. Results appear when analysis finishes.');return;}
    }
    return modelCombinationRenderer();
  }
  const tab=state.tab;if(tab==='matches')return;
  const request=++priceRequest;
  $('results').className='match-grid combo-grid';
  $('results').innerHTML=empty('Finding researched combinations…','Checking saved odds against the evidence and validation policy.');
  $('result-context').textContent=tab==='2'?'Combined odds 1.80–2.30':'Combined odds 2.60–3.50';
  if(!state.token)await refreshStatus();
  let data=await api('/api/price-combinations',{target:tab,page:state.page,...params()});
  if(!data.research_evidence?.[tab]?.length){const selected=params();if(selected.offset||selected.end_offset)data=await api('/api/price-combinations',{target:tab,page:state.page,date:selected.date,offset:0,end_offset:0});}
  if(typeof refreshPerformance==='function'){$('performance-mode').value='odds-only';refreshPerformance().catch(()=>{});}
  if(request!==priceRequest||state.tab!==tab||modeSelect.value!=='odds-only')return;
  $('result-count').textContent=`${data.total} odds-only combinations`;
  notice(data.items.length?'Research-gated prices only: every leg passed the current evidence and validation policy. The combined price is not a new forecast.':'No researched combination passed the evidence gates. '+data.research_report+(data.limited?' Bounded search limits apply.':''));
  $('results').innerHTML=data.items.length?data.items.map((c,i)=>`<article class="combo-card"><div class="combo-top"><div><strong>${c.total_odds.toFixed(2)}×</strong><small>Combination ${(state.page-1)*12+i+1}</small></div><span class="badge ready">RESEARCHED</span></div><div class="combo-legs">${c.legs.map(l=>`<div class="combo-leg"><span class="price">${l.odds.toFixed(2)}</span><b>${esc(l.market)} · ${esc(l.selection)}${l.line!==null?' · Line '+esc(l.line):''}</b><p>${esc(l.fixture)}</p><p>${esc(l.bookmaker)} · ${l.sample_home}/${l.sample_away} history · Model ${pct(l.probability)}</p>${l.correct_scores?.length?`<p>Top correct scores: ${l.correct_scores.slice(0,3).map(s=>`${esc(s.score)} (${pct(s.probability)})`).join(' · ')}</p>`:''}</div>`).join('')}</div><div class="combo-stats"><div><span>CONFIDENCE / SAFETY</span><b>${Number.isFinite(Number(c.safety_rating))?Number(c.safety_rating).toFixed(1):'NOT AVAILABLE'}/10</b></div><div><span>MODEL PROBABILITY</span><b>${pct(c.joint_probability)}</b></div><div><span>LOSS RISK</span><b>${pct(c.risk)}</b></div></div><div class="combo-foot"><b>${esc(c.bookmaker)}</b> · ${c.legs.length} separate matches<br>Every leg passed the evidence policy. Confidence / safety is an evidence score, not a guaranteed win percentage.<br>Top correct scores are Poisson model estimates, not exact predictions.<br>Combined odds are calculated from current saved prices.</div></article>`).join(''):empty('No researched combinations yet','Run Research & load history, refresh current odds, and analyze the selected day. Random price combinations are intentionally blocked.');
  const evidence=data.research_evidence?.[tab]||[];
  if(evidence.length){const section=document.createElement('section');section.className='research-evidence-section';section.innerHTML=`<h2>Research evidence leads</h2><p class="hint">Observed 100% historical records with at least five observations. Research only, not approved bets.</p><div class="match-grid combo-grid">${evidence.map(c=>`<article class="combo-card"><div class="combo-top"><strong>${c.total_odds.toFixed(2)}×</strong><span class="badge warning">RESEARCH ONLY</span></div><div class="combo-legs">${c.legs.map(l=>`<div class="combo-leg"><b>${esc(l.fixture)}</b><p>${esc(l.market)} · ${esc(l.selection)} · ${l.odds.toFixed(2)}</p>${(l.evidence_patterns||[]).map(p=>`<p><b>${p.hits}/${p.trials} · ${pct(p.rate)} observed</b><br>${esc(p.label)} · ${esc(p.group)}</p>`).join('')}</div>`).join('')}</div><div class="combo-foot">${esc(c.research_note)}</div></article>`).join('')}</div>`;$('results').append(section);}
  paginate(data.total,12);
  $('section-title').scrollIntoView({block:'start',behavior:'smooth'});
};

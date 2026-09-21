const historyButton=document.createElement('button');historyButton.className='nav-item';historyButton.dataset.tab='history';historyButton.innerHTML='<span>◷</span>Prediction History';
document.querySelector('.sidebar nav').append(historyButton);
historyButton.addEventListener('click',()=>setTab('history'));
const historyControls=document.createElement('div');historyControls.className='filters';historyControls.hidden=true;
historyControls.innerHTML='<select id="history-mode" aria-label="Prediction history cohort"><option value="historical">Historical suggestions</option><option value="model">Model predictions</option><option value="odds-only">Odds-only combinations</option></select><p>Saved on the selected date · Win rate excludes pending, partial settlements and refunds.</p><button class="secondary" id="history-refresh">Refresh outcomes</button>';
document.querySelector('.results-caption').before(historyControls);
const historySetTab=setTab;
setTab=function(tab){
  historyControls.hidden=tab!=='history';
  if(tab!=='history')return historySetTab(tab);
  state.tab=tab;state.page=1;
  document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));
  for(const id of ['match-controls','combo-controls','insights-controls'])$(id).hidden=true;
  document.querySelector('.hero').hidden=true;
  $('section-title').textContent='Prediction History';$('section-eyebrow').textContent='SAVED BEFORE KICKOFF';$('crumb').textContent='PREDICTION HISTORY';
  renderHistory().catch(e=>notice(e.message,true));
};
const historyRenderCombos=renderCombos;
renderCombos=async function(){if(state.tab==='history')return renderHistory();return historyRenderCombos();};
let historyRequest=0;
async function renderHistory(){
  const request=++historyRequest;
  const data=await api('/api/prediction-history?'+new URLSearchParams({...params(),mode:$('history-mode').value,page:state.page}));
  if(state.tab!=='history'||request!==historyRequest)return;
  $('results').className='insights-list';$('result-count').textContent=`${data.total} predictions saved on ${$('date').value}`;
  $('result-context').textContent='First saved prediction preserved';
  const summary=['2','3'].map(target=>{const s=data.summary[target];return `<article><span>${target}× · SELECTED DATE</span><strong>${s.win_rate===null?'Awaiting results':pct(s.win_rate)}</strong><small>${s.generated} saved · ${s.won} wins · ${s.lost} losses · ${s.pending} pending<br>${s.partial} partial/push · ${s.void} refunds</small></article>`;}).join('');
  $('results').innerHTML=`<div class="performance-cards">${summary}</div>`+(data.items.length?data.items.map(c=>`<article class="combo-card"><div class="combo-top"><strong>${c.target}× · ${c.total_odds.toFixed(2)} odds</strong><span class="badge ${c.outcome==='won'?'ready':'warning'}">${esc(c.outcome.toUpperCase())}</span></div><div class="combo-legs">${c.legs.map(l=>`<div class="combo-leg"><b>${esc(l.fixture)}</b><p>${esc(l.market_key.replaceAll('_',' '))} · ${esc(l.selection)}${l.line===null?'':' · Line '+esc(l.line)} · ${l.odds.toFixed(2)} · ${esc(l.bookmaker)}</p></div>`).join('')}</div><div class="combo-foot">Saved ${esc(new Date(c.created_at).toLocaleString())} · ${esc(c.mode)}<br>Recorded probability: ${c.joint_probability===null?(c.mode==='historical'?'Not assigned — historical records only':'Unavailable'):pct(c.joint_probability)} · Unit return: ${c.payout===null?'Pending':(c.payout-1).toFixed(2)}<br>Selection version: ${esc(c.model_version||'Not applicable')}</div></article>`).join(''):empty('No predictions saved on this date','Choose another date or cohort. Predictions are recorded when generated; old cards are not reconstructed after results are known.'));
  paginate(data.total,data.size);
}
$('history-mode').addEventListener('change',()=>{state.page=1;renderHistory().catch(e=>notice(e.message,true));});
$('history-refresh').addEventListener('click',()=>run('results'));

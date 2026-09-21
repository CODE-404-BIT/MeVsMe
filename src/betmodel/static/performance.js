// Counts represent frozen generated combinations, never bets placed by the user.
const dayBasis=document.createElement('select');dayBasis.id='day-basis';dayBasis.setAttribute('aria-label','Match day timezone');
dayBasis.innerHTML='<option value="local">Local calendar day</option><option value="utc">UTC football date</option>';
document.querySelector('.date-box').append(dayBasis);
dayBasis.addEventListener('change',async()=>{state.page=1;try{await loadSaved();if(state.tab!=='matches')await renderCombos();}catch(e){notice(e.message,true);}});
const performanceStyle=document.createElement('link');
performanceStyle.rel='stylesheet';performanceStyle.href='/performance.css';document.head.append(performanceStyle);
const performancePanel=document.createElement('section');
performancePanel.className='performance-panel';performancePanel.setAttribute('aria-label','Prediction performance');
performancePanel.innerHTML=`<div class="performance-heading"><div><span class="eyebrow">LIVE TRACK RECORD</span><small>All-time generated combinations · tracking starts now</small></div><select id="performance-mode" aria-label="Performance cohort"><option value="historical">Historical suggestions</option><option value="model">Model estimates</option><option value="odds-only">Odds-only</option></select></div><div id="performance-cards" class="performance-cards" aria-live="polite"></div><details class="performance-details"><summary>Results, accuracy & model learning</summary><p>Counts are unique combinations saved before kickoff, not bets placed. Reloading or changing prices does not rewrite the first prediction. 2× / 3× refers to target combined odds, not the number of legs.</p><p>Win rate = full wins ÷ (full wins + full losses). Pushes, refunds and partial settlements are shown separately. Return assumes one unit per saved combination; overlapping combinations are correlated. Brier measures probability error; lower is better. Historical tests are separate from this live record.</p><div id="performance-breakdown"></div><div class="performance-actions"><button id="refresh-results" class="secondary">Refresh results</button><button id="update-model" class="secondary">Evaluate model update</button></div><div id="learning-status"></div></details>`;
document.querySelector('.page-head').append(performancePanel);
let performanceData=null;
let performanceRequest=0;
function drawPerformance(data){
  performanceData=data;
  const mode=$('performance-mode').value;
  const groups=data.cohorts[mode];
  const overallWins=groups['2'].won+groups['3'].won,overallLosses=groups['2'].lost+groups['3'].lost;
  document.querySelector('.performance-heading small').textContent=overallWins+overallLosses?`Overall win rate: ${pct(overallWins/(overallWins+overallLosses))} · ${overallWins} wins / ${overallWins+overallLosses} full outcomes`:'Overall win rate: awaiting results · all dates';
  $('performance-cards').innerHTML=['2','3'].map(target=>{
    const c=groups[target];
    if(mode==='odds-only')return `<article><span>${target}× ODDS-ONLY · LEGACY ARCHIVE</span><strong>0 <small>current-policy bets</small></strong><b>Not used for current recommendations</b><small>${c.generated.toLocaleString()} archived records · ${c.settled} settled</small></article>`;
    return `<article><span>${target}× ${mode==='historical'?'HISTORICAL SUGGESTIONS':'MODEL ARCHIVE'}</span><strong>${c.generated.toLocaleString()} <small>saved combinations</small></strong><b>${c.win_rate!==null?pct(c.win_rate)+' full-outcome win rate':c.generated?'Awaiting results':'No combinations saved yet'}</b><small>${c.settled} settled · ${c.pending} pending</small></article>`;
  }).join('');
  $('performance-breakdown').innerHTML=['2','3'].map(target=>{
    const c=groups[target];
    return `<p><b>${target}×</b> ${c.won} full wins · ${c.lost} full losses · ${c.partial} partial/push · ${c.void} refunds<br>Unit-stake return: ${c.roi===null?'awaiting results':pct(c.roi)} · Probability Brier: ${c.brier===null?'unavailable':c.brier.toFixed(3)} (${c.brier_sample_size} scored)</p>`;
  }).join('');
  const learning=data.learning;
  $('learning-status').innerHTML=`<b>Measured model learning</b><p>${esc(learning.explanation||'No update evaluated yet.')}</p><p>${learning.champions??0} active competition models · ${learning.promoted??0} accepted updates</p>${(learning.competitions||[]).map(c=>`<p><b>${esc(c.competition)}</b> · ${esc(c.status||'')}<br>${esc(c.reason||'')}<br><small>${esc(c.version||'')}</small></p>`).join('')}`;
}
async function refreshPerformance(){
  const request=++performanceRequest;
  const data=await api('/api/performance');
  if(request===performanceRequest)drawPerformance(data);
}
$('performance-mode').addEventListener('change',()=>{if(performanceData)drawPerformance(performanceData);});
modeSelect.addEventListener('change',()=>{$('performance-mode').value=modeSelect.value==='model'?'historical':modeSelect.value;if(performanceData)drawPerformance(performanceData);});
$('analyze').addEventListener('click',()=>{$('performance-mode').value='historical';if(performanceData)drawPerformance(performanceData);});
const performanceRefreshStatus=refreshStatus;
refreshStatus=async function(){
  const data=await performanceRefreshStatus();
  $('refresh-results').disabled=state.busy;$('update-model').disabled=state.busy;
  if(!state.busy)await refreshPerformance();
  return data;
};
$('refresh-results').addEventListener('click',()=>run('results'));
$('update-model').addEventListener('click',()=>run('learn'));
refreshPerformance().catch(()=>{$('performance-cards').textContent='Performance unavailable. Restart the dashboard to load the update.';});
// The timer checks due saved fixtures only, and respects the server's quota reserve.
setInterval(()=>{if(!state.busy&&state.status?.key_configured)run('results');},30*60*1000);

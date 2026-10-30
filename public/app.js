const $ = (id) => document.getElementById(id);
const state = { mode: 'create', room: null, player: null, data: null, lastRound: null, ordersKey: null };
const savedSession = JSON.parse(localStorage.getItem('insider-session') || 'null');
const inviteRoom = new URLSearchParams(location.search).get('room');

function fmtMoney(n){return new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(n||0)}
function fmtPct(n){return `${n>=0?'+':''}${Number(n).toFixed(2)}%`}
async function api(path, body){
  const r = await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d = await r.json(); if(!r.ok) throw new Error(d.error||'Request failed'); return d;
}
function setError(msg=''){ $('landingError').textContent=msg }

document.querySelectorAll('.tab').forEach(btn=>btn.addEventListener('click',()=>{
  document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active')); btn.classList.add('active');
  state.mode=btn.dataset.mode; $('joinRow').classList.toggle('hidden',state.mode!=='join'); $('difficultyRow').classList.toggle('hidden',state.mode==='join'); $('mainLobbyBtn').textContent=state.mode==='create'?'Create room':'Join room'; setError('');
}));

$('mainLobbyBtn').onclick=async()=>{
  setError(''); const name=$('nameInput').value.trim();
  if(!name){setError('Enter your name.');return}
  try{
    const d=state.mode==='create'?await api('/api/create',{name,difficulty:$('difficultyInput').value}):await api('/api/join',{name,room:$('roomInput').value.trim()});
    state.room=d.room; state.player=d.player; localStorage.setItem('insider-session',JSON.stringify({room:d.room,player:d.player})); $('landing').classList.remove('active'); $('game').classList.add('active'); $('roomCodeLabel').textContent=state.room; startPolling();
  }catch(e){setError(e.message)}
};

async function postAction(action, extra={}){
  try{await api('/api/action',{room:state.room,player:state.player,action,...extra}); await poll();}catch(e){alert(e.message)}
}
async function poll(){
  if(!state.room)return; try{const r=await fetch(`/api/state?room=${encodeURIComponent(state.room)}&player=${encodeURIComponent(state.player)}`); if(r.status===404){goHome();setError('That room ended when the server restarted. Create a new room.');return} if(!r.ok) return; const d=await r.json(); render(d)}catch{}
}
let pollingStarted=false;
function startPolling(){poll(); if(!pollingStarted){pollingStarted=true;setInterval(poll,1000)}}

function render(d){
  state.data=d; $('dayLabel').textContent=d.status==='lobby'?'LOBBY':`DAY ${d.round}/${d.total_rounds}`;
  if(d.status==='round') $('timer').textContent=timeFmt(d.seconds_remaining); else $('timer').textContent=d.status==='finished'?'CLOSED':'--:--';
  renderRole(d); renderPortfolio(d); renderPlayers(d); renderFeed(d);
  if(d.status==='lobby'){ $('lobbyPanel').classList.remove('hidden'); $('marketPanel').classList.add('hidden'); renderLobby(d); return; }
  $('lobbyPanel').classList.add('hidden'); $('marketPanel').classList.remove('hidden');
  renderNews(d); renderStocks(d); renderOrders(d); renderRegulator(d); renderBetween(d); renderFinished(d);
}
function timeFmt(sec){const s=Math.ceil(sec);return `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`}
function roleClass(role){return role==='INSIDER'?'insider':role==='REGULATOR'?'regulator':'trader'}
function renderRole(d){
  const r=d.me.role; if(!r){$('roleCard').innerHTML='<div class="section-label">YOUR ROLE</div><div class="role-title">Waiting room</div><div class="role-note">The host starts the market once everyone is ready.</div>';return}
  const title={INSIDER:'INSIDER',REGULATOR:'REGULATOR',TRADER:'TRADER'}[r];
  const note=r==='INSIDER'?'You see tomorrow’s headline one day early. Make money without becoming obvious.':r==='REGULATOR'?'You are the SEC. You get one accusation during the game. Correct = +$3,000; wrong = -$2,000.':'No secret information. Read the news, the market, and other players.';
  $('roleCard').innerHTML=`<div class="section-label">YOUR ROLE</div><div style="margin:7px 0"><span class="role-badge ${roleClass(r)}">${title}</span></div><div class="role-title">${r==='INSIDER'?'Information is your edge.':r==='REGULATOR'?'Follow the money.':'Beat the market.'}</div><div class="role-note">${note}</div>`;
}
function renderPortfolio(d){
  const p=d.me; $('portfolioValue').textContent=fmtMoney(p.portfolio); $('cashValue').textContent=fmtMoney(p.cash);
  let long=0,short=0; for(const s of Object.keys(d.stocks)){long+=p.holdings[s]*d.prices[s];short+=p.shorts[s]*d.prices[s]}
  $('longValue').textContent=fmtMoney(long); $('shortValue').textContent=fmtMoney(short);
  const base=(p.history&&p.history[0])||10000; const change=(p.portfolio/base-1)*100; const el=$('portfolioDelta'); el.textContent=fmtPct(change); el.className='delta '+(change>0.005?'up':change<-0.005?'down':'flat');
}
function renderPlayers(d){$('playerCount').textContent=`${d.players.length}/8`; $('playersList').innerHTML=d.players.map(p=>`<div class="player-row"><span class="dot"></span><span class="player-name ${p.id===d.me.id?'you':''}">${escapeHtml(p.name)}${p.id===d.me.id?' · YOU':''}${p.caught?' · CAUGHT':''}</span><span class="player-val ${p.caught?'caught':''}">${fmtMoney(p.portfolio)}</span></div>`).join('')}
function renderFeed(d){$('feed').innerHTML=d.feed.map(x=>`<div class="feed-item ${x.type==='alert'?'alert':x.type==='resolution'?'resolution':''}">${escapeHtml(x.text)}</div>`).join('')||'<div class="feed-item">No events yet.</div>'}
function renderLobby(d){
  const isHost=d.me.id===d.host_id;
  $('lobbyPanel').innerHTML=`<div class="section-label">PRIVATE MARKET · ${escapeHtml(d.difficulty.toUpperCase())}</div><div class="lobby-title">Room <span>${d.room}</span></div><div class="room-code-large">${d.room}</div><div class="lobby-copy">Send this code or an invite link to your friends. They can join from their own devices. The host starts at 3–8 players.</div><button class="primary" onclick="copyInvite('${d.room}')">Copy invite link</button><div class="player-pills">${d.players.map((p,i)=>`<div class="pill">${escapeHtml(p.name)} ${p.id===d.host_id?'<span class="host-tag">HOST</span>':''}</div>`).join('')}</div>${isHost?`<button class="primary" ${d.players.length>=3?'':'disabled'} onclick="postAction('start')">${d.players.length<3?'Need 3 players':'Start market'}</button>`:'<div class="lobby-copy">Waiting for the host to start…</div>'}`;
}
function renderNews(d){
  $('newsDay').textContent=d.round; $('newsTitle').textContent=d.news?.title||'Market opens.'; $('newsText').textContent=d.news?.text||'';
  const box=$('insiderIntel'); if(d.me.role==='INSIDER'&&d.next_news_for_me){box.classList.remove('hidden');box.textContent=`PRIVATE INTEL · TOMORROW: ${d.next_news_for_me.title}`;} else box.classList.add('hidden');
}
function renderStocks(d){
  $('marketGrid').innerHTML=Object.entries(d.stocks).map(([s,st])=>{const px=d.prices[s], prev=d.previous_prices[s], pct=prev?((px/prev)-1)*100:0; return `<div class="stock-card"><div class="stock-head"><div><div class="ticker">${st.icon} ${st.ticker}</div><div class="stock-name">${st.name}</div></div><div class="pct ${pct>0.01?'up':pct<-0.01?'down':'flat'}">${fmtPct(pct)}</div></div><div class="stock-price">${fmtMoney(px)}</div><div class="price">Last close ${fmtMoney(prev)}</div></div>`}).join('')
}
function renderOrders(d){
  const key=JSON.stringify([d.status,d.round,d.me.orders,d.prices]);
  if (state.ordersKey===key) return;
  state.ordersKey=key;
  const rows=Object.entries(d.stocks).map(([s,st])=>{const o=d.me.orders[s]||{side:'BUY',qty:0}; return `<div class="order-ticket"><div><div class="name">${st.icon} ${st.ticker} <span class="stock-name">${st.name}</span></div><div class="price">${fmtMoney(d.prices[s])} · Long ${d.me.holdings[s]} · Short ${d.me.shorts[s]}</div></div><select class="select" id="side-${s}"><option ${o.side==='BUY'?'selected':''}>BUY</option><option ${o.side==='SELL'?'selected':''}>SELL</option><option ${o.side==='SHORT'?'selected':''}>SHORT</option><option ${o.side==='COVER'?'selected':''}>COVER</option></select><input class="qty" id="qty-${s}" type="number" min="0" step="1" value="${o.qty||''}" placeholder="Qty"/><button class="save-order ${o.qty?'saved':''}" onclick="saveOrder('${s}')">${o.qty?'Saved':'Set'}</button></div>`}).join('');
  $('ordersList').innerHTML=rows; $('ordersStatus').textContent=d.me.order_submitted?'Orders queued for close':'No orders';
}
function saveOrder(s){postAction('order',{symbol:s,side:$(`side-${s}`).value,qty:Number($(`qty-${s}`).value||0)})}
function renderRegulator(d){
  const panel=$('regulatorPanel'); if(d.me.role!=='REGULATOR'||d.status==='finished'){panel.classList.add('hidden');return} panel.classList.remove('hidden');
  const locked=d.round<4 || d.status!=='between';
  panel.innerHTML=`<div class="section-label">SEC WINDOW</div><h3>${d.regulator_used?'Investigation used':locked?'Investigation opens after Day 4':'Who looks suspicious?'}</h3><div class="regulator-copy">${locked?'Watch the market for now. Your one accusation unlocks after Day 4 closes.':'Use your one accusation to identify the player you believe is the Insider. Trading behavior is your evidence.'}</div><div class="accuse-grid">${d.players.filter(p=>p.id!==d.me.id).map(p=>`<button class="accuse-btn" ${d.regulator_used||locked?'disabled':''} onclick="postAction('accuse',{target:'${p.id}'})"><strong>${escapeHtml(p.name)}</strong><small>${fmtMoney(p.portfolio)}</small></button>`).join('')}</div>`;
}
function renderBetween(d){
  const panel=$('betweenPanel'); if(d.status!=='between'){panel.classList.add('hidden');return} panel.classList.remove('hidden');
  const r=d.resolution; const changes=Object.entries(r.price_changes).map(([s,v])=>`<div class="change-box"><span>${d.stocks[s].ticker}</span><strong class="${v>=0?'up':'down'}">${fmtPct(v)}</strong></div>`).join('');
  panel.innerHTML=`<div class="section-label">DAY ${d.round} CLOSED</div><h3>Orders resolved together.</h3><div class="regulator-copy">${escapeHtml(r.news)} · Current leader: <strong>${escapeHtml(r.leader)}</strong></div><div class="price-change">${changes}</div><div class="regulator-copy">Next stage begins automatically in ${Math.ceil(d.seconds_remaining)} seconds.</div>${d.me.id===d.host_id?`<button class="primary next-btn" onclick="postAction('next_round')">${d.round>=d.total_rounds?'See final results':'Start next day'}</button>`:''}`;
}
function renderFinished(d){
  const panel=$('finishedPanel'); if(d.status!=='finished'){panel.classList.add('hidden');return} panel.classList.remove('hidden');
  const sorted=[...d.players].sort((a,b)=>b.portfolio-a.portfolio); const winner=sorted[0];
  const roles=sorted.map((p,i)=>`<div class="rank"><div class="n">#${i+1}</div><div>${escapeHtml(p.name)} ${p.id===d.me.id?'<small>(you)</small>':''}<div class="subtle">${p.role}${p.caught?' · CAUGHT':''}</div></div><div class="v">${fmtMoney(p.portfolio)}</div></div>`).join('');
  const me=d.me; let chart=''; if(me.history&&me.history.length){chart=drawChart(me.history)}
  panel.innerHTML=`<div class="section-label">FINAL BELL</div><h3>The market is closed.</h3><div class="winner"><span>${escapeHtml(winner.name)}</span> wins with ${fmtMoney(winner.portfolio)}</div><div class="rankings">${roles}</div><button class="primary" onclick="goHome()">Back to homepage</button><div class="reveal"><div class="section-label">YOUR PORTFOLIO PATH</div>${chart}<div class="moment">${me.big_moment?`Biggest swing: Day ${me.big_moment.round}, ${me.big_moment.delta>=0?'+':''}${fmtMoney(me.big_moment.delta)} · ${escapeHtml(me.big_moment.news)}`:'No major swing recorded.'}</div></div>`;
}
function drawChart(values){
  const w=720,h=170,p=18; const min=Math.min(...values),max=Math.max(...values),range=Math.max(1,max-min); const pts=values.map((v,i)=>{const x=p+(w-p*2)*(i/(values.length-1||1));const y=h-p-(v-min)/range*(h-p*2);return `${x},${y}`}).join(' '); const circles=values.map((v,i)=>{const x=p+(w-p*2)*(i/(values.length-1||1));const y=h-p-(v-min)/range*(h-p*2);return `<circle cx="${x}" cy="${y}" r="4"/>`}).join(''); return `<svg class="chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><line x1="${p}" y1="${h-p}" x2="${w-p}" y2="${h-p}" stroke="#23303a"/><polyline points="${pts}" fill="none" stroke="#d8ff5f" stroke-width="3"/>${circles}</svg>`;
}
function escapeHtml(v){return String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}

function copyInvite(room){navigator.clipboard.writeText(location.origin+'/?room='+room).then(()=>alert('Invite link copied')).catch(()=>alert('Share this page address and room code: '+room))}
if(inviteRoom){document.querySelector('[data-mode="join"]').click();$('roomInput').value=inviteRoom.toUpperCase()}
if(savedSession?.room&&savedSession?.player){state.room=savedSession.room;state.player=savedSession.player;$('landing').classList.remove('active');$('game').classList.add('active');$('roomCodeLabel').textContent=state.room;startPolling()}

function goHome(){localStorage.removeItem('insider-session');state.room=null;state.player=null;state.data=null;state.ordersKey=null;history.replaceState(null,'',location.pathname);$('game').classList.remove('active');$('landing').classList.add('active');$('nameInput').value=''}

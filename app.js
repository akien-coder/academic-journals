'use strict';
const CREDENTIALS={settings:'rpw_sync_settings_v1',rememberedToken:'rpw_sync_device_token_v1',sessionToken:'rpw_sync_session_token_v1'};
const state={papers:[],archive:{},journals:[],status:null,view:'new',visible:50,search:'',journal:'',range:'',sort:'added',saved:new Set(),ack:'1970-01-01T00:00:00Z'};
const sync={gateway:null,connected:false,busy:false,message:'未接続',error:false};
function load(k,fallback){try{const x=localStorage.getItem(k);return x?JSON.parse(x):fallback}catch{return fallback}}
function store(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch{}}
const $=id=>document.getElementById(id);
function validUrl(s){try{const u=new URL(s);return /^https?:$/.test(u.protocol)?u.href:''}catch{return ''}}
function formatDate(s){if(!s)return '日付未登録';return s.slice(0,10).replaceAll('-','/').replace(/\/$/,'')}
function str(s){return String(s||'')}
function asDate(s){if(!s)return 0;const fixed=s.length===4?s+'-01-01':s.length===7?s+'-01':s;return Date.parse(fixed)||0}
function isNew(p){return asDate(p.first_seen)>asDate(state.ack)}
function truncateAuthors(list){const arr=(list||[]).filter(Boolean);return arr.slice(0,4).join(', ')+(arr.length>4?' ほか':'')}
function el(tag,className,text){const o=document.createElement(tag);if(className)o.className=className;if(text!==undefined)o.textContent=text;return o}
function badge(text,kind){return el('span','badge '+(kind||''),text)}
function link(text,url,cls){const a=el('a',cls||'',text);a.href=validUrl(url)||'#';a.target='_blank';a.rel='noopener noreferrer';return a}
function paperItem(p){
 const card=el('article','paper'),body=el('div','paper-main'),top=el('div','paper-top');
 if(isNew(p))top.append(badge('NEW','new'));
 if(p.kind==='working-paper')top.append(badge('WORKING PAPER','wp'));
 top.append(el('span','',formatDate(p.published)));
 body.append(top,link(p.title,p.url,'title-link'));
 const meta=el('div','paper-meta');const j=el('strong','',p.journal||'掲載媒体不明');meta.append(j);
 const bits=[truncateAuthors(p.authors),p.volume?`Vol. ${p.volume}`:'',p.issue?`No. ${p.issue}`:''].filter(Boolean);
 if(bits.length)meta.append(document.createTextNode(' · '+bits.join(' · ')));
 if(p.doi){meta.append(document.createTextNode(' · '));meta.append(link('DOI',`https://doi.org/${p.doi}`));}
 if(validUrl(p.oa_url)){meta.append(document.createTextNode(' · '));meta.append(link('OA版',p.oa_url));}
 body.append(meta);
 if(p.summary_ja){const sum=el('p','summary-ja',p.summary_ja);body.append(sum);}
 else{body.append(el('p','summary-unavailable','日本語要約なし（抄録未取得・未処理）'));}
 const star=el('button','star',state.saved.has(p.id)?'★':'☆');star.type='button';star.title=state.saved.has(p.id)?'一時保存を解除':'あとで見るために一時保存';star.setAttribute('aria-label',star.title);star.setAttribute('aria-pressed',String(state.saved.has(p.id)));
 star.disabled=sync.busy;
 star.addEventListener('click',()=>{
  if(!sync.connected){$('sync-panel').hidden=false;showSyncMessage('先にGitHubの同期設定を行ってください。',true);$('sync-toggle').scrollIntoView({behavior:'smooth',block:'center'});return;}
  writeChange({type:'bookmark',id:p.id,saved:!state.saved.has(p.id),paper:{title:p.title,journal:p.journal,url:p.url,doi:p.doi||'',published:p.published||'',first_seen:p.first_seen||'',authors:p.authors||[],journal_id:p.journal_id||'',tags:p.tags||[],kind:p.kind||'article'}});
 });
 card.append(body,star);return card;
}
function selectedPapers(){
 const available=[...state.papers];
 if(state.view==='saved')for(const id of state.saved){
   if(!available.some(p=>p.id===id)&&state.archive[id])available.push({id,...state.archive[id]});
 }
 let list=available.filter(p=>{
  if(state.view==='new'&&!isNew(p))return false;
  if(state.view==='saved'&&!state.saved.has(p.id))return false;
  if(state.journal&&p.journal_id!==state.journal)return false;
  if(state.range&&asDate(p.first_seen)<Date.now()-Number(state.range)*864e5)return false;
  if(state.search){const hay=[p.title,p.journal,...(p.authors||[]),p.doi].join(' ').toLocaleLowerCase();if(!hay.includes(state.search))return false;}
  return true;
 });
 list.sort((a,b)=>state.sort==='published'?asDate(b.published)-asDate(a.published):state.sort==='title'?a.title.localeCompare(b.title):asDate(b.first_seen)-asDate(a.first_seen));
 return list;
}
function showIssues(list){
 const groups=new Map();
 for(const p of list){if(!p.volume&&!p.issue)continue;const k=[p.journal_id||p.journal,p.volume,p.issue].join('|');if(!groups.has(k))groups.set(k,{journal:p.journal,vol:p.volume,issue:p.issue,papers:[],home:state.journals.find(j=>j.id===p.journal_id)?.home});groups.get(k).papers.push(p);}
 const wrapper=$('papers');const arr=[...groups.values()].sort((a,b)=>Math.max(...b.papers.map(p=>asDate(p.published)))-Math.max(...a.papers.map(p=>asDate(p.published))));
 $('result-count').textContent=`${arr.length} 巻号（収録データに基づく）`;
 for(const g of arr.slice(0,state.visible)){
  const section=el('section','issue-card');const top=el('div');top.append(el('strong','',g.journal+' · '+[g.vol?`Vol. ${g.vol}`:'',g.issue?`No. ${g.issue}`:''].filter(Boolean).join(' / ')));
  const p=el('p','',`取得済みの論文 ${g.papers.length}件　`);if(g.home)p.append(link('雑誌サイト ↗',g.home));
  const items=el('div');for(const work of g.papers.slice(0,4)){const line=el('div');line.append(link(work.title,work.url));items.append(line)};
  section.append(top,p,items);wrapper.append(section);
 }
 $('more').hidden=arr.length<=state.visible;
 if(!arr.length)showEmpty('巻号情報のある論文が見つかりません。','巻号は取得できたメタデータからまとめており、正式な最新号の完全な目次を保証するものではありません。');
}
function showEmpty(title,detail){const empty=$('empty');empty.hidden=false;empty.replaceChildren(el('strong','',title),el('span','',detail||''));}
function render(){
 const total=state.papers.length,unseen=state.papers.filter(isNew).length,saved=state.saved.size;
 $('total').textContent=total.toLocaleString('ja-JP');$('new-total').textContent=unseen.toLocaleString('ja-JP');$('saved-total').textContent=saved.toLocaleString('ja-JP');$('new-label').textContent=unseen?'('+unseen+')':'';
 const labels={new:'新着論文',all:'すべての論文',saved:'保存済み',issues:'巻号別'};
 $('list-title').textContent=labels[state.view];document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.dataset.view===state.view));
 $('confirm').hidden=state.view!=='new'||!unseen; $('confirm').disabled=sync.busy;
 $('papers').replaceChildren();$('empty').hidden=true;const list=selectedPapers();
 if(state.view==='issues'){showIssues(list);return}
 $('result-count').textContent=`${list.length.toLocaleString('ja-JP')}件`;
 for(const p of list.slice(0,state.visible))$('papers').append(paperItem(p));
 $('more').hidden=list.length<=state.visible;
 if(!list.length)showEmpty(total?'該当する論文はありません':'まだ論文データがありません',total?'検索条件を変えるか「すべて」で確認してください。':'初回はGitHub Actionsの「Collect research papers」を手動実行してください。');
}
function makeOptions(select,rows){for(const p of rows){const op=el('option','',p.title||p.label);op.value=p.id;select.append(op);}}
async function init(){
 try{
  const [papers,journals,status]=await Promise.all(['data/papers.json','config/journals.json','data/status.json'].map(async name=>{const res=await fetch(name+'?v='+Date.now(),{cache:'no-store'});if(!res.ok)throw new Error(name+' HTTP '+res.status);return res.json()}));
  state.papers=Array.isArray(papers)?papers:[];state.journals=journals;state.status=status;
  makeOptions($('journal'),journals);
  if(status.updated_at){$('update').textContent='最終収集 '+new Date(status.updated_at).toLocaleString('ja-JP',{timeZone:'Asia/Tokyo',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'});}else $('update').textContent='初回収集前';
  const problems=Object.entries(status.sources||{}).filter(([,v])=>!v.ok);
  if(problems.length){$('notice').hidden=false;$('notice').textContent=`注意：${problems.length}件の取得先でエラーがあります。前回までの論文データは保持しています。詳細は data/status.json を確認してください。`;}
  render();
 }catch(err){$('update').textContent='読込エラー';showEmpty('サイトデータを読み込めません',str(err)+'。ローカルでは python -m http.server 8000 で起動してください。');}
}
document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click',()=>{state.view=b.dataset.view;state.visible=50;render()}));
for(const [id,key] of [['search','search'],['journal','journal'],['range','range'],['sort','sort']])$(id).addEventListener('input',e=>{state[key]=str(e.target.value).toLocaleLowerCase();state.visible=50;render()});
$('more').addEventListener('click',()=>{state.visible+=50;render()});
// The GitHub repository is the sole source of truth for bookmarks and acknowledgements.
// Local storage contains only optional device credentials, never paper state.
function applyRemote(data){
 const normalized=RpwSync.normalize(data);
 state.saved=new Set(Object.keys(normalized.bookmarks));
 state.archive=Object.fromEntries(Object.entries(normalized.bookmarks).filter(([,v])=>v&&typeof v==='object'));
 state.ack=normalized.confirmed_at;
 render();
}
function showSyncMessage(message,error=false){
 sync.message=message;sync.error=error;
 $('sync-status').textContent='同期：'+message;
 $('sync-detail').textContent=error?'GitHubへの保存は完了していません。接続・権限を確認してください。':(sync.connected?'★保存と確認状態は複数端末で共有されます。':'★保存・新着確認には接続が必要です。');
 document.querySelector('.syncbar').classList.toggle('error',error);
 $('sync-refresh').hidden=!sync.connected;
 $('sync-connect').disabled=sync.busy;
 $('sync-refresh').disabled=sync.busy;
 $('sync-disconnect').disabled=sync.busy;
}
function setSyncBusy(busy){sync.busy=busy;showSyncMessage(sync.message,sync.error);render();}
function savedSettings(){return load(CREDENTIALS.settings,{owner:'',repo:'',remember:false});}
function getSavedToken(){
 try{return sessionStorage.getItem(CREDENTIALS.sessionToken)||localStorage.getItem(CREDENTIALS.rememberedToken)||'';}catch{return ''}
}
function persistCredentials({owner,repo,token,remember}){
 store(CREDENTIALS.settings,{owner,repo,remember});
 try{
  sessionStorage.removeItem(CREDENTIALS.sessionToken);localStorage.removeItem(CREDENTIALS.rememberedToken);
  (remember?localStorage:sessionStorage).setItem(remember?CREDENTIALS.rememberedToken:CREDENTIALS.sessionToken,token);
 }catch{showSyncMessage('接続済み（認証情報の保存不可）',true)}
}
function forgetCredentials(){
 try{localStorage.removeItem(CREDENTIALS.settings);localStorage.removeItem(CREDENTIALS.rememberedToken);sessionStorage.removeItem(CREDENTIALS.sessionToken);}catch{}
}
async function connect({owner,repo,token,remember},automatic=false){
 if(sync.busy)return;
 setSyncBusy(true);showSyncMessage('接続中…');
 try{
  const gateway=RpwSync.createGateway({owner,repo,token});
  await gateway.verifyPrivate();
  const remote=await gateway.read();
  sync.gateway=gateway;sync.connected=true;applyRemote(remote.data);
  persistCredentials({owner,repo,token,remember});
  $('sync-token').value='';$('sync-panel').hidden=true;
  showSyncMessage('同期済み');
 }catch(err){
  sync.gateway=null;sync.connected=false;showSyncMessage(err.message||'接続に失敗しました。',true);
  $('sync-panel').hidden=false;
  if(!automatic)$('sync-token').value='';
 }finally{setSyncBusy(false)}
}
async function refreshRemote(){
 if(!sync.connected||sync.busy)return;
 setSyncBusy(true);showSyncMessage('同期中…');
 try{
  const remote=await sync.gateway.read();applyRemote(remote.data);
  showSyncMessage('同期済み');
 }catch(err){showSyncMessage('同期失敗：'+(err.message||'再試行してください。'),true)}
 finally{setSyncBusy(false)}
}
async function writeChange(change){
 if(!sync.connected||sync.busy)return;
 setSyncBusy(true);showSyncMessage('保存中…');
 try{
  const remote=await sync.gateway.mutate(change);
  applyRemote(remote);
  showSyncMessage('同期済み');
 }catch(err){
  showSyncMessage('保存失敗：'+(err.message||'もう一度操作してください。'),true);
  // The browser must not silently claim a change succeeded if GitHub rejected it.
  try{const remote=await sync.gateway.read();applyRemote(remote.data)}catch{}
 }finally{setSyncBusy(false)}
}
$('sync-toggle').addEventListener('click',()=>{$('sync-panel').hidden=!$('sync-panel').hidden});
$('sync-refresh').addEventListener('click',refreshRemote);
$('sync-form').addEventListener('submit',async e=>{
 e.preventDefault();
 await connect({owner:$('sync-owner').value.trim(),repo:$('sync-repo').value.trim(),token:$('sync-token').value.trim(),remember:$('sync-remember').checked});
});
$('sync-disconnect').addEventListener('click',()=>{
 forgetCredentials();sync.gateway=null;sync.connected=false;sync.error=false;
 state.saved=new Set();state.archive={};state.ack='1970-01-01T00:00:00Z';
 $('sync-token').value='';$('sync-remember').checked=false;
 showSyncMessage('未接続');render();
});
$('confirm').addEventListener('click',()=>{
 if(!sync.connected){$('sync-panel').hidden=false;showSyncMessage('先にGitHubの同期設定を行ってください。',true);return}
 if(!confirm('今回取得済みの新着をまとめて確認済みにします。よろしいですか？'))return;
 // Confirm the snapshot currently on the screen, not the time on the clock.
 // Papers arriving after this snapshot remain NEW, even if publication dates are old.
 const latest=Math.max(...state.papers.map(p=>asDate(p.first_seen)),0);
 if(latest)writeChange({type:'confirm',through:new Date(latest).toISOString()});
});
const prefs=savedSettings();
$('sync-owner').value=prefs.owner||'';$('sync-repo').value=prefs.repo||'';$('sync-remember').checked=!!prefs.remember;
showSyncMessage('未接続');
init();
if(prefs.owner&&prefs.repo&&getSavedToken())connect({...prefs,token:getSavedToken()},true);
// Re-read GitHub on tab return so changes made on another device appear.
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refreshRemote()});
window.addEventListener('focus',()=>{if(sync.connected)refreshRemote()});

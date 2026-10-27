'use strict';
/* GitHub Contents API adapter. No tokens are shipped in the website files. */
(function (root) {
  const EMPTY = '1970-01-01T00:00:00Z';
  const FILE = 'sync/state.json';
  function blank() { return {version:1, bookmarks:{}, confirmed_at:EMPTY, updated_at:''}; }
  function normalize(input) {
    if (!input || typeof input !== 'object' || Array.isArray(input)) return blank();
    const bookmarks={};
    if (input.bookmarks && typeof input.bookmarks==='object' && !Array.isArray(input.bookmarks)) {
      for (const [k,v] of Object.entries(input.bookmarks)) {
        if(k && v===true)bookmarks[k]=true;
        else if(k && v && typeof v==='object' && typeof v.title==='string' && typeof v.url==='string') bookmarks[k]={title:v.title,journal:String(v.journal||''),url:v.url,doi:String(v.doi||''),published:String(v.published||''),first_seen:String(v.first_seen||''),authors:Array.isArray(v.authors)?v.authors.slice(0,10):[],journal_id:String(v.journal_id||''),tags:Array.isArray(v.tags)?v.tags.slice(0,10):[],kind:String(v.kind||'article')};
      }
    }
    const date = Date.parse(input.confirmed_at);
    return {version:1, bookmarks, confirmed_at:Number.isFinite(date)?new Date(date).toISOString():EMPTY, updated_at:typeof input.updated_at==='string'?input.updated_at:''};
  }
  function encode(text) {
    const bytes=new TextEncoder().encode(text);let binary='';
    for(let i=0;i<bytes.length;i+=8192) binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
    return btoa(binary);
  }
  function decode(text) {
    const bytes=Uint8Array.from(atob(text.replace(/\s/g,'')),c=>c.charCodeAt(0));
    return new TextDecoder().decode(bytes);
  }
  function validateSlug(input,label) {
    const str=String(input||'').trim();
    if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}$/.test(str)||str.includes('..')) throw new Error(label+'の指定を確認してください。');
    return str;
  }
  function createGateway({owner,repo,token,requestFetch}) {
    owner=validateSlug(owner,'GitHubユーザー名'); repo=validateSlug(repo,'非公開リポジトリ名');
    if (!token || typeof token!=='string') throw new Error('認証キーを入力してください。');
    const fetcher=requestFetch || fetch;
    const base=`https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`;
    const headers={Accept:'application/vnd.github+json',Authorization:`Bearer ${token}`,'X-GitHub-Api-Version':'2022-11-28'};
    async function request(url,options={}) {
      const res=await fetcher(url,{...options,headers:{...headers,...(options.headers||{})},cache:'no-store'});
      if(!res.ok) {
        const err=new Error(res.status===401?'認証キーが無効です。':res.status===403?'GitHubからアクセスが拒否されました。キーの権限や利用制限を確認してください。':res.status===404?'リポジトリまたはファイルにアクセスできません。名前と権限を確認してください。':`GitHubへのアクセスに失敗しました（HTTP ${res.status}）。`);
        err.status=res.status;throw err;
      }
      return res.json();
    }
    async function verifyPrivate() {
      const repoInfo=await request(base);
      if (repoInfo.private !== true) throw new Error('保存先は必ず Private（非公開）リポジトリを指定してください。');
      return true;
    }
    async function read() {
      try {
        const result=await request(base+'/contents/'+FILE+'?r='+Date.now());
        if(result.type!=='file'||result.encoding!=='base64') throw new Error('同期ファイルの形式が不正です。');
        return {data:normalize(JSON.parse(decode(result.content))),sha:result.sha};
      } catch(err) {
        if(err.status===404)return {data:blank(),sha:null};
        throw err;
      }
    }
    async function mutate(change) {
      for(let attempt=0;attempt<4;attempt++) {
        const {data,sha}=await read();
        const next=normalize(data);
        if(change.type==='bookmark') {
          if(typeof change.id!=='string'||!change.id)throw new Error('論文IDが不正です。');
          if(change.saved)next.bookmarks[change.id]=change.paper||true;else delete next.bookmarks[change.id];
        } else if(change.type==='confirm') {
          const stamp=Date.parse(change.through);
          if(!Number.isFinite(stamp))throw new Error('確認日時が不正です。');
          const latest=Math.max(stamp,Date.parse(next.confirmed_at)||0);
          next.confirmed_at=new Date(latest).toISOString();
        } else throw new Error('不正な更新種別です。');
        next.updated_at=new Date().toISOString();
        const payload={message:change.type==='confirm'?'Confirm new research papers':'Update saved research paper',content:encode(JSON.stringify(next,null,2)+'\n')};
        if(sha)payload.sha=sha;
        try {
          await request(base+'/contents/'+FILE,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
          return next;
        } catch(err) {
          if((err.status===409||err.status===422)&&attempt<3)continue;
          throw err;
        }
      }
      throw new Error('複数端末の更新が競合しました。もう一度操作してください。');
    }
    return {verifyPrivate,read,mutate};
  }
  const api={blank,normalize,encode,decode,createGateway};
  if (typeof module!=='undefined' && module.exports) module.exports=api;
  if (root)root.RpwSync=api;
})(typeof window!=='undefined'?window:null);

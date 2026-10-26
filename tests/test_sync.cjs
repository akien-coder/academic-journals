'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const R=require('../sync.js');
function mockGitHub(){
 let blob=null,sha=0,conflicts=0;
 const calls=[];
 function response(status,obj){return {ok:status>=200&&status<300,status,json:async()=>obj};}
 const fetcher=async (url,options={})=>{
  calls.push({url,method:options.method||'GET',headers:options.headers});
  assert.equal(options.headers.Authorization,'Bearer example-only-token');
  if(url.endsWith('/repos/researcher/private-watch'))return response(200,{private:true});
  if(url.includes('/contents/sync/state.json')){
   if(options.method==='PUT'){
    if(conflicts>0){conflicts--;return response(409,{});}
    const body=JSON.parse(options.body);
    if(blob && body.sha!==String(sha))return response(409,{});
    if(!blob && body.sha)return response(409,{});
    blob=JSON.parse(R.decode(body.content));sha++;
    return response(200,{content:{sha:String(sha)}});
   }
   if(!blob)return response(404,{});
   return response(200,{type:'file',encoding:'base64',content:R.encode(JSON.stringify(blob)),sha:String(sha)});
  }
  return response(404,{});
 };
 return {fetcher,calls,get blob(){return blob},conflictOnce(){conflicts++}};
}
test('private repository verification, unicode-safe state, and bookmark persistence', async()=>{
 const m=mockGitHub();const gateway=R.createGateway({owner:'researcher',repo:'private-watch',token:'example-only-token',requestFetch:m.fetcher});
 await gateway.verifyPrivate();
 assert.deepEqual((await gateway.read()).data.bookmarks,{});
 let updated=await gateway.mutate({type:'bookmark',id:'doi:10.1111/地理学',saved:true,paper:{title:'経済地理論文',url:'https://example.org/paper',journal:'経済地理学年報'}});
 assert.equal(updated.bookmarks['doi:10.1111/地理学'].title,'経済地理論文');
 assert.equal((await gateway.read()).data.bookmarks['doi:10.1111/地理学'].title,'経済地理論文');
 updated=await gateway.mutate({type:'bookmark',id:'doi:10.1111/地理学',saved:false});
 assert.deepEqual(updated.bookmarks,{});
});
test('ack time is monotonic and does not reset on stale device',async()=>{
 const m=mockGitHub(),g=R.createGateway({owner:'researcher',repo:'private-watch',token:'example-only-token',requestFetch:m.fetcher});
 await g.mutate({type:'confirm',through:'2026-10-24T10:12:14.000Z'});
 const later=await g.mutate({type:'confirm',through:'2026-10-23T12:00:00.000Z'});
 assert.equal(later.confirmed_at,'2026-10-24T10:12:14.000Z');
});
test('a conflicting write is retried with the newest version',async()=>{
 const m=mockGitHub(),g=R.createGateway({owner:'researcher',repo:'private-watch',token:'example-only-token',requestFetch:m.fetcher});
 await g.mutate({type:'bookmark',id:'A',saved:true});
 m.conflictOnce();
 const updated=await g.mutate({type:'bookmark',id:'B',saved:true});
 assert.deepEqual(Object.keys(updated.bookmarks).sort(),['A','B']);
});
test('only a private repository can be used',async()=>{
 const bad=R.createGateway({owner:'researcher',repo:'public',token:'example-only-token',requestFetch:async()=>({ok:true,json:async()=>({private:false})})});
 await assert.rejects(bad.verifyPrivate(),/Private/);
});
test('tokens are never written in synchronized data',async()=>{
 const m=mockGitHub(),g=R.createGateway({owner:'researcher',repo:'private-watch',token:'example-only-token',requestFetch:m.fetcher});
 await g.mutate({type:'bookmark',id:'X',saved:true});
 assert.equal(JSON.stringify(m.blob).includes('example-only-token'),false);
});

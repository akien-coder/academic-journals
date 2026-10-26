"""Optional UI smoke test, no network needed. Run: python tests/test_browser_smoke.py"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
PAPERS=[
 {'id':'doi:10.123/a','title':'A Study of Regional Innovations','journal':'Regional Studies','journal_id':'regional-studies','published':'2026-10-24','first_seen':'2026-10-24T12:00:00Z','authors':['A Smith'],'url':'https://doi.org/10.123/a','tags':[]},
 {'id':'doi:10.123/b','title':'Entrepreneurial Ecosystems','journal':'Economic Geography','journal_id':'economic-geography','published':'2026-10-24','first_seen':'2026-10-24T12:02:00Z','authors':['B Smith'],'url':'https://doi.org/10.123/b','tags':[]}
]

# Keep network fully disabled. The mocked repository is seeded on the second page.
def setup(page, seed=None):
    html=(ROOT/'index.html').read_text()
    html=html.replace('<link rel="stylesheet" href="style.css">','').replace('<script src="sync.js" defer></script>','').replace('<script src="app.js" defer></script>','')
    page.set_content(html)
    page.evaluate('''({papers, journals, topics, status, seed}) => {
      const settings=new Map();
      const makeStore=()=>({getItem:k=>settings.get(k)||null,setItem:(k,v)=>settings.set(k,v),removeItem:k=>settings.delete(k)});
      Object.defineProperty(window,'localStorage',{configurable:true,value:makeStore()});
      Object.defineProperty(window,'sessionStorage',{configurable:true,value:makeStore()});
      window.__remote=seed;window.__sha=0;
      const answer=(status,obj)=>({ok:status>=200&&status<300,status,json:async()=>obj});
      window.fetch=async (url, opts={}) => {
        if(url.includes('data/papers.json'))return answer(200,papers);
        if(url.includes('config/journals.json'))return answer(200,journals);
        if(url.includes('config/topics.json'))return answer(200,topics);
        if(url.includes('data/status.json'))return answer(200,status);
        if(url.includes('/repos/researcher/private-watch/contents/sync/state.json')){
          if(opts.method==='PUT'){
            const body=JSON.parse(opts.body);
            window.__remote=JSON.parse(decodeURIComponent(escape(atob(body.content))));window.__sha++;
            return answer(200,{content:{sha:String(window.__sha)}});
          }
          if(!window.__remote)return answer(404,{});
          return answer(200,{type:'file',encoding:'base64',sha:String(window.__sha),content:btoa(unescape(encodeURIComponent(JSON.stringify(window.__remote))))});
        }
        if(url.endsWith('/repos/researcher/private-watch'))return answer(200,{private:true});
        return answer(404,{});
      };
    }''',dict(papers=PAPERS,journals=json.loads((ROOT/'config/journals.json').read_text()),topics=json.loads((ROOT/'config/topics.json').read_text()),status={'updated_at':None,'sources':{}},seed=seed))
    page.add_script_tag(content=(ROOT/'sync.js').read_text())
    page.add_script_tag(content=(ROOT/'app.js').read_text())


def connect(page,token='example-token'):
    page.get_by_role('button',name='同期設定').click()
    page.locator('#sync-owner').fill('researcher')
    page.locator('#sync-repo').fill('private-watch')
    page.locator('#sync-token').fill(token)
    page.get_by_role('button',name='接続して読み込む').click()
    page.get_by_text('同期：同期済み').wait_for(timeout=5000)

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    page=browser.new_page()
    setup(page)
    connect(page)
    assert page.locator('#new-total').inner_text()=='2'
    page.locator('.star').first.click()
    page.get_by_text('同期：同期済み').wait_for()
    page.get_by_role('button',name='★ 保存済み').click()
    assert page.locator('article.paper').count()==1
    page.get_by_role('button',name='新着').first.click()
    page.once('dialog',lambda dialog:dialog.accept())
    page.locator('#confirm').click()
    page.wait_for_function("document.querySelector('#new-total').textContent==='0'")
    remote=page.evaluate('window.__remote')
    assert remote['bookmarks']['doi:10.123/b']['title']=='Entrepreneurial Ecosystems'
    assert remote['confirmed_at']=='2026-10-24T12:02:00.000Z'
    # Independent browser profile (smartphone or another PC) reads the same GitHub state.
    page2=browser.new_page()
    setup(page2,remote)
    connect(page2,token='another-device-token')
    assert page2.locator('#new-total').inner_text()=='0'
    assert page2.locator('#saved-total').inner_text()=='1'
    print('Browser smoke test OK: save, confirm, second device')
    browser.close()

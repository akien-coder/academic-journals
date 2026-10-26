import importlib.util
import json
import unittest
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / 'scripts' / 'collect.py'
spec = importlib.util.spec_from_file_location('collector', FILE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class CollectorTests(unittest.TestCase):
    def test_doi_canonical(self):
        self.assertEqual(m.normalize_doi('HTTPS://DOI.ORG/10.4321/ABC.X'), '10.4321/abc.x')
        self.assertEqual(m.key_of({'doi':'https://doi.org/10.1234/Hello','url':'https://foo'}),'doi:10.1234/hello')

    def test_crossref_online_first(self):
        journal={'title':'Regional Studies'}
        src={'DOI':'10.9999/example','title':['Regional science <i>in context</i>'],
             'type':'journal-article','published-online':{'date-parts':[[2026,9,11]]},
             'published-print':{'date-parts':[[2027,3,1]]},
             'author':[{'given':'A','family':'Writer'}], 'volume':'59','issue':'2'}
        p=m.crossref_item(src,journal)
        self.assertEqual(p['published'],'2026-09-11')
        self.assertEqual(p['title'],'Regional science in context')
        self.assertEqual(p['authors'],['A Writer'])

    def test_jstage_atom(self):
        xml='''<?xml version="1.0"?>
        <feed xmlns="http://www.w3.org/2005/Atom" xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
          <entry><title>制度変化と地域発展</title><link href="https://www.jstage.jst.go.jp/article/jaeg/1/2/abc/_article/-char/ja"/>
            <prism:doi>10.1234/test</prism:doi><dc:creator>研究者 太郎</dc:creator>
            <published>2026-09-01T00:00:00+09:00</published><prism:volume>72</prism:volume><prism:number>2</prism:number>
          </entry></feed>'''
        p=m.jstage_parse(xml,{'title':'経済地理学年報'})
        self.assertEqual(len(p),1)
        self.assertEqual(p[0]['title'],'制度変化と地域発展')
        self.assertEqual(p[0]['volume'],'72')
        self.assertEqual(p[0]['published'],'2026-09-01')

    def test_merge_preserves_first_seen_and_dedups(self):
        old={'first_seen':'2026-01-01T00:00:00+00:00','title':'Example','journal':'X', 'volume':'', 'sources':['Crossref'],'tags':[]}
        new={'first_seen':'2026-10-01T00:00:00+00:00','title':'Example','journal':'X', 'volume':'20','sources':['OpenAlex'],'tags':['bio'],'issns':[]}
        merged=m.merge(old,new,{})
        self.assertEqual(merged['first_seen'],'2026-01-01T00:00:00+00:00')
        self.assertEqual(merged['volume'],'20')
        self.assertEqual(merged['sources'],['Crossref','OpenAlex'])

    def test_journals_and_topics_config(self):
        root=FILE.parents[1]
        journals=json.loads((root/'config/journals.json').read_text())
        topics=json.loads((root/'config/topics.json').read_text())
        self.assertEqual(len(journals),20)
        self.assertEqual(sum(j['source']=='jstage' for j in journals),4)
        self.assertEqual(sum(j['source']=='crossref' for j in journals),15)
        self.assertEqual(sum(j['source']=='repec' for j in journals),1)
        self.assertEqual(len(topics),6)

if __name__=='__main__':
    unittest.main()

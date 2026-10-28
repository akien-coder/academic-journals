#!/usr/bin/env python3
"""Metadata-only daily harvester. No PDFs or paywalled text are fetched."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urljoin
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
NOW = datetime.now(timezone.utc)
TODAY = NOW.date()
HEADERS = {
    'User-Agent': 'ResearchPaperWatch/1.0 (academic metadata monitor; personal use; contact set via CROSSREF_MAILTO)',
    'Accept': 'application/json, application/xml, text/xml, text/html;q=0.9,*/*;q=0.5'
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
MAX_RECORDS = 12000
MAX_PAGES = 8
MAX_GEMINI_SUMMARIES = 20  # Do not exceed daily quota; unprocessed entries carry forward
MAX_ABSTRACT_LOOKUPS = 50  # Extra metadata lookups for older records per daily run


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path, obj):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def fetch(url, params=None, xml=False):
    for attempt in range(5):
        try:
            response = SESSION.get(url, params=params, timeout=35)
            if response.status_code in (429, 500, 502, 503, 504):
                delay = min(40, 2 ** attempt * 2)
                retry = response.headers.get('Retry-After')
                if retry and retry.isdigit():
                    delay = min(60, max(delay, int(retry)))
                logging.warning('HTTP %s from %s; retry in %ss', response.status_code, url, delay)
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response.text if xml else response.json()
        except (requests.RequestException, ValueError) as exc:
            if attempt == 4:
                raise RuntimeError(f'{url}: {exc}') from exc
            time.sleep(min(30, 2 ** attempt * 2))
    raise RuntimeError(f'Cannot fetch {url} after retries')


def normalize_doi(raw):
    raw = (raw or '').strip().lower()
    raw = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', raw)
    return raw if raw.startswith('10.') and '/' in raw else ''


def key_of(paper):
    doi = normalize_doi(paper.get('doi'))
    if doi:
        return 'doi:' + doi
    url = paper.get('url', '').split('#')[0].split('?')[0].rstrip('/').lower()
    if url:
        return 'url:' + url
    return 'title:' + re.sub(r'\W+', '', paper.get('title', '').lower())[:180]


def date_parts(obj):
    if not obj:
        return ''
    parts = obj.get('date-parts', [[]])[0]
    return '-'.join(str(p).zfill(2) if i else str(p) for i, p in enumerate(parts)) if parts else ''


def first(*vals):
    return next((v for v in vals if v), '')


def strip_markup(txt):
    return BeautifulSoup(str(txt or ''), 'html.parser').get_text(' ', strip=True)


def core(title, journal, url, doi='', authors=None, published='', vol='', issue='', source='', tags=None, kind='article'):
    title = strip_markup(title)
    doi = normalize_doi(doi)
    link = 'https://doi.org/' + quote(doi, safe='/()') if doi else str(url or '')
    return {
        'title': title, 'journal': journal, 'url': link, 'doi': doi,
        'authors': (authors or [])[:20], 'published': published, 'volume': str(vol or ''),
        'issue': str(issue or ''), 'kind': kind, 'sources': [source] if source else [],
        'tags': tags or [], 'first_seen': NOW.isoformat(timespec='seconds')
    }


def crossref_item(raw, journal):
    if raw.get('type') != 'journal-article':
        return None
    title = next(iter(raw.get('title') or []), '')
    if not title:
        return None
    # Online-first is preferred; 'published' acts as a fallback.
    published = first(date_parts(raw.get('published-online')),
                      date_parts(raw.get('published')),
                      date_parts(raw.get('published-print')),
                      date_parts(raw.get('issued')))
    authors = [' '.join(filter(None, [a.get('given'), a.get('family')])).strip()
               for a in raw.get('author', [])]
    paper = core(title, journal['title'], raw.get('URL'), raw.get('DOI'), authors,
                 published, raw.get('volume'), raw.get('issue'), 'Crossref')
    paper['_abstract'] = strip_markup(raw.get('abstract'))[:12000]
    return paper


def since_state(state_key, state, initial_days=180, overlap_days=4):
    previous = (state.get('collectors', {}).get(state_key) or {}).get('success_date')
    if previous:
        try:
            return min(TODAY, date.fromisoformat(previous) - timedelta(days=overlap_days))
        except ValueError:
            pass
    return TODAY - timedelta(days=initial_days)


def crossref_collect(journal, state):
    key = 'crossref:' + journal['id']
    past = (state.get('collectors', {}).get(key) or {}).get('success_date')
    start = since_state(key, state)
    # First run: publication-date window. Later runs: index-date for late metadata changes.
    filter_name = 'from-index-date' if past else 'from-pub-date'
    base_url = f"https://api.crossref.org/journals/{journal['issn']}/works"
    filters = f'{filter_name}:{start.isoformat()},type:journal-article'
    params = {'filter': filters, 'rows': 300, 'cursor': '*',
              'select': 'DOI,title,type,author,URL,published-online,published-print,published,issued,volume,issue,abstract'}
    email = os.getenv('CROSSREF_MAILTO', '').strip()
    if email:
        params['mailto'] = email
    results = []
    for i in range(MAX_PAGES):
        response = fetch(base_url, params)
        msg = response.get('message', {})
        batch = msg.get('items', [])
        for work in batch:
            paper = crossref_item(work, journal)
            if paper:
                results.append(paper)
        if len(batch) < 300 or not msg.get('next-cursor'):
            break
        params['cursor'] = msg['next-cursor']
        time.sleep(0.35)
    else:
        logging.warning('Crossref cap hit for %s: check truncated records', journal['id'])
    return results


def localname(tag):
    return tag.rsplit('}', 1)[-1].split(':')[-1].lower()


def direct_text(el):
    return ' '.join(''.join(el.itertext()).split()) if el is not None else ''


def children_by_name(root, name):
    return [el for el in root.iter() if localname(el.tag) == name.lower()]


def xml_first(root, *names):
    for name in names:
        for found in children_by_name(root, name):
            txt = direct_text(found)
            if txt:
                return txt
    return ''


def jstage_parse(xml_text, journal):
    root = ET.fromstring(xml_text)
    entries = [e for e in root.iter() if localname(e.tag) == 'entry']
    results = []
    for entry in entries:
        title = xml_first(entry, 'title')
        if not title:
            continue
        doi = xml_first(entry, 'doi')
        # Atom's alternate link points to the article landing page.
        links = [el.attrib.get('href', '') for el in entry.iter()
                 if localname(el.tag) == 'link' and el.attrib.get('href')]
        url = next((u for u in links if '/article/' in u), next(iter(links), ''))
        if not url and not normalize_doi(doi):
            continue
        authors = [direct_text(el) for el in entry.iter()
                   if localname(el.tag) == 'creator' and direct_text(el)]
        if not authors:
            authors = [direct_text(el) for el in entry.iter()
                       if localname(el.tag) == 'author' and direct_text(el)]
        published = xml_first(entry, 'published', 'pubdate', 'publicationdate', 'coverdate', 'date')[:10]
        volume = xml_first(entry, 'volume')
        issue = xml_first(entry, 'number', 'issue')
        paper = core(title, journal['title'], url, doi, authors, published,
                     volume, issue, 'J-STAGE')
        paper['_abstract'] = strip_markup(xml_first(entry, 'summary', 'abstract'))[:12000]
        results.append(paper)
    # The API can return error information as a valid XML document.
    errors = [direct_text(e) for e in root.iter() if localname(e.tag) in ('error', 'err_msg')]
    if errors:
        raise RuntimeError('J-STAGE API error: ' + '; '.join(errors[:3]))
    return results


def jstage_collect(journal):
    # A rolling 2-year window handles delayed publication/release updates.
    params = {'service': 3, 'cdjournal': journal['cdjournal'],
              'pubyearfrom': TODAY.year - 1, 'pubyearto': TODAY.year,
              'start': 1, 'count': 200}
    result = fetch('https://api.jstage.jst.go.jp/searchapi/do', params, xml=True)
    return jstage_parse(result, journal)


def repec_collect(journal):
    # RePEc is a working-paper *series*, not an ISSN journal; identifiers use the RePEc handle.
    html = SESSION.get(journal['home'], timeout=35)
    html.raise_for_status()
    soup = BeautifulSoup(html.text, 'html.parser')
    records = []
    seen = set()
    for a in soup.select('a[href*="/p/egu/wpaper/"]'):
        href = urljoin(journal['home'], a.get('href', ''))
        m = re.search(r'/p/egu/wpaper/(\d+)\.html', href)
        if not m or m.group(1) in seen:
            continue
        title = a.get_text(' ', strip=True)
        if len(title) < 12:
            continue
        seen.add(m.group(1))
        year = '20' + m.group(1)[:2] if len(m.group(1)) >= 4 else ''
        paper = core(title, journal['title'], href, published=year,
                     source='RePEc', kind='working-paper')
        paper['series_id'] = 'RePEc:egu:wpaper:' + m.group(1)
        paper['issue'] = m.group(1)
        records.append(paper)
        if len(records) >= 120:
            break
    if not records:
        raise RuntimeError('No PEEG records extracted: check page structure')
    return records


def merge(existing, incoming, journal_by_issn):
    if not existing:
        incoming.pop('issns', None)
        return incoming
    for key in ('title', 'journal', 'url', 'doi', 'authors', 'published', 'volume', 'issue', 'oa_url', 'kind', 'series_id'):
        value = incoming.get(key)
        if value and (not existing.get(key) or key in ('volume', 'issue')):
            existing[key] = value
    for key in ('sources', 'tags'):
        existing[key] = list(dict.fromkeys(existing.get(key, []) + incoming.get(key, [])))
    # Journal selection is based on confirmed ISSNs, not the provider's approximate journal name.
    known_id = next((journal_by_issn[x] for x in incoming.get('issns', [])
                     if x in journal_by_issn), None)
    if known_id:
        existing['journal_id'] = known_id
    return existing



def lookup_abstract(paper):
    """Look up a specific DOI; never run topical paper searches."""
    doi = normalize_doi(paper.get('doi'))
    if not doi:
        return ''
    # Crossref may contain the original publisher's abstract.
    try:
        record = fetch('https://api.crossref.org/works/' + quote(doi, safe='/()'))
        text = strip_markup((record.get('message') or {}).get('abstract'))
        if text:
            return text[:12000]
    except Exception as exc:
        logging.warning('Abstract unavailable from Crossref for %s: %s', doi, str(exc)[:90])
    # OpenAlex is used only as a DOI metadata fallback, NOT for keyword harvesting.
    key = os.getenv('OPENALEX_API_KEY', '').strip()
    if key:
        try:
            record = fetch('https://api.openalex.org/works/https://doi.org/' + quote(doi, safe='/'),
                           {'api_key': key})
            inverted = record.get('abstract_inverted_index') or {}
            words = [(position, word) for word, positions in inverted.items() for position in positions]
            words.sort()
            return ' '.join(word for _, word in words)[:12000]
        except Exception as exc:
            logging.warning('Abstract unavailable from OpenAlex for %s: %s', doi, str(exc)[:90])
    return ''


def gemini_summary(abstract, paper, api_key):
    """Brief, grounded Japanese synopsis generated from an available abstract."""
    url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent'
    prompt = (
        '以下は学術論文の抄録です。日本語で100〜150字の簡潔な要約を書いてください。'
        '対象、方法、主要な知見を抄録にある範囲で述べ、存在しない情報・数値・結論は補わない。'
        '抄録が研究計画だけなら結論を捏造しない。原題の日本語訳や前置き、箇条書きは不要。\n'
        'タイトル（照合用）: ' + paper.get('title', '')[:300] + '\n'
        '抄録: ' + abstract[:11000]
    )
    response = requests.post(
        url, headers={'x-goog-api-key': api_key, 'Content-Type': 'application/json'},
        json={'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
              'generationConfig': {'temperature': 0.1, 'maxOutputTokens': 600}},
        timeout=45
    )
    if response.status_code == 429:
        raise RuntimeError('Gemini free-tier rate limit reached (429)')
    if response.status_code in (401, 403, 404):
        raise RuntimeError('Gemini API key rejected or model unavailable (HTTP ' + str(response.status_code) + ')')
    response.raise_for_status()
    body = response.json()
    parts = ((body.get('candidates') or [{}])[0].get('content') or {}).get('parts') or []
    out = ' '.join(p.get('text', '') for p in parts).strip().strip('「」')
    if not out:
        raise RuntimeError('Gemini returned no text')
    return out[:400]


def summarize_records(papers, abstracts, report):
    """Daily quota + caching: keep old summaries, skip records without abstract."""
    api_key = os.getenv('GEMINI_API_KEY', '').strip()
    stats = {'enabled': bool(api_key), 'generated': 0, 'abstract_not_found': 0,
             'failed': 0, 'model': 'gemini-3.5-flash-lite', 'max_per_run': MAX_GEMINI_SUMMARIES}
    report['summaries'] = stats
    if not api_key:
        return
    lookups = 0
    attempts = 0
    now_iso = TODAY.isoformat()
    for p in sorted(papers, key=lambda p: (p.get('first_seen', ''), p.get('published', '')), reverse=True):
        if attempts >= MAX_GEMINI_SUMMARIES or lookups >= MAX_ABSTRACT_LOOKUPS:
            break
        if p.get('summary_ja'):
            continue
        # A previous negative abstract lookup is retried monthly rather than daily.
        checked = p.get('abstract_checked_at')
        abstract = abstracts.get(key_of(p), '')
        if checked and not abstract:
            try:
                if date.fromisoformat(checked) > TODAY - timedelta(days=30):
                    continue
            except ValueError:
                pass
        if not abstract:
            lookups += 1
            abstract = lookup_abstract(p)
        if not abstract:
            p['abstract_checked_at'] = now_iso
            stats['abstract_not_found'] += 1
            continue
        attempts += 1
        try:
            p['summary_ja'] = gemini_summary(abstract, p, api_key)
            p['summary_model'] = 'gemini-3.5-flash-lite'
            p.pop('abstract_checked_at', None)
            stats['generated'] += 1
            time.sleep(2.4)  # gentle pacing for free-tier per-minute limits
        except Exception as exc:
            logging.warning('Gemini summary skipped for %s: %s', p.get('doi') or p['id'], str(exc)[:160])
            stats['failed'] += 1
            if isinstance(exc, RuntimeError) and ('429' in str(exc) or 'key rejected' in str(exc) or 'model unavailable' in str(exc)):
                stats['paused_reason'] = str(exc)
                break
            # Other failures must not stop collection or erase existing summaries.
    stats['pending'] = sum(not p.get('summary_ja') and not p.get('abstract_checked_at') for p in papers)
    stats['attempted'] = attempts


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    journals = read_json(ROOT / 'config/journals.json', [])
    old = read_json(DATA / 'papers.json', [])
    original_total = len(old)
    state = read_json(DATA / 'state.json', {'collectors': {}})
    before = len(old)
    # Historic keyword-only records are removed; bookmarked copies remain in Private GitHub.
    registered = {j['id'] for j in journals}
    old = [p for p in old if p.get('journal_id') in registered]
    mapping = {key_of(p): p for p in old}
    abstracts = {}
    issn_to_id = {val: j['id'] for j in journals for val in (j.get('issn'), j.get('print_issn')) if val}
    report = {'updated_at': NOW.isoformat(timespec='seconds'), 'sources': {}, 'total_before': before,
              'removed_keyword_only': original_total - before}
    total_new = 0

    def ingest(papers, chosen=None):
        nonlocal total_new
        for paper in papers:
            if not paper.get('title') or not paper.get('url'):
                continue
            if chosen:
                paper['journal_id'] = chosen
            else:
                # DOI overlap with a registered journal is explicitly indicated.
                match = next((issn_to_id[x] for x in paper.get('issns', []) if x in issn_to_id), None)
                if match:
                    paper['journal_id'] = match
            key = key_of(paper)
            if paper.get('_abstract'):
                abstracts[key] = paper['_abstract']
            paper.pop('_abstract', None)  # Never publish raw abstracts to Pages
            if key not in mapping:
                mapping[key] = merge({}, paper, issn_to_id)
                mapping[key]['id'] = key
                total_new += 1
            else:
                mapping[key] = merge(mapping[key], paper, issn_to_id)

    for journal in journals:
        label = journal['source'] + ':' + journal['id']
        logging.info('Collecting %s', label)
        try:
            if journal['source'] == 'crossref':
                papers = crossref_collect(journal, state)
            elif journal['source'] == 'jstage':
                papers = jstage_collect(journal)
            else:
                papers = repec_collect(journal)
            ingest(papers, journal['id'])
            state.setdefault('collectors', {})[label] = {'success_date': TODAY.isoformat()}
            report['sources'][label] = {'ok': True, 'count': len(papers)}
            logging.info('  %d records', len(papers))
        except Exception as exc:
            logging.exception('Failed: %s', label)
            report['sources'][label] = {'ok': False, 'error': str(exc)[:240]}
        time.sleep(0.45)

    recent = sorted(mapping.values(), key=lambda p: (p.get('first_seen') or '', p.get('published') or ''), reverse=True)[:MAX_RECORDS]
    summarize_records(recent, abstracts, report)
    report['total_after'] = len(recent)
    report['new_papers'] = total_new
    write_json(DATA / 'papers.json', recent)
    write_json(DATA / 'state.json', state)
    write_json(DATA / 'status.json', report)
    logging.info('Stored %d records (%d newly collected)', len(recent), total_new)
    if not any(entry['ok'] for entry in report['sources'].values()):
        raise SystemExit('All providers failed; retained existing data, check API/network')


if __name__ == '__main__':
    main()

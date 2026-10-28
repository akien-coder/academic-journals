# Academic Journals — journal-only + Gemini edition

20 media: 19 academic journals plus 1 PEEG working paper series. No broad keyword collection. Titles remain in the original language. A brief Japanese synopsis is shown underneath when an abstract is available and Gemini has processed it.

## Collection

- Crossref: 15 journals by ISSN (Online First included when metadata available).
- J-STAGE: 4 Japanese journals.
- RePEc: PEEG series.
- OpenAlex is **only** used as an optional DOI-based abstract fallback. It is **not** used to find new papers by keyword.
- Existing `data/papers.json` is retained. On the first run of this version, keyword-only records are removed from the journal list, but saved bookmarks remain untouched in the separate Private GitHub repository.
- The Japanese synopsis uses **Gemini 2.5 Flash-Lite**, up to **20 requests per collection run**. Unprocessed articles roll over to a later day. Models and quotas can change.
- Abstracts are used transiently; the published JSON contains short AI-written Japanese synopses, not the full source abstracts. If an abstract cannot be retrieved, the site displays “日本語要約なし（抄録未取得・未処理）”. AI summaries can contain errors: check the original before citing.

## Setup

1. Keep `academic-journals` Public for GitHub Pages and `academic-journals-private` Private for personal ★ and acknowledgment synchronization.
2. Create a **Gemini API key** at https://aistudio.google.com/api-keys . Do not share it in chat or code.
3. In `academic-journals`: **Settings → Secrets and variables → Actions → New repository secret**. Set **Name** to `GEMINI_API_KEY`, and paste the key as **Secret**.
4. Replace the five changed files supplied in the update package. The Actions workflow `.github/workflows/update.yml` must contain `GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}` under `env:` for the Collect step.
5. **Actions → Collect research papers → Run workflow**. A green check confirms code ran, but inspect `data/status.json` → `summaries.generated` and the site itself to confirm actual Japanese summaries.

The daily cron is **07:00 JST** (`0 22 * * *` UTC). GitHub Actions scheduled tasks may start late. The optional `OPENALEX_API_KEY` enables broader abstract retrieval for papers missing Crossref abstracts. Crossref, J-STAGE, and RePEc are still the journal collection sources.

Gemini free tier limits and eligibility depend on the project. Never enable paid billing without reviewing the costs. Some free-tier requests may be used by Google for product improvements; use only permitted public metadata and abstracts.

## Data and privacy

- No Paperpile integration: follow the paper link and save with the Edge extension.
- ★ bookmarks and checked-through timestamps are stored in the separate private repo via the existing browser-based sync; no Firebase.
- Publication data and Japanese synopses are visible on the public GitHub Pages site.
- Never commit GitHub private repo tokens, Gemini keys or OpenAlex keys to the public repo.
- Preserve `data/papers.json`, `data/state.json`, `data/status.json` when uploading this patch; they contain the live collection state.

## Tests

```
python -m unittest discover -s tests -v
node --test tests/test_sync.cjs
```

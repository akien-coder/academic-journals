# Academic Journals

登録した19の学術雑誌と1つのワーキングペーパー系列、さらに6分野のOpenAlexキーワード検索結果を統合表示する研究用サイトです。**原題表示（翻訳なし）**。出版社等の論文ページを開き、文献登録はEdgeのPaperpile拡張機能で行う運用を想定しています。

## 最重要：GitHubだけで複数端末同期（Firebase不要）

**2つのGitHubリポジトリを使います。** それぞれに違う役割があります。

| リポジトリ | 公開設定 | 用途 |
| --- | --- | --- |
| `academic-journals` | **Public** | GitHub Pagesでサイトを表示、論文データを毎日収集。サイトのコードと収集した公開論文メタデータは誰でも閲覧できます。 |
| `academic-journals-private` | **Private** | 自分の★保存と「新着を確認済み」の情報だけ保管。他人は閲覧・編集できません。 |

重要：**Private側は空のリポジトリでも構いませんが、READMEを作成して最初のコミットを済ませてください。** 初めて★を付けたときに、サイトが自動で `sync/state.json` を作成します。

### 端末ごとの初期接続

1. GitHubで `academic-journals-private` を**Private**として新規作成し、`Add a README file` をオンにします。Public側とは別です。
2. GitHubの **Settings → Developer settings → Personal access tokens → Fine-grained tokens** で認証キーを作ります。**Repository access = Only select repositories** で `academic-journals-private` **のみ**を選択し、**Repository permissions → Contents = Read and write** に設定してください。それ以外の書き込み権限は不要です。キーに有効期限がある場合、期限切れ時は再発行します。
3. Academic Journalsの画面上部の**「同期設定」**を開き、GitHubユーザー名、非公開リポジトリ名、認証キーを入力します。「接続して読み込む」を押してください。
4. スマホ・別PCでも同じサイトを開き、**各端末で一度**この設定をします。以降、★保存と一括確認の操作はGitHubに反映されます。サイトに戻ったときにも同期し、手動の「今すぐ同期」ボタンもあります。

**認証キーをGitHub Pages用リポジトリ、公開ファイル、チャット、スクリーンショットなどに書かないでください。** 認証キーはユーザーのブラウザからGitHub APIへ直接送信されます。サイトに配布されるJavaScriptにキーを埋め込むことはありません。

- 初期設定では認証キーはブラウザの**セッション**にのみ保管します。タブを閉じると再入力が必要になる場合があります。
- 自分専用の端末なら「この端末に認証キーを保存する」をオンにできます。ただしブラウザ内のトークンは、端末を共有する人や悪意のあるスクリプトから完全に保護されるわけではありません。共用PCではチェックしないでください。
- **同期未接続のまま★を押しても、ローカルにだけ保存されることはありません。** 接続を促します。接続・保存に失敗したときも、保存できたことにしません。
- データの同時更新はGitHubのファイルSHAを使って競合を検出し、最新状態を再取得して再試行します。
- 初回接続前の旧版 `localStorage` 保存情報は自動移行していません。以前の★が必要な場合は手作業で再登録してください。
- この方式は**個人利用**向けです。短時間に多数の更新を繰り返すとGitHubのAPIレート制限に達する可能性があります。

## はじめかた

1. このフォルダ一式を新しいGitHubリポジトリ（例: `academic-journals`）にアップロードします。前回のニュースサイトとは**別リポジトリ**が安全です。
2. GitHubリポジトリの `Settings → Pages → Build and deployment` で **Deploy from a branch / main / (root)** にします。
3. `Settings → Secrets and variables → Actions` に `OPENALEX_API_KEY` を登録します（無料キー取得: https://openalex.org/）。キーなしでも試せますが、日々の定常収集にはキー推奨。`CROSSREF_MAILTO` に連絡先メールアドレスを設定するとCrossrefのpolite pool利用に役立ちます。**キーをソースに書かないでください。**
4. `Actions → Collect research papers → Run workflow` を手動実行してください。成功すると `data/papers.json` に取得結果が入り、その後は毎日日本時間07:20頃に実行されます（GitHub Actionsのスケジュールには遅延の可能性あり）。
5. 公開URLは通常 `https://<GitHubユーザー名>.github.io/<リポジトリ名>/` です。公開範囲やGitHub Pagesのプラン条件はリポジトリ設定で確認してください。

## ローカルプレビュー

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
OPENALEX_API_KEY='自分の無料キー' python scripts/collect.py
python -m http.server 8000
```

ブラウザで `http://localhost:8000/` を開いてください。ファイルを直接ダブルクリックして開くとブラウザの制限でJSONを読み込めないことがあります。

## 収集の考え方

- **15誌（海外）**: CrossrefのISSN単位で取得。初回は直近180日の公開日、2回目以降は前回成功日以降の**インデックス更新日時**で差分取得。早期公開日（published-online）がある場合は優先表示します。後から正式な巻号情報がついてもDOIで統合されます。
- **4誌（国内）**: J-STAGE WebAPIの`service=3`による各誌最近2年のメタデータ取得。APIが返す公開日を利用。国内誌は公開に時差が生じる場合があります。J-STAGEへの出典表示をサイトに設けています。
- **PEEG**: RePEcのPEEG系列ページから新しいワーキングペーパーを取得。DOIの代わりにRePEcの固有ページURLをキーとして使います。PEEGには日付が年単位しかない場合があります。
- **キーワード型**: OpenAlexで6カテゴリー・計12クエリを検索し、各検索の先頭100件を取得（直近75日）。無料枠では**インデックス更新日による完全同期は使えない**ため、公開日範囲を重ねて再取得します。検索範囲と100件上限に起因する漏れはありえます。
- **重複排除**: DOI（なければURL）を基準に統合。同じ論文の巻号情報が後から追加されてもNEW扱いに戻しません。
- **NEW**: 掲載日ではなく「このサイトが初めて収集した日時」で判定。一覧確認後に「今回の新着を確認済みにする」を1回押すと、次回の追加分だけNEWになります。初回は全てNEWとして扱われます。
- **★ 保存／新着確認**: 別のGitHub **Private**リポジトリの `sync/state.json` に保存。★には論文の最小限の書誌情報も保持するため、公開側の取得履歴から古い論文が消えても保存済み一覧に残ります。PC・スマホ間で同期します。Paperpile直接連携はありません。
- **巻号別**: 収録データに記載された巻号を集約する参考ビューであり、正式な最新号の完全な目次ではありません。

## 変更方法

- `config/journals.json` : ISSN、収集先、掲載誌名、J-STAGEコードを設定。
- `config/topics.json` : 6分野のOpenAlex検索語を追加・編集。
- `data/status.json` : 取得先ごとの成功・失敗、件数を確認。
- Actionsの実行スケジュール: `.github/workflows/update.yml` のUTC cronを変更。

## 注意事項

- 本プロジェクトは論文の**書誌メタデータと外部リンク**のみ収集し、PDFや購読制限付き本文をダウンロードしません。抄録の転載は禁止転載も行いません。
- J-STAGE WebAPIの利用条件を確認してください。商用利用には申請が必要です。 https://www.jstage.jst.go.jp/static/pages/JstageServices/TAB3/-char/ja
- Crossref・OpenAlex等のAPI利用制限、GitHub Pages/Actionsの利用条件は変更される場合があります。HTTP429への再試行を実装しています。
- 収集先に障害があった場合は前回までの結果を保持します。`data/status.json`でエラーを確認できます。
- 論文収集用APIの認証キーはGitHub ActionsのSecretsに設定します。個人データ用GitHub認証キーはユーザーが各端末のサイト上で設定し、その端末からGitHub APIへ直接送信します。GitHubにアップロードするコードや収集データには含めません。
- 20媒体全件の厳密な完全収集やIssue収録の厳密な保証はありません。欠損がある媒体は雑誌公式サイトのRSS/APIを個別追加する拡張方針です。

## テスト

```bash
python -m unittest discover -s tests -v
node --test tests/test_sync.cjs
```

`tests/test_browser_smoke.py` はブラウザを使う追加確認用です（Playwrightが必要）。

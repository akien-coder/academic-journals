# 最初の設定（5段階）

この更新版は、**★保存と新着確認をPC・スマホ間で同期**します。Firebaseは不要です。

## 1. サイト用のPublicリポジトリを用意

GitHubで `academic-journals`（Public）を作り、このZIPを解凍したフォルダの**中身**を全部アップロード。`.github/workflows/update.yml` も必須です。過去版のファイルがある場合は **`index.html`, `app.js`, `style.css`, `sync.js`, `README.md` など更新版一式**に置き換えてください。

## 2. 保存先のPrivateリポジトリを別途作成

GitHubで `academic-journals-private`（Private）を新規作成し、`Add a README file` をオンにして保存します。**Publicにはしない**でください。

## 3. 個人用GitHub認証キーを作る

GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token

- Repository access: **Only select repositories**
- 選ぶリポジトリ: **`academic-journals-private` のみ**
- Repository permissions → Contents: **Read and write**
- キーをメモ。画面共有、チャット、Public側リポジトリのファイルには貼り付けない。

認証キーの取得手順：[GitHub公式ヘルプ](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)。

## 4. サイトを公開、論文を収集

Public側の Settings → Pages → Deploy from a branch → main / (root)。
次に Actions → Collect research papers → Run workflow を実行。必要に応じて公開側 Secrets に `OPENALEX_API_KEY` を追加してください。

## 5. サイト上で同期設定

Academic Journals の上部「同期設定」を開き、ユーザー名・Privateリポジトリ名・認証キーを入力。「接続して読み込む」を押します。スマホ・別PCでも**同じPrivateリポジトリと認証キー**を設定すれば、★保存と新着確認が同期します。

**メモ:** 自分以外も使うPCでは「この端末に認証キーを保存する」をオフにしてください。GitHub Pagesで同じ `username.github.io` ドメインの別サイトを運用している場合も、トークンをブラウザへ長期保存すると同一オリジンのスクリプトから読み取られるリスクがあります。

※現在のサイトZIPに論文は含まれず、初回のGitHub Actions実行で収集します。GitHub実アカウントとの通信はユーザー設定後に確認が必要です。

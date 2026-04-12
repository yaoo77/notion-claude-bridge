# よくある質問 (FAQ)

notion-claude-bridge に関するよくある質問と回答をまとめています。

---

## セットアップ・初期設定

### Q1. セットアップに必要なものは何ですか？

以下が必要です：

- **GitHub リポジトリ** — notion-claude-bridge のコードをホストする場所
- **Anthropic API キー** — Claude Code を動かすために必要（GitHub Secrets に `ANTHROPIC_API_KEY` として登録）
- **GitHub App「claude」** — リポジトリにインストールする
- **Cloudflare アカウント** — MCP サーバー（Worker）のホスティングに使用
- **Notion ワークスペース** — Notion AI と MCP 連携が利用できるプラン

---

### Q2. Cloudflare Worker の設定方法を教えてください。

1. `worker/` ディレクトリ配下のコードを Cloudflare Workers にデプロイします。
2. Worker の Secret に `GITHUB_TOKEN`（対象リポジトリへの書き込み権限が必要）を設定します。
3. デプロイ後に発行された Worker の URL を控えておきます。

---

### Q3. Notion AI の MCP 設定はどこで行いますか？

Notion の **ワークスペース設定 → Notion AI → MCP** から設定します。

1. 「許可リスト」に Cloudflare Worker の URL を追加します。
2. カスタムエージェントに MCP サーバーを接続します。
3. 接続後、Notion AI から `create_issue` / `comment_on_pr` ツールが利用できるようになります。

---

## 使い方

### Q4. Notion AI から Claude Code を呼び出す方法は？

Notion AI エージェントで MCP ツールを使い、GitHub に Issue またはコメントを作成します。
Issue・コメントの本文に `@claude` を含めることで、GitHub Actions が起動して Claude Code が処理を実行します。

基本的な流れ：

```
Notion AI → MCP ツール (create_issue / comment_on_pr) → GitHub Issue/PR → @claude トリガー → Claude Code が処理
```

---

### Q5. Claude Code が動いているか確認するには？

GitHub の **Actions** タブから実行中のワークフローを確認できます。
また、Claude Code は処理状況を Issue/PR のコメントに書き込むため、そちらでも確認可能です。

---

### Q6. `@claude` を付けてもアクションが起動しない場合は？

以下を確認してください：

- GitHub App「claude」がリポジトリにインストールされているか
- `ANTHROPIC_API_KEY` が GitHub Secrets に正しく設定されているか
- `.github/workflows/claude.yml` が正しく存在しているか
- Issue/PR の本文またはコメントに `@claude` が含まれているか

---

## スライド生成

### Q7. Google Slides を生成する方法は？

1. `slides.json` をプロジェクトルートに作成します（5〜7 枚構成推奨）：

```json
[
  {"title": "表紙タイトル", "body": "サブタイトル"},
  {"title": "セクション1", "body": "内容\n箇条書き1\n箇条書き2"}
]
```

2. 依存パッケージをインストールします：

```bash
pip install -r scripts/requirements.txt
```

3. スクリプトを実行します：

```bash
python3 scripts/create_slides.py --title "プレゼンタイトル" --slides slides.json
```

4. 出力される JSON から Google Slides の URL を取得します。

> **注意**: 環境変数 `GOOGLE_OAUTH_TOKEN` が必要です（GitHub Secrets に登録済み）。

---

### Q8. スライド生成で認証エラーが出る場合は？

`GOOGLE_OAUTH_TOKEN` が正しく設定されているか確認してください。
GitHub Actions 経由で実行する場合は Secrets に登録されている必要があります。

---

## トラブルシューティング

### Q9. Claude Code が途中でエラーになった場合はどうすればよいですか？

GitHub Actions のログ（**Actions タブ → 対象のワークフロー実行 → ジョブの詳細**）でエラー内容を確認してください。
多くの場合、API キーの期限切れ・権限不足・ネットワークエラーのいずれかが原因です。

---

### Q10. 結果を Notion に自動で反映させることはできますか？

はい。Claude Code が処理を完了すると、GitHub Actions が Notion の対象データベースを自動更新する仕組みが実装されています。
Notion 側でデータベース ID と連携設定が正しく行われていることを確認してください。

---

## その他

### Q11. このシステムのアーキテクチャを教えてください。

```
Notion AI エージェント
  ↓ MCP ツール (create_issue / comment_on_pr)
Cloudflare Worker (MCP サーバー)
  ↓ GitHub API
notion-claude-bridge リポジトリ
  ↓ @claude トリガー
claude-code-action (GitHub Actions)
  ↓ コード修正・PR 作成・コメント返信
Notion AI が GitHub コネクターで結果を読む
```

---

### Q12. 不具合や要望はどこに報告すればよいですか？

このリポジトリの **Issues** から報告してください。
Issue の本文に `@claude` を付けることで、Claude Code に直接タスクを依頼することも可能です。

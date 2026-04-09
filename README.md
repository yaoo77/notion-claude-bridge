# notion-claude-bridge

Notion AI から Claude Code を非同期で操作するブリッジシステム。

## 構成

```
Notion AI エージェント
  ↓ MCP ツール (create_issue / comment_on_pr)
Cloudflare Worker (MCPサーバー)
  ↓ GitHub API
このリポジトリ
  ↓ @claude トリガー
claude-code-action (GitHub Actions)
  ↓ コード修正・PR作成・コメント返信
Notion AI が GitHubコネクターで結果を読む
```

## 使い方

1. **Notion AI でIssueを作成する**
   - Notion AI エージェントに「〇〇を実装して」などのタスクを伝える
   - エージェントが MCP ツール（`create_issue`）を使い、このリポジトリに GitHub Issue を自動作成する
   - Issue 本文には `@claude` が含まれ、Claude Code へのトリガーとなる

2. **Claude Code が自動でPRを作成する**
   - GitHub Actions の `claude-code-action` が起動し、Issue の内容を解析
   - コードを修正・追加して、専用ブランチへコミット・プッシュ
   - Pull Request を自動作成し、Issue にコメントで結果を報告する

3. **結果を確認する**
   - Notion AI が GitHub コネクターで PR やコメントを読み取り、タスク完了を確認できる
   - PR をレビューしてマージするだけで作業完了

## セットアップ

### 1. GitHub
- `ANTHROPIC_API_KEY` をリポジトリのSecretsに登録
- GitHub App [claude](https://github.com/apps/claude) をインストール

### 2. Cloudflare Worker (MCPサーバー)
- `worker/` 配下をデプロイ
- `GITHUB_TOKEN` を Worker の Secret に設定

### 3. Notion AI
- ワークスペース設定 → Notion AI → MCP → Worker URLを許可リストに追加
- カスタムエージェントにMCPサーバーを接続

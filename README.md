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

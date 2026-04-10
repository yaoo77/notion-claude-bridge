# notion-claude-bridge

## スライド生成

Google Slidesを作成する場合:

1. スライド内容を slides.json として作成
2. `pip install -r scripts/requirements.txt` を実行
3. `python scripts/create_slides.py --title "タイトル" --slides slides.json` を実行
4. 出力されるJSONからURLを取得

slides.json の形式:
```json
[
  {"title": "表紙タイトル", "body": "サブタイトル"},
  {"title": "セクション1", "body": "内容\n箇条書き1\n箇条書き2"},
  {"title": "セクション2", "body": "内容"}
]
```

環境変数 `GCP_SA_KEY` が必要（GitHub Secretsに登録済み）。

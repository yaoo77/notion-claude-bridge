#!/usr/bin/env python3
"""
Google Slides 自動生成スクリプト
Claude Code Action から呼び出され、提案書・研修資料等のスライドを生成する。

Usage:
    python scripts/create_slides.py \
        --title "第一三共様向けAI研修提案" \
        --slides slides.json

slides.json の形式:
[
  {"title": "スライドタイトル", "body": "本文\n箇条書き1\n箇条書き2"},
  ...
]
"""

import argparse
import json
import os
import sys

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def authenticate():
    token_data = json.loads(os.environ["GOOGLE_OAUTH_TOKEN"])
    creds = Credentials(
        token=token_data["token"],
        refresh_token=token_data["refresh_token"],
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=[
            "https://www.googleapis.com/auth/presentations",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    slides_svc = build("slides", "v1", credentials=creds)
    drive_svc = build("drive", "v3", credentials=creds)
    return slides_svc, drive_svc


def create_presentation(slides_svc, title):
    pres = slides_svc.presentations().create(body={"title": title}).execute()
    return pres["presentationId"], pres["slides"][0]["objectId"]


def add_slides(slides_svc, pres_id, slide_data):
    """スライドを追加してテキストを挿入する"""
    # 1枚目は既存、2枚目以降を追加
    requests = []
    for i in range(len(slide_data) - 1):
        sid = f"slide_{i + 2}"
        layout = "TITLE_AND_BODY"
        if i == 0 and len(slide_data) > 1:
            layout = "TITLE_AND_BODY"
        requests.append({
            "createSlide": {
                "objectId": sid,
                "insertionIndex": i + 1,
                "slideLayoutReference": {"predefinedLayout": layout},
            }
        })

    # 1枚目のレイアウトをタイトルスライドに変更
    if requests:
        slides_svc.presentations().batchUpdate(
            presentationId=pres_id, body={"requests": requests}
        ).execute()

    # スライド情報を再取得
    pres = slides_svc.presentations().get(presentationId=pres_id).execute()

    # テキスト挿入
    text_requests = []
    for idx, slide in enumerate(pres["slides"]):
        if idx >= len(slide_data):
            break
        data = slide_data[idx]
        for element in slide.get("pageElements", []):
            shape = element.get("shape", {})
            ph = shape.get("placeholder", {})
            ph_type = ph.get("type", "")

            if ph_type in ("TITLE", "CENTERED_TITLE"):
                text_requests.append({
                    "insertText": {
                        "objectId": element["objectId"],
                        "text": data.get("title", ""),
                        "insertionIndex": 0,
                    }
                })
            elif ph_type in ("BODY", "SUBTITLE"):
                text_requests.append({
                    "insertText": {
                        "objectId": element["objectId"],
                        "text": data.get("body", ""),
                        "insertionIndex": 0,
                    }
                })

    if text_requests:
        slides_svc.presentations().batchUpdate(
            presentationId=pres_id, body={"requests": text_requests}
        ).execute()


def make_public(drive_svc, pres_id):
    """誰でも閲覧可能にする"""
    drive_svc.permissions().create(
        fileId=pres_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()


def move_to_folder(drive_svc, pres_id, folder_id):
    """指定フォルダに移動"""
    file = drive_svc.files().get(fileId=pres_id, fields="parents").execute()
    prev_parents = ",".join(file.get("parents", []))
    drive_svc.files().update(
        fileId=pres_id,
        addParents=folder_id,
        removeParents=prev_parents,
        fields="id, parents",
    ).execute()


def main():
    parser = argparse.ArgumentParser(description="Generate Google Slides")
    parser.add_argument("--title", required=True, help="プレゼンテーションのタイトル")
    parser.add_argument("--slides", required=True, help="スライド内容のJSONファイルパス")
    parser.add_argument("--folder", help="Google DriveフォルダID（省略時はルート）")
    args = parser.parse_args()

    # スライドデータ読み込み
    with open(args.slides) as f:
        slide_data = json.load(f)

    if not slide_data:
        print("Error: slides.json is empty", file=sys.stderr)
        sys.exit(1)

    # 認証
    slides_svc, drive_svc = authenticate()

    # スライド作成
    pres_id, first_slide_id = create_presentation(slides_svc, args.title)
    add_slides(slides_svc, pres_id, slide_data)

    # 公開設定
    make_public(drive_svc, pres_id)

    # フォルダ移動（指定時）
    if args.folder:
        move_to_folder(drive_svc, pres_id, args.folder)

    # 結果出力
    url = f"https://docs.google.com/presentation/d/{pres_id}/edit"
    result = {
        "presentation_id": pres_id,
        "url": url,
        "slide_count": len(slide_data),
        "title": args.title,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Google Slides 自動生成スクリプト（テンプレコピー方式）
Michikusa会社概要_テンプレをコピーし、不要スライドを削除、
セクション扉の文言を差し替え、新規コンテンツスライドを追加する。

Usage:
    python scripts/create_slides.py \
        --title "第一三共様向けAI研修提案" \
        --slides slides.json

    # テンプレなしで新規作成（フォールバック）
    python scripts/create_slides.py \
        --title "タイトル" \
        --slides slides.json \
        --no-template

slides.json の形式:
[
  {"title": "スライドタイトル", "body": "本文\\n箇条書き1\\n箇条書き2"},
  ...
]
"""

import argparse
import json
import os
import sys

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Michikusa テンプレート設定
TEMPLATE_ID = "12l8CuaomS2F2Ejo5ZOTF9xwj4Y7HkYn8HShyPRhQBHw"
DEST_FOLDER_ID = "1hRW692V8wtJJvOVMC3D_dNikxIHEY_MW"

# テンプレートで残すスライド番号（0始まり）
# 0:タイトル, 1:Michikusaご紹介扉, 2:会社概要, 6:研修実績ロゴ, 7:研修実績数値, 8:セクション扉, 47:Thank you
KEEP_SLIDES = [0, 1, 2, 6, 7, 8, 47]


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


def copy_template(drive_svc, title):
    """テンプレートをコピーして新しいプレゼンテーションを作成"""
    copied = drive_svc.files().copy(
        fileId=TEMPLATE_ID,
        body={"name": title},
    ).execute()
    return copied["id"]


def remove_unwanted_slides(slides_svc, pres_id):
    """不要なスライドを削除（KEEP_SLIDESに含まれないもの）"""
    pres = slides_svc.presentations().get(presentationId=pres_id).execute()
    all_slides = pres["slides"]
    to_delete = []
    for idx, slide in enumerate(all_slides):
        if idx not in KEEP_SLIDES:
            to_delete.append(slide["objectId"])

    if to_delete:
        requests = [{"deleteObject": {"objectId": oid}} for oid in to_delete]
        slides_svc.presentations().batchUpdate(
            presentationId=pres_id, body={"requests": requests}
        ).execute()


def replace_section_title(slides_svc, pres_id, placeholder, replacement):
    """セクション扉の文言を差し替え"""
    slides_svc.presentations().batchUpdate(
        presentationId=pres_id,
        body={"requests": [{
            "replaceAllText": {
                "containsText": {"text": placeholder, "matchCase": False},
                "replaceText": replacement,
            }
        }]}
    ).execute()


def add_content_slides(slides_svc, pres_id, slide_data, insert_after_index):
    """コンテンツスライドを追加（テンプレートのレイアウトを使用）"""
    pres = slides_svc.presentations().get(presentationId=pres_id).execute()
    layouts = pres.get("layouts", [])

    # TITLE_AND_BODY に相当するレイアウトを探す
    layout_id = None
    for layout in layouts:
        name = layout.get("layoutProperties", {}).get("name", "")
        if "title" in name.lower() and ("body" in name.lower() or "content" in name.lower()):
            layout_id = layout["objectId"]
            break
    if not layout_id and layouts:
        layout_id = layouts[0]["objectId"]

    requests = []
    for i, data in enumerate(slide_data):
        sid = f"content_slide_{i}"
        req = {
            "createSlide": {
                "objectId": sid,
                "insertionIndex": insert_after_index + i,
            }
        }
        if layout_id:
            req["createSlide"]["slideLayoutReference"] = {"layoutId": layout_id}
        else:
            req["createSlide"]["slideLayoutReference"] = {"predefinedLayout": "TITLE_AND_BODY"}
        requests.append(req)

    if requests:
        slides_svc.presentations().batchUpdate(
            presentationId=pres_id, body={"requests": requests}
        ).execute()

    # テキスト挿入
    pres = slides_svc.presentations().get(presentationId=pres_id).execute()
    text_requests = []

    for i, data in enumerate(slide_data):
        slide_idx = insert_after_index + i
        if slide_idx >= len(pres["slides"]):
            break
        slide = pres["slides"][slide_idx]
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


def create_from_scratch(slides_svc, title, slide_data):
    """テンプレなしで新規作成（フォールバック）"""
    pres = slides_svc.presentations().create(body={"title": title}).execute()
    pres_id = pres["presentationId"]

    requests = []
    for i in range(len(slide_data) - 1):
        requests.append({
            "createSlide": {
                "objectId": f"slide_{i + 2}",
                "insertionIndex": i + 1,
                "slideLayoutReference": {"predefinedLayout": "TITLE_AND_BODY"},
            }
        })
    if requests:
        slides_svc.presentations().batchUpdate(
            presentationId=pres_id, body={"requests": requests}
        ).execute()

    pres = slides_svc.presentations().get(presentationId=pres_id).execute()
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

    return pres_id


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
    parser.add_argument("--no-template", action="store_true", help="テンプレなしで新規作成")
    parser.add_argument("--no-folder", action="store_true", help="提案資料フォルダに移動しない")
    args = parser.parse_args()

    with open(args.slides) as f:
        slide_data = json.load(f)

    if not slide_data:
        print("Error: slides.json is empty", file=sys.stderr)
        sys.exit(1)

    slides_svc, drive_svc = authenticate()

    if args.no_template:
        pres_id = create_from_scratch(slides_svc, args.title, slide_data)
    else:
        # テンプレコピー方式
        pres_id = copy_template(drive_svc, args.title)
        remove_unwanted_slides(slides_svc, pres_id)

        # セクション扉の文言差し替え（02セクション → 提案内容のタイトルに）
        if slide_data:
            replace_section_title(slides_svc, pres_id, "02", slide_data[0].get("title", "提案内容"))

        # テンプレの残りスライド数を取得してコンテンツを追加
        pres = slides_svc.presentations().get(presentationId=pres_id).execute()
        # Thank youスライドの前にコンテンツを挿入
        insert_idx = len(pres["slides"]) - 1
        add_content_slides(slides_svc, pres_id, slide_data, insert_idx)

    make_public(drive_svc, pres_id)

    if not args.no_folder and not args.no_template:
        move_to_folder(drive_svc, pres_id, DEST_FOLDER_ID)

    url = f"https://docs.google.com/presentation/d/{pres_id}/edit"
    result = {
        "presentation_id": pres_id,
        "url": url,
        "slide_count": len(slide_data),
        "title": args.title,
        "template": "michikusa" if not args.no_template else "none",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

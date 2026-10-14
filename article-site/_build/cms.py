#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ARTICLE — microCMS からの記事取得・検証

ビルド時（build.py の実行時）にだけ動きます。
公開されるHTML / CSS / JS には APIキーは一切含まれません。

環境変数
  MICROCMS_SERVICE_DOMAIN : https://XXXX.microcms.io の XXXX 部分
  MICROCMS_API_KEY        : GET のみ許可した APIキー
  ARTICLE_SAMPLE          : 1 = サンプル記事を使う / 0 = 使わない（未指定なら自動判定）
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

BUILD_DIR = pathlib.Path(__file__).resolve().parent
SAMPLE_FILE = BUILD_DIR / "sample-articles.json"

ENDPOINT = "articles"
VALID_CATEGORIES = ("COLUMN", "NEWS")
SLUG_RE = re.compile(r"^[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*$")
JST = timezone(timedelta(hours=9))

PAGE_SIZE = 100
MAX_ITEMS = 1000


class BuildError(Exception):
    """記事データに問題があってビルドを止めるときに投げる例外。"""


# ---------------------------------------------------------------- 本番判定
def is_production() -> bool:
    """本番ビルドかどうか。

    本番＝Netlify等の自動ビルド。ここではサンプル記事・サンプル実績・
    サンプルのお客様の声を一切出力しません（架空の実績と誤解されないため）。

      ARTICLE_ENV=production … 強制的に本番扱い（手元で最終確認したいとき）
      ARTICLE_ENV=preview    … 強制的にプレビュー扱い
      未指定                  … NETLIFY / CI 環境変数があれば本番
    """
    env = os.environ.get("ARTICLE_ENV", "").strip().lower()
    if env in ("production", "prod", "1"):
        return True
    if env in ("preview", "local", "dev", "0"):
        return False
    return bool(os.environ.get("NETLIFY") or os.environ.get("CI"))


# ---------------------------------------------------------------- 取得
def _request(domain: str, api_key: str, endpoint: str, offset: int, orders: str = "") -> dict:
    url = (
        f"https://{domain}.microcms.io/api/v1/{endpoint}"
        f"?limit={PAGE_SIZE}&offset={offset}"
    )
    if orders:
        url += f"&orders={orders}"
    req = urllib.request.Request(url, headers={"X-MICROCMS-API-KEY": api_key})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode("utf-8"))


def fetch_raw(domain: str, api_key: str, endpoint: str = ENDPOINT,
              orders: str = "-date", required: bool = True) -> list[dict]:
    """microCMS から公開中のコンテンツをすべて取得する（下書きは含まれません）。"""
    items: list[dict] = []
    offset = 0
    while offset < MAX_ITEMS:
        try:
            data = _request(domain, api_key, endpoint, offset, orders)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if not required and e.code == 404:
                print(f"  ⚠ エンドポイント '{endpoint}' が見つかりません。既存の内容を表示します。",
                      file=sys.stderr)
                return []
            raise BuildError(
                f"microCMS からの取得に失敗しました（HTTP {e.code}）。\n"
                f"  エンドポイント : {endpoint}\n"
                f"  サービスドメイン: {domain}\n"
                f"  応答           : {body}\n"
                f"  → APIキーの権限（GET）と、エンドポイント名をご確認ください。"
            ) from e
        except urllib.error.URLError as e:
            if not required:
                print(f"  ⚠ '{endpoint}' に接続できませんでした（{e.reason}）。既存の内容を表示します。",
                      file=sys.stderr)
                return []
            raise BuildError(
                f"microCMS に接続できませんでした（{e.reason}）。ネットワーク接続をご確認ください。"
            ) from e

        chunk = data.get("contents") or []
        items.extend(chunk)
        total = data.get("totalCount", len(items))
        offset += PAGE_SIZE
        if offset >= total or not chunk:
            break
    return items


# ---------------------------------------------------------------- 正規化
def _text(v) -> str:
    return "" if v is None else str(v).strip()


def _category(v) -> str:
    """セレクトフィールドは ['COLUMN'] のような配列で返ってくる。"""
    if isinstance(v, (list, tuple)):
        v = v[0] if v else ""
    if isinstance(v, dict):
        v = v.get("value") or v.get("label") or v.get("name") or ""
    return _text(v).upper()


def _image(v) -> dict | None:
    if not v:
        return None
    if isinstance(v, str):
        return {"url": v, "width": None, "height": None}
    url = v.get("url")
    if not url:
        return None
    return {"url": url, "width": v.get("width"), "height": v.get("height")}


def _parse_dt(v: str):
    if not v:
        return None
    s = v.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(JST)


def normalise(raw: list[dict]) -> list[dict]:
    """microCMS の生データを、テンプレートで使いやすい形に整えつつ検証する。"""
    errors: list[str] = []
    warnings: list[str] = []
    seen: dict[str, str] = {}
    out: list[dict] = []

    for i, it in enumerate(raw, 1):
        cid = _text(it.get("id")) or f"(id不明・{i}件目)"
        title = _text(it.get("title"))
        slug = _text(it.get("slug"))
        category = _category(it.get("category"))
        label = title or slug or cid

        # --- 必須項目 ---
        if not title:
            errors.append(f"[{cid}] title（記事タイトル）が空です。")
        if not slug:
            errors.append(f"[{label}] slug（URL用文字列）が空です。")
        elif not SLUG_RE.match(slug):
            errors.append(
                f"[{label}] slug「{slug}」は使えません。"
                f"半角英数字とハイフンのみ、先頭と末尾はハイフン以外にしてください（例: web-renewal-tips）。"
            )
        elif slug in seen:
            errors.append(
                f"[{label}] slug「{slug}」が重複しています（先に「{seen[slug]}」が使用）。"
                f"どちらかを変更してください。"
            )
        else:
            seen[slug] = label

        if not category:
            errors.append(f"[{label}] category が未選択です。COLUMN か NEWS を選んでください。")
        elif category not in VALID_CATEGORIES:
            errors.append(
                f"[{label}] category「{category}」は使えません。"
                f"選択肢は {' / '.join(VALID_CATEGORIES)} です。"
            )

        content = it.get("content") or ""
        if not _text(content):
            errors.append(f"[{label}] content（記事本文）が空です。")

        # --- 日付 ---
        published = _parse_dt(_text(it.get("date"))) or _parse_dt(_text(it.get("publishedAt")))
        if published is None:
            published = _parse_dt(_text(it.get("createdAt")))
        if published is None:
            errors.append(f"[{label}] date（公開日）が読み取れませんでした。")
            published = datetime.now(JST)

        modified = (
            _parse_dt(_text(it.get("revisedAt")))
            or _parse_dt(_text(it.get("updatedAt")))
            or published
        )
        if modified < published:
            modified = published

        excerpt = _text(it.get("excerpt"))
        if not excerpt:
            warnings.append(f"[{label}] excerpt（概要）が空です。一覧の説明文とSEO説明文が出せません。")

        eyecatch = _image(it.get("eyecatch"))
        if eyecatch is None:
            warnings.append(f"[{label}] eyecatch（メイン画像）が未設定です。代替表示になります。")

        out.append(dict(
            id=cid,
            title=title,
            slug=slug,
            category=category if category in VALID_CATEGORIES else "COLUMN",
            excerpt=excerpt,
            content=content,
            eyecatch=eyecatch,
            published=published,
            modified=modified,
            seo_title=_text(it.get("seoTitle")),
            seo_description=_text(it.get("seoDescription")),
        ))

    if errors:
        msg = ["microCMS の記事データにエラーがあります。修正してから再度ビルドしてください。", ""]
        msg += [f"  ✕ {e}" for e in errors]
        raise BuildError("\n".join(msg))

    for w in warnings:
        print(f"  ⚠ {w}", file=sys.stderr)

    out.sort(key=lambda a: a["published"], reverse=True)
    return out


# ---------------------------------------------------------------- 入口
def load_articles() -> tuple[list[dict], str]:
    """記事一覧と、データの出どころ（'microcms' / 'sample' / 'empty'）を返す。"""
    domain = os.environ.get("MICROCMS_SERVICE_DOMAIN", "").strip()
    api_key = os.environ.get("MICROCMS_API_KEY", "").strip()

    if domain and api_key:
        raw = fetch_raw(domain, api_key)
        articles = normalise(raw)
        return articles, "microcms"

    # --- APIの設定がない場合 ---
    # 本番ビルドでは、サンプル記事を絶対に出力しません。
    sample_flag = os.environ.get("ARTICLE_SAMPLE", "").strip()
    if is_production():
        use_sample = False
    else:
        use_sample = sample_flag != "0"

    if use_sample and SAMPLE_FILE.exists():
        raw = json.loads(SAMPLE_FILE.read_text(encoding="utf-8"))
        articles = normalise(raw)
        return articles, "sample"

    return [], "empty"


# ---------------------------------------------------------------- 制作実績
# 既存の works-web / works-film エンドポイントは変更していません。
# 以前はブラウザ側から呼び出していましたが、APIキーを公開しないため
# ビルド時に取得して静的HTMLに書き出す方式に変更しています。
WORKS_WEB_ENDPOINT = "works-web"
WORKS_FILM_ENDPOINT = "works-film"


def _first(obj, keys, default=""):
    for k in keys:
        v = obj.get(k)
        if v not in (None, "", [], {}):
            return v
    return default


def _tags(v) -> list[str]:
    if not v:
        return []
    if isinstance(v, (list, tuple)):
        out = []
        for x in v:
            if isinstance(x, str):
                out.append(x.strip())
            elif isinstance(x, dict):
                out.append(_text(x.get("label") or x.get("name") or x.get("value")))
        return [t for t in out if t]
    return [t.strip() for t in re.split(r"[,、/]", str(v)) if t.strip()]


def _url_of(v) -> str:
    if not v:
        return ""
    if isinstance(v, str):
        return v.strip()
    return _text(v.get("url"))


def normalise_web_works(raw: list[dict]) -> list[dict]:
    out = []
    for it in raw:
        name = _text(_first(it, ["title", "name", "clientEn"]))
        if not name:
            continue
        url = _text(_first(it, ["url", "siteUrl", "link"]))
        out.append(dict(
            name=name,
            jp=_text(_first(it, ["clientName", "client", "jpName", "subtitle"])),
            ghost=_text(_first(it, ["ghost", "keyword"])) or name,
            url=url,
            tags=_tags(_first(it, ["tags", "tag", "category", "categories"])),
            copy=_text(_first(it, ["description", "body", "copy", "text"])),
            thumb=_url_of(_first(it, ["thumbnail", "image", "ogp", "eyecatch"])),
        ))
    return out


def normalise_film_works(raw: list[dict]) -> list[dict]:
    out = []
    for it in raw:
        name = _text(_first(it, ["title", "name"]))
        if not name:
            continue
        kind = _first(it, ["category", "kind", "type"])
        kind = " / ".join(_tags(kind)) if not isinstance(kind, str) else _text(kind)
        out.append(dict(
            kind=kind or "Film",
            name=name,
            desc=_text(_first(it, ["description", "body", "copy", "text"])),
            image=_url_of(_first(it, ["thumbnail", "image", "eyecatch"])),
            video=_url_of(_first(it, ["video", "videoUrl", "movie"])),
            link=_text(_first(it, ["url", "link", "youtubeUrl"])),
            vertical=bool(it.get("vertical") or it.get("isVertical")),
        ))
    return out


def load_works() -> tuple[list[dict] | None, list[dict] | None]:
    """制作実績を microCMS から取得する。未設定・0件なら None（＝既存の内容を使う）。"""
    domain = os.environ.get("MICROCMS_SERVICE_DOMAIN", "").strip()
    api_key = os.environ.get("MICROCMS_API_KEY", "").strip()
    if not (domain and api_key):
        return None, None

    web_raw = fetch_raw(domain, api_key, WORKS_WEB_ENDPOINT, orders="", required=False)
    film_raw = fetch_raw(domain, api_key, WORKS_FILM_ENDPOINT, orders="", required=False)

    web = normalise_web_works(web_raw) or None
    film = normalise_film_works(film_raw) or None
    return web, film

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ARTICLE — 静的サイトビルダー

使い方:  python3 _build/build.py
        （article-site フォルダの直下で実行してください）

生成するもの
  /index.html                 TOP
  /service/index.html         SERVICE
  /works/index.html           WORKS
  /about/index.html           ABOUT
  /column/index.html          COLUMN 一覧
  /column/{slug}/index.html   記事詳細（microCMSの記事ごとに1ページ）
  /contact/index.html         CONTACT
  /404.html
  /sitemap.xml
  /robots.txt

文言を直したいときは `_build/content.py` を編集して、このスクリプトを再実行してください。
記事（COLUMN / NEWS）は microCMS 側で管理します。
"""
from __future__ import annotations

import html
import json as _json
import os
import pathlib
import re
import shutil
import sys
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import content as C  # noqa: E402
from cms import BuildError, is_production, load_articles, load_works  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent

SITE_URL = (os.environ.get("SITE_URL") or C.DEFAULT_SITE_URL).rstrip("/")
OGP_DEFAULT = "/assets/ogp-default.png"
LOGO = "/assets/a-symbol-lime.png"

# 本番ビルドか（True なら サンプルの実績・お客様の声を一切出力しません）
IS_PROD = is_production()


def drop_samples(items):
    """本番ビルドでは sample=True の項目を除外する。"""
    return [i for i in items if not i.get("sample")] if IS_PROD else list(items)


# 制作実績。microCMS が設定されていれば main() で差し替わります。
WEB_WORKS = C.WEB_WORKS
FILM_WORKS = C.FILM_WORKS


# ================================================================ helpers
def esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def abs_url(path: str) -> str:
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path
    return SITE_URL + ("" if path.startswith("/") else "/") + path


def fmt_date(dt: datetime) -> str:
    return dt.strftime("%Y.%m.%d")


def iso_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def iso_full(dt: datetime) -> str:
    return dt.isoformat()


def strip_tags(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def clip(s: str, n: int = 120) -> str:
    s = strip_tags(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def jsonld(obj) -> str:
    """JSON-LD を安全に埋め込む（"</script>" 対策込み）。"""
    body = _json.dumps(obj, ensure_ascii=False, indent=2)
    body = body.replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{body}\n</script>'


# ================================================================ shell
def nav_items(current, indent, mobile=False):
    """ナビのリンク一覧。NAV_SUB に登録がある項目にはサブメニューを付ける。

    PC（ヘッダー）… <div class="has-sub"> で包み、カーソルを合わせると下に出る
    スマホ（オーバーレイ）… 親リンクの下に小さめのリンクとして並べる
    """
    rows = []
    subs = getattr(C, "NAV_SUB", {})
    for href, jp, en in C.NAV:
        cls = ' class="is-current"' if href == current else ""
        aria = ' aria-current="page"' if href == current else ""
        link = f'<a href="{href}"{cls}{aria}><span class="jp">{jp}</span><span class="en">{en}</span></a>'
        sub = subs.get(href)
        if not sub:
            rows.append(indent + link)
            continue
        if mobile:
            rows.append(indent + link)
            rows.append(f'{indent}<div class="nav-sub">')
            for shref, sjp, sen in sub:
                rows.append(f'{indent}  <a href="{shref}"><span class="jp">{sjp}</span><span class="en">{sen}</span></a>')
            rows.append(f'{indent}</div>')
        else:
            rows.append(f'{indent}<div class="has-sub">')
            rows.append(f'{indent}  {link}')
            rows.append(f'{indent}  <div class="gnav-sub" aria-label="{esc(jp)}のサブメニュー">')
            for shref, sjp, sen in sub:
                rows.append(f'{indent}    <a href="{shref}"><span class="jp">{sjp}</span><span class="en">{sen}</span></a>')
            rows.append(f'{indent}  </div>')
            rows.append(f'{indent}</div>')
    return "\n".join(rows)


def head(title, desc, current, canonical="", og_image="", og_type="website",
         extra_head="", noindex=False):
    """全ページ共通の <head> ～ ヘッダー部分。"""
    og_image = og_image or OGP_DEFAULT
    can = abs_url(canonical) if canonical else ""
    parts = [f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">"""]
    if noindex:
        parts.append('<meta name="robots" content="noindex">')
    if can:
        parts.append(f'<link rel="canonical" href="{esc(can)}">')
    parts.append(f"""<meta property="og:site_name" content="{esc(C.SITE_NAME)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="{esc(og_type)}">
<meta property="og:locale" content="ja_JP">""")
    if can:
        parts.append(f'<meta property="og:url" content="{esc(can)}">')
    parts.append(f"""<meta property="og:image" content="{esc(abs_url(og_image))}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<meta name="twitter:image" content="{esc(abs_url(og_image))}">
<link rel="icon" href="/assets/a-symbol-lime.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Inter:wght@400;500;600;700&family=Noto+Sans+JP:wght@400;500;700;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css">{extra_head}
</head>
<body>

<div id="loader" aria-hidden="true">
  <img class="a" src="/assets/a-symbol-lime.png" alt="">
  <div class="bar"></div>
</div>

<header>
  <a class="logo" href="/" aria-label="ARTICLE トップへ">
    <img class="a-light" src="/assets/a-symbol-mono.png" alt="" width="28" height="28">
    <img class="a-dark" src="/assets/a-symbol-dark.png" alt="" width="28" height="28">
    <span>ARTICLE</span>
  </a>
  <nav class="gnav" aria-label="グローバルナビゲーション">
{nav_items(current, "    ")}
  </nav>
  <button class="menu-btn" id="menuBtn" aria-label="メニューを開く" aria-expanded="false" aria-controls="navOverlay">Menu</button>
</header>

<div id="navOverlay" aria-label="メニュー">
  <button class="close" aria-label="メニューを閉じる">Close</button>
  <a class="nav-top" href="/"><span class="jp">トップ</span><span class="en">Top</span></a>
{nav_items(current, "  ", mobile=True)}
</div>
""")
    return "\n".join(parts)


def footer(scripts="", jsonld_blocks=""):
    links = "\n".join(
        f'      <a href="{href}">{jp}<span>{en}</span></a>' for href, jp, en in C.NAV
    )
    # "ARTICLE" → "ARTICLE." / "ARTICLE Inc." → "ARTICLE Inc." （ピリオドの重複を防ぐ）
    copy_name = C.BRAND_EN if C.BRAND_EN.endswith(".") else C.BRAND_EN + "."
    return f"""
<footer data-bg="dark">
  <div class="cols">
    <div class="brand">
      <img src="/assets/a-symbol-lime.png" alt="ARTICLE">
      <p>{C.FOOTER_TAGLINE}</p>
    </div>
    <nav aria-label="フッターナビゲーション">
      <a href="/">トップ<span>Top</span></a>
{links}
    </nav>
  </div>
  <div class="base">
    <span>&copy; {C.COPY_YEAR} {copy_name} All rights reserved.</span>
    <span>企業の魅力を クリエイティブで 形にする</span>
  </div>
</footer>
{jsonld_blocks}
<script src="/assets/app.js" defer></script>{scripts}
</body>
</html>
"""


MARQUEE = """
<div class="marquee" data-bg="dark" aria-hidden="true">
  <div class="track">
    <div class="mq-group"><span>Web <i>&mdash;</i> Film <i>&mdash;</i> ARTICLE <i>&mdash;</i> 相模原 <i>&mdash;</i></span><span>Web <i>&mdash;</i> Film <i>&mdash;</i> ARTICLE <i>&mdash;</i> 相模原 <i>&mdash;</i></span><span>Web <i>&mdash;</i> Film <i>&mdash;</i> ARTICLE <i>&mdash;</i> 相模原 <i>&mdash;</i></span><span>Web <i>&mdash;</i> Film <i>&mdash;</i> ARTICLE <i>&mdash;</i> 相模原 <i>&mdash;</i></span><span>Web <i>&mdash;</i> Film <i>&mdash;</i> ARTICLE <i>&mdash;</i> 相模原 <i>&mdash;</i></span><span>Web <i>&mdash;</i> Film <i>&mdash;</i> ARTICLE <i>&mdash;</i> 相模原 <i>&mdash;</i></span></div>
    <div class="mq-group"><span>Web <i>&mdash;</i> Film <i>&mdash;</i> ARTICLE <i>&mdash;</i> 相模原 <i>&mdash;</i></span><span>Web <i>&mdash;</i> Film <i>&mdash;</i> ARTICLE <i>&mdash;</i> 相模原 <i>&mdash;</i></span><span>Web <i>&mdash;</i> Film <i>&mdash;</i> ARTICLE <i>&mdash;</i> 相模原 <i>&mdash;</i></span><span>Web <i>&mdash;</i> Film <i>&mdash;</i> ARTICLE <i>&mdash;</i> 相模原 <i>&mdash;</i></span><span>Web <i>&mdash;</i> Film <i>&mdash;</i> ARTICLE <i>&mdash;</i> 相模原 <i>&mdash;</i></span><span>Web <i>&mdash;</i> Film <i>&mdash;</i> ARTICLE <i>&mdash;</i> 相模原 <i>&mdash;</i></span></div>
  </div>
</div>
"""


def cta_lime():
    return """
<section class="cta-lime" data-bg="light">
  <div class="sec-cta">
    <h3 class="anton rv">Start<br>a Project<span class="q">.</span></h3>
    <div class="side rv">
      <p>「こんなことできる？」の段階でも大丈夫です。まずはやりたいことを聞かせてください。</p>
      <a class="btn-solid" href="/contact/">お問い合わせ &mdash; Contact <span class="ar">&rarr;</span></a>
    </div>
  </div>
</section>
"""


def price_band():
    notes = "".join(f"\n        <li>{n}</li>" for n in C.PRICE_NOTES)
    return f"""
<section class="price" id="price" data-bg="dark" aria-label="料金の目安">
  <div class="price-inner">
    <div class="price-head">
      <p class="eyebrow rv">Price &mdash; 料金の目安</p>
      <p class="price-num rv"><span class="from">From</span><b>&yen;40,000</b><span class="tax">&#12316;（税別）</span></p>
      <p class="price-lead rv">{C.PRICE_LEAD}</p>
    </div>
    <div class="price-side">
      <p class="price-why rv">安くできる理由</p>
      <ul class="price-notes rv">{notes}
      </ul>
      <a class="btn-line rv" href="/contact/">見積りを相談する <span class="ar">&rarr;</span></a>
    </div>
  </div>
</section>
"""


def crumb(items):
    """パンくず（HTML）。items = [(表示名, href or None), ...]"""
    out = []
    for i, (label, href) in enumerate(items):
        if i:
            out.append("<span>/</span>")
        if href:
            out.append(f'<a href="{esc(href)}">{esc(label)}</a>')
        else:
            out.append(f"<span>{esc(label)}</span>")
    return '<p class="crumb">' + "".join(out) + "</p>"


def crumb_jsonld(items):
    """パンくずの構造化データ。items = [(表示名, パス), ...]"""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": label, "item": abs_url(path)}
            for i, (label, path) in enumerate(items, 1)
        ],
    }


PUBLISHER = {
    "@type": "Organization",
    "name": C.SITE_NAME,
    "url": SITE_URL + "/",
    "logo": {"@type": "ImageObject", "url": abs_url(LOGO)},
}


# ================================================================ 記事カード
def article_card(a, reveal=True):
    cat = a["category"]
    rv = " rv" if reveal else ""
    if a["eyecatch"]:
        src = a["eyecatch"]["url"]
        if src.startswith("http"):
            src += "?w=760&fm=webp"
        thumb = f'<img src="{esc(src)}" alt="" loading="lazy" decoding="async">'
        thumb_cls = "col-thumb"
    else:
        thumb = '<span class="col-noimg" aria-hidden="true">ARTICLE</span>'
        thumb_cls = "col-thumb is-empty"
    return f"""    <article class="col-card{rv}" data-category="{esc(cat)}">
      <a href="/column/{esc(a['slug'])}/">
        <span class="{thumb_cls}">{thumb}</span>
        <span class="col-txt">
          <span class="col-meta">
            <span class="col-cat cat-{esc(cat.lower())}">{esc(cat)}</span>
            <time datetime="{iso_date(a['published'])}">{fmt_date(a['published'])}</time>
          </span>
          <span class="col-title">{esc(a['title'])}</span>
          <span class="col-excerpt">{esc(clip(a['excerpt'] or a['content'], 90))}</span>
        </span>
      </a>
    </article>
"""


# ================================================================ TOP
def page_index(articles):
    latest = articles[:3]
    h = head(
        "ARTICLE｜Web制作・映像制作 — 企業の魅力を、クリエイティブで形にする。",
        "ARTICLEは、神奈川県相模原市を拠点にWeb制作と映像制作を行うクリエイティブカンパニーです。"
        "SNSフォロワー5万人の運用実績。制作費は4万円から、制作期間は2週間。",
        "/", canonical="/",
    )
    h += f"""
<main>

<section class="hero" data-bg="dark" aria-label="企業の魅力を クリエイティブで 形にする">
  <video class="hero-video" autoplay muted loop playsinline preload="metadata"
         poster="/assets/hero-final-poster.jpg">
    <source src="/assets/hero-final.mp4" type="video/mp4">
  </video>
  <div class="hero-scrim" aria-hidden="true"></div>

  <div class="hero-copy">
    <p class="hero-eyebrow">{C.BRAND_EN} &mdash; Web &amp; Film</p>
    <h1 class="hero-lead">
      <span class="l"><span>企業の魅力を</span></span>
      <span class="l"><span><em>クリエイティブ</em>で</span></span>
      <span class="l"><span>形にする</span></span>
    </h1>
    <div class="hero-actions">
      <a class="btn-solid" href="/works/">実績を見る <span class="ar">&rarr;</span></a>
      <a class="btn-ghost" href="/contact/">お問い合わせ</a>
    </div>
  </div>

  <div class="hero-scroll" aria-hidden="true">SCROLL</div>
</section>
"""
    h += MARQUEE
    h += f"""
<section class="services theme-light" data-bg="light" aria-label="事業紹介">
  <div class="sec-intro">
    <p class="no rv"><span class="n">01</span> Business &mdash; 事業紹介</p>
    <h2 class="anton rv">What<br><span class="stroke">We Do</span><span class="accent">.</span></h2>
    <p class="jp rv">{C.SERVICE_LEAD}</p>
  </div>

  <div class="svc-list">
"""
    for s in C.SERVICES[:2]:
        tags = "".join(f"<span>{t}</span>" for t in s["tags"])
        h += f"""    <article class="svc">
      <div class="svc-head">
        <p class="svc-no rv">Service <b>{s['no']}</b></p>
        <h3 class="svc-title rv">{s['en']}<span class="jp-name">{s['jp']}</span></h3>
      </div>
      <div class="svc-body">
        <p class="rv">{s['body']}</p>
        <div class="svc-tags rv">{tags}</div>
        <div class="svc-links rv"><a class="btn-line" href="{s['link'][0]}">{s['link'][1]} <span class="ar">&rarr;</span></a></div>
      </div>
    </article>
"""
    h += """  </div>
  <div class="svc-more">
    <a class="btn-line rv" href="/service/">SNS支援・料金・制作の流れを見る <span class="ar">&rarr;</span></a>
  </div>
</section>
"""
    h += price_band()

    h += """
<section class="col-latest theme-light" data-bg="light" aria-label="最新の記事">
  <div class="sec-intro">
    <p class="no rv"><span class="n">03</span> Column &amp; News &mdash; 最新記事</p>
    <h2 class="anton rv">Latest<br><span class="stroke">Posts</span><span class="accent">.</span></h2>
    <p class="jp rv">お役立ち記事とARTICLEからのお知らせを掲載しています。</p>
  </div>
  <div class="col-grid">
"""
    if latest:
        for a in latest:
            h += article_card(a)
    else:
        h += '    <p class="col-empty">記事は準備中です。</p>\n'
    h += """  </div>
  <div class="col-more">
    <a class="btn-line rv" href="/column/">記事をすべて見る &mdash; Column <span class="ar">&rarr;</span></a>
  </div>
</section>
"""
    h += f"""
<section class="about" id="about" data-bg="dark" aria-label="ARTICLEについて">
  <img class="asym" src="/assets/a-symbol-mono.png" alt="" aria-hidden="true">
  <p class="eyebrow rv">About Article</p>
  <h2 class="anton rv">About<br>Article<span style="color:var(--lime)">.</span></h2>
  <p class="rv">{C.ABOUT_LEAD}</p>
  <p class="vision rv">{C.ABOUT_VISION}</p>
  <div class="corp rv">
    <span>{C.BRAND_EN}</span><span>{C.REPRESENTATIVE}</span><span>Sagamihara, Japan</span>
  </div>
  <div class="about-more rv"><a class="btn-line" href="/about/">ARTICLEについて詳しく見る <span class="ar">&rarr;</span></a></div>
</section>

<nav class="nextnav" data-bg="dark" aria-label="サイト内の主要ページ">
  <a href="/service/"><span class="idx">01</span><span class="nm">サービス</span><span class="en">Service &rarr;</span></a>
  <a href="/works/"><span class="idx">02</span><span class="nm">実績</span><span class="en">Works &rarr;</span></a>
  <a href="/about/"><span class="idx">03</span><span class="nm">ARTICLEについて</span><span class="en">About &rarr;</span></a>
  <a href="/column/"><span class="idx">04</span><span class="nm">コラム</span><span class="en">Column &rarr;</span></a>
</nav>
"""
    h += cta_lime()
    h += "</main>\n"

    ld = jsonld({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": C.SITE_NAME,
        "url": SITE_URL + "/",
        "publisher": PUBLISHER,
    })
    return h + footer(jsonld_blocks=ld)


# ================================================================ SERVICE
def svc_items(s):
    """サービスの「支援内容」リスト（content.py の items）。無ければ空文字。"""
    items = s.get("items")
    if not items:
        return ""
    rows = "".join(
        f'\n          <li><strong>{esc(t)}</strong><span>{esc(d)}</span></li>' for t, d in items
    )
    return f'\n        <ul class="svc-items rv">{rows}\n        </ul>'


def page_service(articles):
    h = head(
        "サービス｜ARTICLE — Web制作・映像制作・SNS / 料金と制作の流れ",
        "ARTICLEのサービス内容・料金・制作の流れ・よくある質問。"
        "ホームページ制作、映像制作、SNS支援を4万円から、制作期間2週間の目安で承ります。",
        "/service/", canonical="/service/",
    )
    h += f"""
<main>

<section class="page-hero" data-bg="dark">
  <div class="ph-bg ph-service" aria-hidden="true"></div>
  {crumb([("Top", "/"), ("サービス / Service", None)])}
  <div class="inner">
    <p class="no">01 / Service</p>
    <h1 class="anton">What<br><span class="stroke">We Do</span><span class="accent">.</span></h1>
    <div class="tags"><span>Web</span><span>Film</span><span>Social</span><span>Price</span><span>Process</span><span>FAQ</span></div>
    <p class="jp">{C.SERVICE_LEAD}</p>
  </div>
</section>

<section class="theme-light" data-bg="light" aria-label="サービス内容">
  <div class="sec-intro">
    <p class="no rv"><span class="n">01</span> Service &mdash; サービス内容</p>
    <h2 class="anton rv">Our<br><span class="stroke">Service</span><span class="accent">.</span></h2>
    <p class="jp rv">Web・映像・SNS。ひとつでも、まとめてでもご依頼いただけます。</p>
  </div>

  <div class="svc-list">
"""
    anchors = {"01": "web", "02": "film", "03": "social"}
    for s in C.SERVICES:
        tags = "".join(f"<span>{t}</span>" for t in s["tags"])
        h += f"""    <article class="svc" id="{anchors.get(s['no'], '')}">
      <div class="svc-head">
        <p class="svc-no rv">Service <b>{s['no']}</b></p>
        <h3 class="svc-title rv">{s['en']}<span class="jp-name">{s['jp']}</span></h3>
      </div>
      <div class="svc-body">
        <p class="rv">{s['body']}</p>{svc_items(s)}
        <div class="svc-tags rv">{tags}</div>
        <div class="svc-links rv"><a class="btn-line" href="{s['link'][0]}">{s['link'][1]} <span class="ar">&rarr;</span></a></div>
      </div>
    </article>
"""
    h += """  </div>
</section>
"""
    h += price_band()

    h += """
<section class="pr-wrap" data-bg="dark" aria-label="制作の流れ">
  <div class="sec-intro">
    <p class="no rv"><span class="n">03</span> Process &mdash; 制作の流れ</p>
    <h2 class="anton rv">How<br><span class="stroke">We Work</span><span class="accent">.</span></h2>
    <p class="jp rv">お問い合わせから公開まで、6つのステップで進みます。制作は2週間。最短で1ヶ月ほどで公開できます。</p>
  </div>
  <div class="pr-list" id="process">
"""
    for i, p in enumerate(C.PROCESS, 1):
        items = "".join(f"<li>{x}</li>" for x in p["items"])
        h += f"""  <article class="pr-step">
    <div class="pr-num" aria-hidden="true"><span class="dot">{i:02d}</span><span class="line"></span></div>
    <div class="pr-head">
      <p class="pr-en rv">Step {i:02d} &mdash; {p['en']}</p>
      <h3 class="pr-title rv">{p['title']}</h3>
      <span class="pr-term rv">目安 {p['term']}</span>
    </div>
    <div class="pr-body">
      <p class="rv">{p['body']}</p>
      <ul class="rv">{items}</ul>
    </div>
  </article>
"""
    h += f"""  </div>
</section>

<section class="notice" data-bg="light">
  <p>{C.PROCESS_NOTE}</p>
</section>
"""

    h += """
<section class="faq-sec theme-light" data-bg="light" aria-label="よくある質問">
  <div class="sec-intro">
    <p class="no rv"><span class="n">04</span> FAQ &mdash; よくある質問</p>
    <h2 class="anton rv">Any<br><span class="stroke">Questions</span><span class="accent">?</span></h2>
    <p class="jp rv">ここにない疑問も、お問い合わせからお気軽にどうぞ。</p>
  </div>
  <div class="faq-list">
"""
    for i, f in enumerate(C.FAQ, 1):
        h += f"""    <details class="faq-item rv">
      <summary><span class="faq-q" aria-hidden="true">Q{i:02d}</span><span class="faq-t">{f['q']}</span></summary>
      <div class="faq-a"><p>{f['a']}</p></div>
    </details>
"""
    h += """  </div>
</section>
"""
    h += cta_lime()
    h += "</main>\n"

    ld = jsonld(crumb_jsonld([("トップ", "/"), ("サービス", "/service/")])) + "\n" + jsonld({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": f["q"],
             "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
            for f in C.FAQ
        ],
    })
    return h + footer(jsonld_blocks=ld)


# ================================================================ WORKS
PER_PAGE = 9  # 1ページに表示する実績の件数（WEB / FILM 共通）


def cms_img(url, w):
    """microCMS の画像は、幅とWebP変換のパラメータを付けて軽くする。"""
    if not url:
        return ""
    if url.startswith("http") and "?" not in url:
        return url + "?w=" + str(w) + "&fm=webp"
    return url


def img_tag(url, alt, cls, base_w=760, ratio=0.625):
    """サムネイル用の img。microCMS の画像なら 1x / 2x を出し分ける。"""
    src = cms_img(url, base_w)
    srcset = ""
    if url.startswith("http") and "?" not in url:
        srcset = (' srcset="' + esc(cms_img(url, base_w)) + ' 1x, '
                  + esc(cms_img(url, base_w * 2)) + ' 2x"')
    return ('<img class="' + cls + '" src="' + esc(src) + '"' + srcset
            + ' alt="' + esc(alt) + '"'
            + ' width="' + str(base_w) + '" height="' + str(int(base_w * ratio)) + '"'
            + ' loading="lazy" decoding="async">')


def pager(kind, total, label):
    """ページ送り。JavaScriptが有効なときだけ表示します（JSが hidden を外します）。"""
    if total <= PER_PAGE:
        return ""
    return (
        '<nav class="wk-pager" data-pager="' + kind + '" aria-label="' + esc(label) + '" hidden>\n'
        '      <button type="button" class="wk-pg-arrow" data-nav="prev">'
        '<span class="ar" aria-hidden="true">&larr;</span> PREV</button>\n'
        '      <ol class="wk-pg-nums"></ol>\n'
        '      <button type="button" class="wk-pg-arrow" data-nav="next">'
        'NEXT <span class="ar" aria-hidden="true">&rarr;</span></button>\n'
        '    </nav>'
    )


# ---------------------------------------------------------------- WEBカード
def web_card(w, i):
    name = w.get("name") or ""
    client = w.get("jp") or ""
    url = (w.get("url") or "").strip()
    thumb = (w.get("thumb") or "").strip()
    ghost = w.get("ghost") or name
    desc = w.get("copy") or ""
    tags = "".join('<span>' + esc(t) + '</span>' for t in (w.get("tags") or [])[:4])
    host = re.sub(r"^https?://", "", url).rstrip("/")
    page = i // PER_PAGE + 1

    # サムネイルは常に img 要素で出力します（スマホでも確実に表示されるように）。
    # PCではこの上に、実サイトの iframe を JavaScript が重ねます。
    if thumb:
        alt = (client or name) + "のWebサイト スクリーンショット"
        media = img_tag(thumb, alt, "wk-thumb", 760, 0.625)
    else:
        media = '<span class="wk-noimg" aria-hidden="true">' + esc(ghost) + '</span>'

    preview = ' data-preview="' + esc(url) + '"' if url else ""
    bar = ('<span class="wk-bar" aria-hidden="true"><i></i><i></i><i></i><b>'
           + esc(host) + '</b></span>') if host else ""
    hover = ('<span class="wk-hover" aria-hidden="true"><span>View Site</span></span>'
             if url else "")

    rows = ['<span class="wk-no">Project <b>' + ("%02d" % (i + 1)) + '</b></span>',
            '<span class="wk-name">' + esc(name) + '</span>']
    if client:
        rows.append('<span class="wk-client">' + esc(client) + '</span>')
    if tags:
        rows.append('<span class="wk-tags">' + tags + '</span>')
    if desc:
        rows.append('<span class="wk-desc">' + esc(desc) + '</span>')
    if url:
        rows.append('<span class="wk-cta">Visit Website '
                    '<i aria-hidden="true">&#8599;</i></span>')
    body = ('<span class="wk-body">\n          '
            + '\n          '.join(rows) + '\n        </span>')

    shot = ('<span class="wk-shot"' + preview + '>\n          ' + bar
            + '\n          <span class="wk-frame">' + media + '</span>\n          '
            + hover + '\n        </span>')

    if url:
        open_tag = ('<a class="wk-link" href="' + esc(url) + '" target="_blank" rel="noopener"'
                    ' aria-label="' + esc(client or name) + 'のサイトを新しいタブで開く">')
        close_tag = "</a>"
    else:
        open_tag = '<div class="wk-link is-static">'
        close_tag = "</div>"

    return ('      <article class="wk-card rv" data-page="' + str(page) + '">\n        '
            + open_tag + '\n        ' + shot + '\n        ' + body + '\n        '
            + close_tag + '\n      </article>\n')


# ---------------------------------------------------------------- FILMカード
def film_card(f, i):
    name = f.get("name") or ""
    kind = f.get("kind") or ""
    desc = f.get("desc") or ""
    video = (f.get("video") or "").strip()
    link = (f.get("link") or "").strip()
    image = (f.get("image") or f.get("poster") or "").strip()
    vertical = bool(f.get("vertical"))
    page = i // PER_PAGE + 1
    vcls = " is-vertical" if vertical else ""

    if image:
        media = img_tag(image, name + "のサムネイル", "wk-thumb", 760, 0.5625)
    else:
        visual = f.get("visual") or "fv-corp"
        media = ('<span class="wk-ph ' + esc(visual) + '" aria-hidden="true">'
                 + esc(kind or "Film") + '</span>')

    play = '<span class="wk-play" aria-hidden="true"></span>' if video else ""
    ext = ('<span class="wk-hover" aria-hidden="true"><span>Watch</span></span>'
           if (link and not video) else "")

    rows = []
    if kind:
        rows.append('<span class="wk-kind">' + esc(kind) + '</span>')
    rows.append('<span class="wk-name">' + esc(name) + '</span>')
    if desc:
        rows.append('<span class="wk-desc">' + esc(desc) + '</span>')
    body = ('<span class="wk-body">\n          '
            + '\n          '.join(rows) + '\n        </span>')

    shot = ('<span class="wk-shot is-film' + vcls + '">\n          '
            '<span class="wk-frame">' + media + '</span>\n          '
            + play + ext + '\n        </span>')

    if video:
        vert_attr = ' data-vertical="1"' if vertical else ''
        open_tag = ('<button type="button" class="wk-link" data-video="' + esc(video) + '"'
                    ' data-title="' + esc(name) + '"' + vert_attr
                    + ' aria-label="' + esc(name) + 'の動画を再生">')
        close_tag = "</button>"
    elif link:
        open_tag = ('<a class="wk-link" href="' + esc(link) + '" target="_blank" rel="noopener"'
                    ' aria-label="' + esc(name) + 'を新しいタブで開く">')
        close_tag = "</a>"
    else:
        open_tag = '<div class="wk-link is-static">'
        close_tag = "</div>"

    return ('      <article class="wk-card wk-film rv" data-page="' + str(page) + '">\n        '
            + open_tag + '\n        ' + shot + '\n        ' + body + '\n        '
            + close_tag + '\n      </article>\n')


VIDEO_MODAL = """
<div class="vmodal" id="videoModal" hidden>
  <div class="vmodal-backdrop" data-vmodal-close></div>
  <div class="vmodal-box" role="dialog" aria-modal="true" aria-labelledby="vmodalTitle">
    <div class="vmodal-head">
      <p class="vmodal-title" id="vmodalTitle"></p>
      <button type="button" class="vmodal-close" data-vmodal-close aria-label="動画を閉じる">
        Close <span aria-hidden="true">&times;</span>
      </button>
    </div>
    <div class="vmodal-stage">
      <video id="vmodalVideo" controls playsinline preload="none"></video>
    </div>
  </div>
</div>
"""


def page_works(articles):
    has_voice = bool(drop_samples(C.VOICES))
    webs = list(WEB_WORKS)
    films = drop_samples(FILM_WORKS)

    h = head(
        "実績｜ARTICLE — HP制作実績・映像制作実績"
        + ("・お客様の声" if has_voice else ""),
        "ARTICLEのHP制作実績と映像制作実績"
        + ("、お客様の声。" if has_voice else "。")
        + "相模原を中心に、コーポレートサイトやブランドサイト、SNS動画などを制作しています。",
        "/works/", canonical="/works/",
    )
    voice_tag = "<span>Voice</span>" if has_voice else ""
    h += f"""
<main>

<section class="page-hero" data-bg="dark">
  <div class="ph-bg ph-works" aria-hidden="true"></div>
  {crumb([("Top", "/"), ("実績 / Works", None)])}
  <div class="inner">
    <p class="no">02 / Works</p>
    <h1 class="anton">Our<br><span class="stroke">Works</span><span class="accent">.</span></h1>
    <div class="tags"><span>Website</span><span>Landing Page</span><span>Corporate</span><span>Social Film</span><span>Thumbnail</span>{voice_tag}</div>
    <p class="jp">これまでにつくってきたもの。WEBと映像、それぞれの実績をご覧いただけます。</p>
  </div>
</section>

<section class="wk-sec theme-light" id="works" data-bg="light" aria-label="制作実績">
  <div class="wk-tabbar" hidden>
    <div class="wk-tabs" role="tablist" aria-label="実績の種類">
      <button type="button" role="tab" id="tab-web" aria-controls="panel-web"
              aria-selected="true" data-tab="web">WEB<span class="jp">HP制作実績</span></button>
      <button type="button" role="tab" id="tab-film" aria-controls="film"
              aria-selected="false" tabindex="-1" data-tab="film">FILM<span class="jp">映像制作実績</span></button>
    </div>
    <p class="wk-count" data-count></p>
  </div>

  <div class="wk-panel" id="panel-web" data-tab="web" role="tabpanel"
       aria-labelledby="tab-web" tabindex="0">
    <div class="sec-intro">
      <p class="no rv"><span class="n">01</span> Web &mdash; HP制作実績</p>
      <h2 class="anton rv">Web<br><span class="stroke">Works</span><span class="accent">.</span></h2>
      <p class="jp rv">コーポレートサイトからプロジェクトサイトまで。実際に公開されているサイトをご覧いただけます。</p>
    </div>
    <div class="wk-grid" id="webWorks" data-source="html">
"""
    if webs:
        for i, w in enumerate(webs):
            h += web_card(w, i)
    else:
        h += '      <p class="wk-empty">実績は準備中です。</p>\n'

    h += "    </div>\n    " + pager("web", len(webs), "HP制作実績のページ送り") + """
  </div>

  <div class="wk-panel" id="film" data-tab="film" role="tabpanel"
       aria-labelledby="tab-film" tabindex="0">
    <div class="sec-intro">
      <p class="no rv"><span class="n">02</span> Film &mdash; 映像制作実績</p>
      <h2 class="anton rv">Film<br><span class="stroke">Works</span><span class="accent">.</span></h2>
      <p class="jp rv">SNSショートからサムネイルデザインまで。Web制作とあわせてご依頼いただけます。</p>
    </div>
    <div class="wk-grid is-film" id="filmWorks" data-source="html">
"""
    if films:
        for i, f in enumerate(films):
            h += film_card(f, i)
    else:
        h += '      <p class="wk-empty">実績は準備中です。</p>\n'

    h += "    </div>\n    " + pager("film", len(films), "映像制作実績のページ送り") + """
  </div>
</section>
"""

    # ---- お客様の声（本番ビルドではサンプルを出力しない） ----
    voices = drop_samples(C.VOICES)
    if voices:
        h += """
<section class="theme-light" id="voice" data-bg="light" aria-label="お客様の声">
  <div class="sec-intro">
    <p class="no rv"><span class="n">03</span> Voice &mdash; お客様の声</p>
    <h2 class="anton rv">Client<br><span class="stroke">Voice</span><span class="accent">.</span></h2>
    <p class="jp rv">ご依頼いただいたお客様からいただいた言葉を紹介します。</p>
  </div>
</section>
"""
        if any(v.get("sample") for v in voices) and C.VOICE_NOTICE:
            h += '\n<section class="notice" data-bg="light">\n  <p>' + C.VOICE_NOTICE + '</p>\n</section>\n'
        h += '\n<div class="vo-grid" data-bg="light">\n'
        for v in voices:
            tag = '\n    <span class="vo-tag">Sample</span>' if v.get("sample") else ""
            h += f"""  <article class="vo-card rv">{tag}
    <p class="vo-mark" aria-hidden="true">&ldquo;</p>
    <p class="vo-body">{v['body']}</p>
    <div class="vo-meta">
      <p class="vo-who">{v['who']}</p>
      <p class="vo-sub">{v['sub']}</p>
    </div>
  </article>
"""
        h += "</div>\n"

    h += cta_lime()
    h += "</main>\n"
    h += VIDEO_MODAL

    ld = jsonld(crumb_jsonld([("トップ", "/"), ("実績", "/works/")]))
    return h + footer(jsonld_blocks=ld)


# ================================================================ ABOUT
def page_about(articles):
    h = head(
        "ARTICLEについて｜ARTICLE — 強み・会社概要・対応地域",
        "神奈川県相模原市を拠点に、Web制作と映像制作を行うARTICLEについて。"
        "選ばれる5つの強み、会社概要、対応地域をご紹介します。",
        "/about/", canonical="/about/",
    )
    h += f"""
<main>

<section class="page-hero" data-bg="dark">
  <div class="ph-bg ph-about" aria-hidden="true"></div>
  {crumb([("Top", "/"), ("ARTICLEについて / About", None)])}
  <div class="inner">
    <p class="no">03 / About</p>
    <h1 class="anton">Why<br><span class="stroke">Article</span><span class="accent">.</span></h1>
    <div class="tags"><span>Local</span><span>Price</span><span>One Stop</span><span>SNS Marketing</span><span>After Launch</span></div>
    <p class="jp">ARTICLEがどんな会社で、なぜ選ばれているのかをまとめました。</p>
  </div>
</section>

<section class="about" data-bg="dark" aria-label="ARTICLEについて">
  <img class="asym" src="/assets/a-symbol-mono.png" alt="" aria-hidden="true">
  <p class="eyebrow rv">About Article</p>
  <h2 class="anton rv">About<br>Article<span style="color:var(--lime)">.</span></h2>
  <p class="rv">{C.ABOUT_LEAD}</p>
  <p class="vision rv">{C.ABOUT_VISION}</p>
  <div class="corp rv">
    <span>{C.BRAND_EN}</span><span>{C.REPRESENTATIVE}</span><span>Sagamihara, Japan</span>
  </div>
</section>

<section class="theme-light" data-bg="light" aria-label="ARTICLEの強み">
  <div class="sec-intro">
    <p class="no rv"><span class="n">01</span> Strengths &mdash; ARTICLEの強み</p>
    <h2 class="anton rv">Five<br><span class="stroke">Reasons</span><span class="accent">.</span></h2>
    <p class="jp rv">ARTICLEにご依頼いただく理由を、5つにまとめました。</p>
  </div>
</section>

<section class="st-list" id="strengths" data-bg="light" aria-label="ARTICLEの強み 一覧">
"""
    for i, s in enumerate(C.STRENGTHS, 1):
        points = "".join(f"<span>{p}</span>" for p in s["points"])
        h += f"""  <article class="st-item">
    <div class="st-head">
      <p class="st-no rv">Point <b>{i:02d}</b></p>
      <p class="st-en rv">{s['en']}</p>
      <h3 class="st-title rv">{s['title']}</h3>
    </div>
    <div class="st-body">
      <p class="rv">{s['body']}</p>
      <div class="st-points rv">{points}</div>
    </div>
  </article>
"""
    h += "</section>\n"

    msg = C.MESSAGE
    if msg.get("body"):
        paras = "".join(f'\n      <p class="rv">{p}</p>' for p in msg["body"])
        sign = ""
        if msg.get("name"):
            role = f'<span class="ms-role">{msg["role"]}</span>' if msg.get("role") else ""
            sign = f'\n      <p class="ms-sign rv">{role}<span class="ms-name">{msg["name"]}</span></p>'
        h += f"""
<section class="msg-sec" id="message" data-bg="dark" aria-label="代表メッセージ">
  <div class="msg-inner">
    <div class="msg-head">
      <p class="eyebrow rv">Message &mdash; 代表メッセージ</p>
      <h2 class="anton rv">Our<br>Message<span style="color:var(--lime)">.</span></h2>
    </div>
    <div class="msg-body">{paras}{sign}
    </div>
  </div>
</section>
"""
    else:
        h += """
<!-- 代表メッセージ：原稿が未入稿のため非表示にしています（README.md「要確認項目」参照）。
     _build/content.py の MESSAGE に文章を入れて再ビルドすると、ここに表示されます。 -->
"""

    rows = "".join(
        f'\n      <div class="cp-row rv"><dt>{esc(k)}</dt><dd>{v}</dd></div>'
        for k, v in C.COMPANY
    )
    areas = "".join(f"<span>{esc(a)}</span>" for a in C.AREAS)
    h += f"""
<section class="cp-sec theme-light" data-bg="light" aria-label="会社概要">
  <div class="sec-intro">
    <p class="no rv"><span class="n">02</span> Company &mdash; 会社概要</p>
    <h2 class="anton rv">Company<br><span class="stroke">Profile</span><span class="accent">.</span></h2>
  </div>
  <div class="cp-wrap">
    <dl class="cp-list">{rows}
    </dl>
  </div>
</section>

<section class="area-sec" id="area" data-bg="dark" aria-label="対応地域">
  <div class="area-inner">
    <div class="area-head">
      <p class="eyebrow rv">Area &mdash; 対応地域</p>
      <h2 class="anton rv">Where<br>We Work<span style="color:var(--lime)">.</span></h2>
    </div>
    <div class="area-body">
      <p class="rv">{C.AREA_LEAD}</p>
      <div class="area-tags rv">{areas}</div>
      <a class="btn-line rv" href="/contact/">エリア外かどうか相談する <span class="ar">&rarr;</span></a>
    </div>
  </div>
</section>

<section class="cta-dark" data-bg="dark">
  <div class="sec-cta">
    <h3 class="anton rv">See<br>Our Works<span class="q">.</span></h3>
    <div class="side rv">
      <p>言葉より、つくったものを見ていただくのがいちばん早いかもしれません。</p>
      <a class="btn-solid" href="/works/">実績を見る &mdash; Works <span class="ar">&rarr;</span></a>
    </div>
  </div>
</section>
"""
    h += cta_lime()
    h += "</main>\n"

    org = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": C.SITE_NAME,
        "url": SITE_URL + "/",
        "logo": abs_url(LOGO),
        "address": {
            "@type": "PostalAddress",
            "addressRegion": "神奈川県",
            "addressLocality": "相模原市",
            "addressCountry": "JP",
        },
    }
    # 英字表記が名称と同じときは alternateName を出さない（重複するだけのため）
    if C.SITE_NAME_EN and C.SITE_NAME_EN != C.SITE_NAME:
        org["alternateName"] = C.SITE_NAME_EN

    ld = (jsonld(crumb_jsonld([("トップ", "/"), ("ARTICLEについて", "/about/")]))
          + "\n" + jsonld(org))
    return h + footer(jsonld_blocks=ld)


# ================================================================ COLUMN 一覧
def page_column(articles):
    n_all = len(articles)
    n_col = sum(1 for a in articles if a["category"] == "COLUMN")
    n_news = sum(1 for a in articles if a["category"] == "NEWS")

    h = head(
        "コラム・お知らせ｜ARTICLE",
        "ホームページ制作、映像制作、SNS、地域企業向けのお役立ち記事と、"
        "ARTICLEからのお知らせを掲載しています。",
        "/column/", canonical="/column/",
    )
    h += f"""
<main>

<section class="page-hero" data-bg="dark">
  <div class="ph-bg ph-column" aria-hidden="true"></div>
  {crumb([("Top", "/"), ("コラム / Column", None)])}
  <div class="inner">
    <p class="no">04 / Column</p>
    <h1 class="anton">Column<br><span class="stroke">&amp; News</span><span class="accent">.</span></h1>
    <div class="tags"><span>Web</span><span>Film</span><span>Social</span><span>Local</span><span>News</span></div>
    <p class="jp">{C.COLUMN_LEAD}</p>
  </div>
</section>

<section class="col-sec theme-light" data-bg="light" aria-label="記事一覧">
  <div class="col-filter-bar">
    <div class="col-filter" role="group" aria-label="カテゴリーで絞り込む">
      <button type="button" data-filter="ALL" aria-pressed="true">ALL<span class="n">{n_all}</span></button>
      <button type="button" data-filter="COLUMN" aria-pressed="false">COLUMN<span class="n">{n_col}</span></button>
      <button type="button" data-filter="NEWS" aria-pressed="false">NEWS<span class="n">{n_news}</span></button>
    </div>
    <p class="col-filter-note">COLUMN：{C.CATEGORY_DESC['COLUMN']}<br>NEWS：{C.CATEGORY_DESC['NEWS']}</p>
  </div>

  <div class="col-grid" id="columnGrid">
"""
    if articles:
        for a in articles:
            h += article_card(a)
    else:
        h += '    <p class="col-empty">記事は準備中です。</p>\n'
    h += """  </div>
  <p class="col-empty" id="columnEmpty" hidden>このカテゴリーの記事はまだありません。</p>
</section>
"""
    h += cta_lime()
    h += "</main>\n"

    ld = jsonld(crumb_jsonld([("トップ", "/"), ("コラム", "/column/")])) + "\n" + jsonld({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "コラム・お知らせ",
        "url": abs_url("/column/"),
        "isPartOf": {"@type": "WebSite", "name": C.SITE_NAME, "url": SITE_URL + "/"},
    })
    return h + footer(jsonld_blocks=ld)


# ================================================================ 記事詳細
IMG_TAG = re.compile(r"<img\b(?![^>]*\bloading=)", re.I)
TABLE_BLOCK = re.compile(r"<table\b.*?</table>", re.I | re.S)


def prepare_body(raw: str) -> str:
    """リッチエディタのHTMLを、そのままサイトに載せられる形に整える。"""
    out = IMG_TAG.sub('<img loading="lazy" decoding="async"', raw or "")
    out = TABLE_BLOCK.sub(lambda m: f'<div class="tbl-wrap">{m.group(0)}</div>', out)
    return out


def related_of(article, articles, limit=3):
    same = [a for a in articles
            if a["slug"] != article["slug"] and a["category"] == article["category"]]
    other = [a for a in articles
             if a["slug"] != article["slug"] and a["category"] != article["category"]]
    return (same + other)[:limit]


def page_article(a, articles):
    cat = a["category"]
    cat_jp = C.CATEGORY_LABEL.get(cat, cat)
    path = f"/column/{a['slug']}/"

    title = a["seo_title"] or f"{a['title']}｜ARTICLE"
    desc = a["seo_description"] or a["excerpt"] or clip(a["content"], 110)
    og_image = a["eyecatch"]["url"] if a["eyecatch"] else OGP_DEFAULT

    h = head(
        title, desc, "/column/", canonical=path, og_image=og_image, og_type="article",
        extra_head=(
            f'\n<meta property="article:published_time" content="{esc(iso_full(a["published"]))}">'
            f'\n<meta property="article:modified_time" content="{esc(iso_full(a["modified"]))}">'
            f'\n<meta property="article:section" content="{esc(cat)}">'
        ),
    )

    if a["eyecatch"]:
        src = a["eyecatch"]["url"]
        if src.startswith("http"):
            src += "?w=1600&fm=webp"
        eyecatch = (
            '\n  <figure class="art-eyecatch rv">'
            f'<img src="{esc(src)}" alt="{esc(a["title"])}" decoding="async">'
            "</figure>"
        )
    else:
        eyecatch = ""

    h += f"""
<main class="art-main">

<article class="art">

<header class="art-head" data-bg="dark">
  <div class="ph-bg ph-article" aria-hidden="true"></div>
  {crumb([("Top", "/"), ("Column", "/column/"), (a["title"], None)])}
  <div class="art-head-inner">
    <p class="art-meta">
      <span class="col-cat cat-{esc(cat.lower())}">{esc(cat)}</span>
      <span class="art-cat-jp">{esc(cat_jp)}</span>
      <time datetime="{iso_date(a['published'])}">公開 {fmt_date(a['published'])}</time>
      <time class="art-upd" datetime="{iso_date(a['modified'])}">更新 {fmt_date(a['modified'])}</time>
    </p>
    <h1 class="art-title">{esc(a['title'])}</h1>
  </div>
</header>

<div class="art-wrap theme-light" data-bg="light">{eyecatch}
  <div class="art-body">
{prepare_body(a['content'])}
  </div>

  <div class="art-foot">
    <a class="btn-line" href="/column/"><span class="ar">&larr;</span> COLUMN一覧へ戻る</a>
  </div>
</div>

</article>
"""

    rel = related_of(a, articles)
    if rel:
        h += """
<section class="rel-sec" data-bg="dark" aria-label="関連記事">
  <div class="rel-head">
    <p class="eyebrow rv">Related &mdash; 関連記事</p>
  </div>
  <div class="col-grid is-dark">
"""
        for r in rel:
            h += article_card(r)
        h += """  </div>
</section>
"""

    h += cta_lime()
    h += "</main>\n"

    article_ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": a["title"][:110],
        "description": desc,
        "datePublished": iso_full(a["published"]),
        "dateModified": iso_full(a["modified"]),
        "author": PUBLISHER,
        "publisher": PUBLISHER,
        "mainEntityOfPage": {"@type": "WebPage", "@id": abs_url(path)},
        "articleSection": cat,
        "inLanguage": "ja",
    }
    if a["eyecatch"]:
        img = {"@type": "ImageObject", "url": abs_url(a["eyecatch"]["url"])}
        if a["eyecatch"].get("width"):
            img["width"] = a["eyecatch"]["width"]
        if a["eyecatch"].get("height"):
            img["height"] = a["eyecatch"]["height"]
        article_ld["image"] = img
    else:
        article_ld["image"] = abs_url(OGP_DEFAULT)

    ld = jsonld(article_ld) + "\n" + jsonld(
        crumb_jsonld([("トップ", "/"), ("コラム", "/column/"), (a["title"], path)])
    )
    return h + footer(jsonld_blocks=ld)


# ================================================================ CONTACT
def page_contact(articles):
    h = head(
        "お問い合わせ｜ARTICLE",
        "ARTICLEへのお問い合わせ。Web制作・映像制作・SNSのご相談、お見積りはこちらから。",
        "/contact/", canonical="/contact/",
    )
    info = "".join(
        f"\n        <div><dt>{esc(k)}</dt><dd>{v}</dd></div>" for k, v in C.CONTACT_INFO
    )
    h += f"""
<main>

<section class="page-hero" data-bg="dark">
  <div class="ph-bg ph-contact" aria-hidden="true"></div>
  {crumb([("Top", "/"), ("お問い合わせ / Contact", None)])}
  <div class="inner">
    <p class="no">05 / Contact</p>
    <h1 class="anton">Start<br>a Project<span class="accent">.</span></h1>
    <p class="jp">次につくりたいものを、聞かせてください。</p>
  </div>
</section>

<section class="contact-body" data-bg="dark">
  <div class="contact-grid">
    <div class="contact-side">
      <h2 class="anton rv">Let's<br>Talk<span style="color:var(--lime)">.</span></h2>
      <p class="rv">{C.CONTACT_LEAD}</p>
      <dl class="info rv">{info}
      </dl>
    </div>

    <div class="contact-form">
      <div class="pj-select rv" role="group" aria-label="ご相談の種類">
        <button type="button" data-pj="web" aria-pressed="false">Web制作</button>
        <button type="button" data-pj="film" aria-pressed="false">映像制作</button>
        <button type="button" data-pj="both" aria-pressed="false">Web + 映像</button>
        <button type="button" data-pj="other" aria-pressed="false">その他</button>
      </div>

      <!-- Netlify Forms 接続済み。
           data-netlify="true" があることで、Netlify はデプロイ時にこのHTMLを解析し
           「contact」というフォームを自動登録します。送信は Netlify が受け取り、
           成功すると action の /thanks/ へ移動します。 -->
      <form id="contactForm"
            name="contact"
            method="POST"
            action="/thanks/"
            data-netlify="true"
            netlify-honeypot="bot-field">
        <input type="hidden" name="form-name" value="contact">
        <p hidden>
          <label>入力しないでください：<input name="bot-field" tabindex="-1" autocomplete="off"></label>
        </p>
        <input type="hidden" id="pjType" name="type" value="">
        <div class="field rv">
          <label for="fName">お名前<span class="req">*</span></label>
          <input id="fName" name="name" type="text" required placeholder="山田 太郎" autocomplete="name">
        </div>
        <div class="field rv">
          <label for="fCompany">会社名・団体名</label>
          <input id="fCompany" name="company" type="text" placeholder="株式会社〇〇" autocomplete="organization">
        </div>
        <div class="field rv">
          <label for="fEmail">メールアドレス<span class="req">*</span></label>
          <input id="fEmail" name="email" type="email" required placeholder="mail@example.com" autocomplete="email">
        </div>
        <div class="field rv">
          <label for="fTel">電話番号</label>
          <input id="fTel" name="tel" type="tel" placeholder="042-000-0000" autocomplete="tel">
        </div>
        <div class="field rv">
          <label for="fBody">ご相談内容<span class="req">*</span></label>
          <textarea id="fBody" name="message" required placeholder="ご依頼の概要、ご希望の時期、ご予算など、わかる範囲でお書きください。"></textarea>
        </div>
        <button class="btn-solid rv" id="contactSubmit" type="submit">送信する <span class="ar">&rarr;</span></button>
        <p id="formMsg" role="status" aria-live="polite"></p>
      </form>
    </div>
  </div>
</section>
</main>
"""
    ld = jsonld(crumb_jsonld([("トップ", "/"), ("お問い合わせ", "/contact/")]))
    return h + footer(jsonld_blocks=ld)


# ================================================================ THANKS
def page_thanks(articles):
    """お問い合わせ送信後に表示されるページ（Netlify Forms の遷移先）。"""
    h = head(
        "お問い合わせありがとうございます｜ARTICLE",
        "お問い合わせを受け付けました。内容を確認のうえ、担当者よりご返信いたします。",
        "", noindex=True,
    )
    h += f"""
<main>
<section class="thanks-sec" data-bg="dark">
  <div class="ph-bg ph-contact" aria-hidden="true"></div>
  {crumb([("Top", "/"), ("お問い合わせ", "/contact/"), ("送信完了", None)])}
  <div class="thanks-inner">
    <p class="thanks-eyebrow">Thank You</p>
    <h1 class="anton thanks-code">Sent<span class="accent">.</span></h1>
    <p class="thanks-title">お問い合わせありがとうございます</p>
    <p class="thanks-lead">
      送信が完了しました。内容を確認のうえ、担当者よりご返信いたします。<br>
      2〜3営業日たっても返信がない場合は、お手数ですが再度ご連絡ください。
      迷惑メールフォルダに振り分けられていることもありますので、あわせてご確認ください。
    </p>
    <div class="thanks-actions">
      <a class="btn-solid" href="/">トップへ戻る <span class="ar">&rarr;</span></a>
      <a class="btn-ghost" href="/works/">実績を見る</a>
    </div>
  </div>
</section>

<nav class="nf-nav" data-bg="dark" aria-label="主要ページ">
    <a href="/service/"><span class="nm">サービス</span><span class="en">Service &rarr;</span></a>
    <a href="/works/"><span class="nm">実績</span><span class="en">Works &rarr;</span></a>
    <a href="/about/"><span class="nm">ARTICLEについて</span><span class="en">About &rarr;</span></a>
    <a href="/column/"><span class="nm">コラム</span><span class="en">Column &rarr;</span></a>
</nav>
</main>
"""
    return h + footer()


# ================================================================ 404
def page_404(articles):
    h = head(
        "ページが見つかりません｜ARTICLE",
        "お探しのページは見つかりませんでした。URLが変更されたか、削除された可能性があります。",
        "", noindex=True,
    )
    links = "".join(
        f'\n    <a href="{href}"><span class="nm">{jp}</span><span class="en">{en} &rarr;</span></a>'
        for href, jp, en in C.NAV
    )
    h += f"""
<main>
<section class="nf-sec" data-bg="dark">
  <div class="nf-inner">
    <p class="nf-code anton">404</p>
    <h1 class="nf-title">ページが見つかりませんでした</h1>
    <p class="nf-lead">URLが変更されたか、削除された可能性があります。下のリンクからお探しください。</p>
    <a class="btn-solid" href="/">トップへ戻る <span class="ar">&rarr;</span></a>
  </div>
  <nav class="nf-nav" aria-label="主要ページ">{links}
  </nav>
</section>
</main>
"""
    return h + footer()


# ================================================================ sitemap / robots
def build_sitemap(articles):
    now = datetime.now().astimezone()
    pages = [
        ("/", "1.0", "weekly"),
        ("/service/", "0.9", "monthly"),
        ("/works/", "0.9", "monthly"),
        ("/about/", "0.8", "monthly"),
        ("/column/", "0.8", "weekly"),
        ("/contact/", "0.7", "yearly"),
    ]
    rows = []
    for path, prio, freq in pages:
        rows.append(
            "  <url>\n"
            f"    <loc>{esc(abs_url(path))}</loc>\n"
            f"    <lastmod>{iso_date(now)}</lastmod>\n"
            f"    <changefreq>{freq}</changefreq>\n"
            f"    <priority>{prio}</priority>\n"
            "  </url>"
        )
    for a in articles:
        rows.append(
            "  <url>\n"
            f"    <loc>{esc(abs_url('/column/' + a['slug'] + '/'))}</loc>\n"
            f"    <lastmod>{iso_date(a['modified'])}</lastmod>\n"
            "    <changefreq>monthly</changefreq>\n"
            "    <priority>0.7</priority>\n"
            "  </url>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(rows)
        + "\n</urlset>\n"
    )


def build_robots():
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /_build/\n"
        f"\nSitemap: {abs_url('/sitemap.xml')}\n"
    )


# ================================================================ run
LEGACY_FILES = ["works.html", "strengths.html", "process.html", "voice.html", "contact.html"]


def write(path: pathlib.Path, text: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path.stat().st_size


def main() -> int:
    global WEB_WORKS, FILM_WORKS

    print("─" * 62)
    print("ARTICLE — build")
    print(f"  SITE_URL : {SITE_URL}")

    try:
        articles, source = load_articles()
        cms_web, cms_film = load_works()
    except BuildError as e:
        print("\n" + "═" * 62, file=sys.stderr)
        print(" ビルドを中止しました", file=sys.stderr)
        print("═" * 62, file=sys.stderr)
        print(str(e), file=sys.stderr)
        print("═" * 62, file=sys.stderr)
        return 1

    label = {
        "microcms": "microCMS から取得",
        "sample": "サンプル記事（_build/sample-articles.json）※ローカル確認用",
        "empty": "記事なし（microCMSの環境変数が未設定）",
    }[source]
    print(f"  記事     : {len(articles)} 件 / {label}")

    if cms_web:
        WEB_WORKS = cms_web
        print(f"  HP実績   : {len(cms_web)} 件 / microCMS（works-web）")
    else:
        print(f"  HP実績   : {len(WEB_WORKS)} 件 / _build/content.py の内容")
    if cms_film:
        FILM_WORKS = cms_film
        src = "microCMS（works-film）"
    else:
        src = "_build/content.py の内容"
    shown = len(drop_samples(FILM_WORKS))
    hidden = len(FILM_WORKS) - shown
    print(f"  映像実績 : {shown} 件 / {src}"
          + (f"（サンプル{hidden}件を非表示）" if hidden else ""))

    v_shown = len(drop_samples(C.VOICES))
    v_hidden = len(C.VOICES) - v_shown
    if v_shown:
        print(f"  お客様の声: {v_shown} 件"
              + (f"（サンプル{v_hidden}件を非表示）" if v_hidden else ""))
    else:
        print(f"  お客様の声: 0 件（サンプル{v_hidden}件を非表示 → セクションごと非表示）")

    print(f"  ビルド種別: {'本番（サンプル非表示）' if IS_PROD else 'プレビュー（サンプル表示）'}")

    if source == "sample":
        print("  ⚠ サンプル記事でビルドしています。公開ビルドでは MICROCMS_SERVICE_DOMAIN と")
        print("    MICROCMS_API_KEY を設定してください。")
    if source == "empty":
        print("  ⚠ 記事0件でビルドします。COLUMN一覧は「準備中」の表示になります。")
    print("─" * 62)

    for name in LEGACY_FILES:
        p = OUT / name
        if p.exists():
            p.unlink()
            print(f"  removed  {name}（統合済み／_redirects で301）")

    col_dir = OUT / "column"
    if col_dir.exists():
        shutil.rmtree(col_dir)

    total = 0
    outputs = [
        ("index.html", page_index),
        ("service/index.html", page_service),
        ("works/index.html", page_works),
        ("about/index.html", page_about),
        ("column/index.html", page_column),
        ("contact/index.html", page_contact),
        ("thanks/index.html", page_thanks),
        ("404.html", page_404),
    ]
    for name, builder in outputs:
        size = write(OUT / name, builder(articles))
        total += size
        print(f"  {name:30} {size/1024:7.1f} KB")

    for a in articles:
        name = f"column/{a['slug']}/index.html"
        size = write(OUT / name, page_article(a, articles))
        total += size
        print(f"  {name:30} {size/1024:7.1f} KB")

    write(OUT / "sitemap.xml", build_sitemap(articles))
    write(OUT / "robots.txt", build_robots())
    print(f"  {'sitemap.xml':30} {(OUT/'sitemap.xml').stat().st_size/1024:7.1f} KB")
    print(f"  {'robots.txt':30} {(OUT/'robots.txt').stat().st_size/1024:7.1f} KB")

    print("─" * 62)
    print(f"完了 → {OUT}  （HTML合計 {total/1024:.1f} KB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

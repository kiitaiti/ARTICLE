#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ARTICLE — ローカルプレビュー起動スクリプト

サイトを表示するための簡易サーバーを立ち上げ、ブラウザを自動で開きます。
直接これを実行してもいいですが、通常は次のファイルをダブルクリックしてください。

  Mac      … プレビュー起動_Mac.command
  Windows  … プレビュー起動_Windows.bat

止めるときは、開いた黒い画面（ターミナル / コマンドプロンプト）を閉じるか、
Ctrl + C を押してください。
"""
import http.server
import os
import pathlib
import socketserver
import sys
import threading
import webbrowser

ROOT = pathlib.Path(__file__).resolve().parent.parent


def start_server(handler, start=8000, tries=40):
    """空いているポートでサーバーを起動する。
    「空きを調べる」→「あらためて起動する」の2段階だと、その隙に他のソフトが
    そのポートを取ってしまうことがあるため、実際に起動できたものを返します。"""
    socketserver.TCPServer.allow_reuse_address = True
    for port in range(start, start + tries):
        try:
            return socketserver.TCPServer(("127.0.0.1", port), handler), port
        except OSError:
            continue
    return None, None


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def end_headers(self):
        # 修正がすぐ反映されるようキャッシュを無効にする
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self):
        """フォーム送信（POST）を受けたときの動き。

        本番では Netlify が受け取りますが、ローカルの簡易サーバーは POST を
        扱えず「Error response」になってしまうため、Netlify と同じように
        送信先ページへ転送します。※ 内容は保存されません（動作確認用）。
        """
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)
        except (ValueError, OSError):
            pass
        dest = self.path or "/thanks/"
        self.send_response(303)
        self.send_header("Location", dest)
        self.send_header("Content-Length", "0")
        self.end_headers()
        print(f"  [ローカル] フォーム送信を受け取りました → {dest} へ移動します")
        print("            ※ ローカルでは内容は保存されません。本番では Netlify に記録されます。")

    def send_error(self, code, message=None, explain=None):
        # 存在しないURLは、本番と同じ 404.html を返す
        if code == 404 and (ROOT / "404.html").exists():
            body = (ROOT / "404.html").read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            return
        super().send_error(code, message, explain)

    def log_message(self, *a):
        pass  # 画面をきれいに保つ


def main():
    if not (ROOT / "index.html").exists():
        print("※ index.html が見つかりません。")
        print("  先に  python3 _build/build.py  を実行してください。")
        input("\nEnterキーを押すと閉じます...")
        return 1

    httpd, port = start_server(Handler)
    if httpd is None:
        print("※ 使えるポートが見つかりませんでした。")
        print("  他のプレビューが起動したままになっていないか確認してください。")
        input("\nEnterキーを押すと閉じます...")
        return 1

    url = f"http://localhost:{port}/"
    line = "─" * 54
    print(line)
    print("  ARTICLE — ローカルプレビュー")
    print(line)
    print(f"  ブラウザで開きます → {url}")
    print()
    print("  開かない場合は、上のアドレスをブラウザに貼り付けてください。")
    print()
    print("  【終了するには】この画面で Ctrl + C を押すか、")
    print("                  この画面（ウィンドウ）を閉じてください。")
    print(line)
    sys.stdout.flush()

    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        with httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  プレビューを終了しました。")
    return 0


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.exit(main())

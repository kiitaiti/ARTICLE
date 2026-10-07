#!/bin/bash
# ARTICLE — ローカルプレビュー（Mac用）
# このファイルをダブルクリックするとサイトが表示されます。
# ※ 初回は「開発元を確認できません」と出ることがあります。
#    その場合は右クリック →「開く」→「開く」を選んでください。

cd "$(dirname "$0")" || exit 1

if command -v python3 >/dev/null 2>&1; then
  python3 _build/preview.py
else
  echo "──────────────────────────────────────────────"
  echo " Python 3 が見つかりませんでした。"
  echo ""
  echo " ターミナルで次を実行するとインストールできます："
  echo "   xcode-select --install"
  echo ""
  echo " または https://www.python.org/downloads/ からどうぞ。"
  echo "──────────────────────────────────────────────"
  read -r -p "Enterキーを押すと閉じます..."
fi

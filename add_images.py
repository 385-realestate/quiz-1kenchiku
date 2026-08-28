"""
questions.js の全問題に対して元ページの図を追加するパッチスクリプト

使い方:
  python add_images.py           # 未処理の全問題をチェック
  python add_images.py --force   # img フィールドありも再取得

動作:
  1. questions.js の全問題から元問題IDを収集（約250件）
  2. 各ページに <img> があれば base64 エンコードして "img" フィールドに追加
  3. questions.js を上書き保存
"""

import json, re, time, os, sys
import requests
from bs4 import BeautifulSoup
import base64

BASE_URL = "https://kenchikusekou1.kakomonn.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.9",
}

# これらを含む src はアイコン等なのでスキップ
SKIP_KEYWORDS = ["icon", "logo", "btn", "arrow", "bullet", "mark", "star",
                 "favicon", "banner", "ad", "banner"]


def fetch(url, timeout=20):
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    return r


def get_figure(qid):
    """問題ページから図のbase64データURLを取得する。なければNone。"""
    url = f"{BASE_URL}/questions/{qid}"
    try:
        r = fetch(url)
        r.encoding = "utf-8"
        soup = BeautifulSoup(r.text, "html.parser")

        detail = soup.select_one("div.problem_detail") or soup

        for img in detail.select("img"):
            src = img.get("src", "").strip()
            if not src:
                continue
            if any(kw in src.lower() for kw in SKIP_KEYWORDS):
                continue
            if not src.startswith("http"):
                src = BASE_URL + ("" if src.startswith("/") else "/") + src

            try:
                ir = fetch(src, timeout=15)
                ct = ir.headers.get("Content-Type", "image/png").split(";")[0].strip()
                if not ct.startswith("image/"):
                    continue
                # 極端に小さい画像（アイコン等）はスキップ
                if len(ir.content) < 1000:
                    continue
                b64 = base64.b64encode(ir.content).decode()
                return f"data:{ct};base64,{b64}"
            except Exception as e:
                continue

    except Exception as e:
        print(f"  ERROR: {e}")
    return None


def main():
    force = "--force" in sys.argv

    script_dir = os.path.dirname(os.path.abspath(__file__))
    js_path = os.path.join(script_dir, "questions.js")

    # questions.js 読み込み
    with open(js_path, encoding="utf-8") as f:
        txt = f.read()
    m = re.search(r"const QUESTIONS = (\[.*\]);", txt, re.DOTALL)
    if not m:
        print("ERROR: questions.js のパースに失敗しました。")
        return
    questions = json.loads(m.group(1))
    print(f"読み込み: {len(questions)} 問")

    # 全問題の base_qid を収集
    qid_map = {}  # base_qid -> [index, ...]
    for i, q in enumerate(questions):
        if not force and q.get("img"):
            continue  # 既に画像あり
        base_qid = q["id"].rsplit("_", 1)[0]
        qid_map.setdefault(base_qid, []).append(i)

    total = len(qid_map)
    print(f"チェック対象: {total} 問題ページ")
    print("（図がないページは「図なし」と表示します）\n")

    updated = 0
    for j, (qid, indices) in enumerate(qid_map.items()):
        print(f"[{j+1:3d}/{total}] 問題 {qid} ...", end=" ", flush=True)
        img_data = get_figure(qid)
        if img_data:
            for idx in indices:
                questions[idx]["img"] = img_data
            updated += 1
            print(f"図あり → {len(indices)}問に追加")
        else:
            print("図なし")
        time.sleep(0.6)

    print(f"\n--- 完了 ---")
    print(f"  図あり: {updated} ページ")
    print(f"  図なし: {total - updated} ページ")

    if updated == 0:
        print("新規の図はありませんでした。questions.js はそのままです。")
        return

    # 保存
    header = (
        "// 1級建築施工管理技士 ○×問題データ（頻出選定済み）\n"
        f"// 問題数: {len(questions)} 問\n"
        "const QUESTIONS = "
    )
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(header)
        json.dump(questions, f, ensure_ascii=False, indent=2)
        f.write(";\n")
    print(f"questions.js を更新しました（図あり: {updated} ページ）。")


if __name__ == "__main__":
    main()

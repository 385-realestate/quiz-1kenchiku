"""
questions.js の「図に示す」問題に画像データを追加するパッチスクリプト

使い方:
  pip install requests beautifulsoup4
  python add_images.py

動作:
  1. questions.js を読み込み
  2. context/statement に「図」を含む問題を検出
  3. 元の問題ページから <img> を取得 → base64でエンコード
  4. questions.js の該当問題に "img" フィールドを追加して上書き保存
"""

import json, re, time, os
import requests
from bs4 import BeautifulSoup
import base64

BASE_URL = "https://kenchikusekou1.kakomonn.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.9",
}

FIG_PATTERN = re.compile(r"図に示す|下図|次の図|図のよう|右図|左図|図－")

SKIP_KEYWORDS = ["icon", "logo", "btn", "arrow", "bullet", "mark", "star"]


def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
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
            # アイコン系・ロゴ系は除外
            if any(kw in src.lower() for kw in SKIP_KEYWORDS):
                continue
            if not src.startswith("http"):
                src = BASE_URL + ("" if src.startswith("/") else "/") + src

            try:
                ir = fetch(src)
                ct = ir.headers.get("Content-Type", "image/png").split(";")[0].strip()
                if not ct.startswith("image/"):
                    continue
                b64 = base64.b64encode(ir.content).decode()
                print(f"      → 図取得: {src} ({len(ir.content)//1024}KB)")
                return f"data:{ct};base64,{b64}"
            except Exception as e:
                print(f"      → 画像DL失敗: {e}")
                continue

    except Exception as e:
        print(f"  ERROR fetching {url}: {e}")
    return None


def main():
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

    # 図を含む問題の base_qid を収集
    fig_qids = {}   # base_qid -> [index, ...]
    for i, q in enumerate(questions):
        if q.get("img"):
            continue  # 既に画像あり
        ctx = (q.get("context") or "") + " " + (q.get("statement") or "")
        if FIG_PATTERN.search(ctx):
            base_qid = q["id"].rsplit("_", 1)[0]
            fig_qids.setdefault(base_qid, []).append(i)

    if not fig_qids:
        print("図を含む未処理の問題はありませんでした。")
        return

    print(f"図を含む問題グループ: {len(fig_qids)} 件\n")

    updated = 0
    skipped = 0
    for j, (qid, indices) in enumerate(fig_qids.items()):
        print(f"[{j+1:3d}/{len(fig_qids)}] 問題 {qid} (該当 {len(indices)} 問) ...", flush=True)
        img_data = get_figure(qid)
        if img_data:
            for idx in indices:
                questions[idx]["img"] = img_data
            updated += 1
        else:
            print(f"      → 図なし（スキップ）")
            skipped += 1
        time.sleep(0.8)

    print(f"\n--- 完了 ---")
    print(f"  画像追加: {updated} グループ")
    print(f"  図なし  : {skipped} グループ")

    if updated == 0:
        print("更新なし。questions.js はそのままです。")
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
    print(f"questions.js を更新しました。")


if __name__ == "__main__":
    main()
"""
1級建築施工管理技士 ○×問題スクレイパー
kenchikusekou1.kakomonn.com から4択問題を収集し、○×形式に変換して questions.js を生成する。

【使い方】
  pip install requests beautifulsoup4

  python scraper.py --year r06              # 令和6年
  python scraper.py --year r06 r05          # 複数年度
  python scraper.py --all                   # 全年度（8年分）
  python scraper.py --all --merge           # 既存データに追記
  python scraper.py --year r06 --limit 20   # テスト（20問で止める）

【変換ロジック】
  各選択肢の解説文（div.expound-X > div.expound-txt）を読み、
  「不適当」「誤」で始まる → × (false)
  「適当」「正」で始まる  → ○ (true)
  4択1問 → 最大4つの○×問題に変換
"""

import requests
from bs4 import BeautifulSoup
import json, time, re, os, sys, argparse

BASE_URL = "https://kenchikusekou1.kakomonn.com"
HEADERS  = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en;q=0.9",
}

YEAR_IDS = {
    "r07": ("89008", "令和7年"),
    "r06": ("89007", "令和6年"),
    "r05": ("89006", "令和5年"),
    "r04": ("89005", "令和4年"),
    "r03": ("89004", "令和3年"),
    "r02": ("89003", "令和2年"),
    "r01": ("89002", "令和元年"),
    "h30": ("89001", "平成30年"),
}

# 区分 → 分野名のマッピング
SECTION_MAP = {
    "午前 イ": "建築学（環境工学・材料）",
    "午前 ロ": "建築施工（躯体）",
    "午前 ハ": "建築施工（仕上）",
    "午前 ニ": "施工管理・仮設安全",
    "午前 ホ": "施工管理",
    "午前 ヘ": "法規",
    "午後 イ": "施工管理（管理）",
    "午後 ロ": "施工管理（記述）",
    "午後 ハ": "施工管理（応用）",
}

WRONG_KEYWORDS = [
    "不適当", "誤りです", "誤です", "不正確", "誤った", "誤りであ", "誤っ",
    "不正解",                # 「〜は不正解です」
    "正解ではない",          # 「正解ではありません」
    "正解ではあり",          # 同上（短縮）
    "こちらが正解です",      # 試験の正答 = 設問文は誤り
    "×（正解）",             # 「×（正解）〜」= この設問は誤り
    "【✖】",                 # 「【✖】間違い」= 計算誤り
    "この解答は『 〇 』",    # 〇が正解 = 設問文が最も不適当 = 誤り
    "この解答が『 〇 』",    # 同上（表記ゆれ）
    "この解答は『 ○ 』",    # 同上（丸文字）
    "この解答が『 ○ 』",
    # 注意: 「この解答は『 ✖ 』です（適当）」は True のためWRONGに含めない
    # ✖ = 「この選択肢を選ぶと不正解」= 設問文は正しい（適当）
]
RIGHT_KEYWORDS = ["適当です", "正しい", "正です", "正確", "正解"]


def fetch(url, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.encoding = "utf-8"
            return r
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2)


# ── 問題IDリスト取得 ────────────────────────────────────────────
def get_question_ids(list_id, year_label):
    ids = []
    seen = set()
    page = 1

    while True:
        url = f"{BASE_URL}/list1/{list_id}?page={page}"
        print(f"  リスト {page}ページ目: {url}")
        r = fetch(url)
        soup = BeautifulSoup(r.text, "html.parser")

        # メインコンテンツ内の /questions/ リンクを収集
        main = soup.select_one("main") or soup
        links = main.select("a[href*='/questions/']")

        new_count = 0
        for link in links:
            m = re.search(r"/questions/(\d+)", link["href"])
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                ids.append(m.group(1))
                new_count += 1

        if new_count == 0:
            print(f"  → {page}ページ: 新規IDなし。終了。")
            break

        # 次ページの有無を確認（数字リンク or 「次へ」リンク）
        pager = soup.select_one(".pager") or soup.select_one("[class*='pager']")
        if pager:
            next_link = pager.find("a", string=re.compile(r"次|Next|›|»"))
            page_nums = [int(a.get_text()) for a in pager.select("a") if a.get_text().isdigit()]
            if next_link or (page_nums and page < max(page_nums)):
                page += 1
                time.sleep(0.8)
                continue
        # ページャーがない場合も次ページを試みる（取得0件になるまで）
        page += 1
        time.sleep(0.8)

    print(f"  {year_label}: 合計 {len(ids)} 問取得")
    return ids


# ── ○×判定 ─────────────────────────────────────────────────────
def judge_answer(text):
    """解説テキストから○(True)か×(False)かを判定する。不明はNone。"""
    t = text.strip()

    # 文頭または冒頭50文字で判定
    head = t[:60]

    for w in WRONG_KEYWORDS:
        if w in head:
            return False

    for w in RIGHT_KEYWORDS:
        if w in head:
            return True

    # 追加パターン: 「○です」「×です」
    if re.search(r"^[○×〇]", head):
        return head[0] in "○〇"

    # 文中にある場合
    if re.search(r"不適当|誤り|誤った|誤っ", t[:100]):
        return False
    if re.search(r"適当|正しい", t[:100]):
        return True

    return None  # 判定不能


# ── 1問パース ──────────────────────────────────────────────────
def parse_question(qid, year_label):
    url = f"{BASE_URL}/questions/{qid}"
    try:
        r = fetch(url)
    except Exception as e:
        print(f"    SKIP {qid}: 取得失敗 ({e})")
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    # ── 年度・区分 ──
    when_el = soup.select_one("p.when")
    when_text = when_el.get_text(separator=" ", strip=True) if when_el else ""
    # "1級建築施工管理技士試験 令和6年（2024年）  問1（午前 イ 問1）"

    year_m = re.search(r"(令和\d+年|平成\d+年)", when_text)
    year   = year_m.group(1) if year_m else year_label

    # 区分を抽出: 「午前 イ」「午後 ロ」など（全角括弧対応）
    sec_m = re.search(r"[（(]([午後前]+\s*[イロハニホヘ]?)\s*問\d+[）)]", when_text)
    section  = sec_m.group(1).strip() if sec_m else ""
    # 午前/午後だけの場合も拾う
    if not section:
        sec_m2 = re.search(r"(午[前後])\s*[イロハニホヘ]", when_text)
        if sec_m2:
            sec_m3 = re.search(r"(午[前後]\s*[イロハニホヘ])", when_text)
            section = sec_m3.group(1).strip() if sec_m3 else sec_m2.group(1)
    category = SECTION_MAP.get(section, section or "施工管理")

    # ── 問題文 ──
    problem_detail = soup.select_one("div.problem_detail")
    if not problem_detail:
        print(f"    SKIP {qid}: problem_detail 未検出")
        return []

    ttl_el = problem_detail.select_one("div.ttl")
    question_text = ttl_el.get_text(separator=" ", strip=True) if ttl_el else ""

    # ── 選択肢 ──
    choice_lis = problem_detail.select("ul.list li")
    choices = [li.get_text(separator=" ", strip=True) for li in choice_lis]

    if not question_text or len(choices) < 2:
        print(f"    SKIP {qid}: 問題文または選択肢未取得 (choices={len(choices)})")
        return []

    # ── 解説・○×判定 ──
    results = []
    for i, choice in enumerate(choices):
        idx = i + 1  # 1-based
        expound_div = soup.select_one(f"div.expound-{idx}")
        if not expound_div:
            continue

        exp_txt_el = expound_div.select_one("div.expound-txt")
        exp_text   = exp_txt_el.get_text(separator=" ", strip=True) if exp_txt_el else ""

        answer = judge_answer(exp_text)
        if answer is None:
            # フォールバック: 全解説テキストから判定
            full_exp = expound_div.get_text(separator=" ", strip=True)
            answer = judge_answer(full_exp)

        if answer is None:
            # どうしても判定できない場合はスキップ（ログのみ）
            continue

        results.append({
            "id":          f"{qid}_{idx}",
            "year":        year,
            "category":    category,
            "context":     question_text,
            "statement":   choice,
            "answer":      answer,
            "explanation": exp_text[:350],
        })

    return results


# ── questions.js 生成 ───────────────────────────────────────────
def build_js(questions, output_path):
    header = (
        "// 1級建築施工管理技士 ○×問題データ（scraper.py により自動生成）\n"
        f"// 生成問題数: {len(questions)} 問\n"
        "const QUESTIONS = "
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        json.dump(questions, f, ensure_ascii=False, indent=2)
        f.write(";\n")
    print(f"\n[完了] {output_path} に {len(questions)} 問を保存しました。")


# ── メイン ─────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="1級建築施工管理技士 スクレイパー")
    ap.add_argument("--year",  nargs="+",
                    help="対象年度 (r07 r06 r05 r04 r03 r02 r01 h30)")
    ap.add_argument("--all",   action="store_true", help="全年度")
    ap.add_argument("--limit", type=int, default=0,
                    help="1年度あたりの最大問題ページ数（テスト用）")
    ap.add_argument("--merge", action="store_true",
                    help="既存 questions.js に追記（重複除外）")
    args = ap.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_js  = os.path.join(script_dir, "questions.js")

    # 対象年度
    if args.all:
        targets = list(YEAR_IDS.keys())
    elif args.year:
        targets = args.year
    else:
        ap.print_help()
        sys.exit(1)

    for t in targets:
        if t not in YEAR_IDS:
            print(f"ERROR: 年度 '{t}' は不明です。使えるキー: {list(YEAR_IDS.keys())}")
            sys.exit(1)

    # 既存データ読み込み
    existing = []
    existing_ids = set()
    if args.merge and os.path.exists(output_js):
        with open(output_js, "r", encoding="utf-8") as f:
            txt = f.read()
        m = re.search(r"const QUESTIONS\s*=\s*(\[.*\]);", txt, re.DOTALL)
        if m:
            existing = json.loads(m.group(1))
            existing_ids = {q["id"] for q in existing}
            print(f"既存データ読み込み: {len(existing)} 問")

    # スクレイピング
    all_new = []
    for yr_key in targets:
        list_id, year_label = YEAR_IDS[yr_key]
        print(f"\n{'='*50}")
        print(f"  {year_label} ({yr_key})")
        print(f"{'='*50}")

        qids = get_question_ids(list_id, year_label)
        if args.limit:
            qids = qids[:args.limit]
            print(f"  ※ --limit {args.limit} 適用")

        for i, qid in enumerate(qids):
            print(f"  [{i+1:3d}/{len(qids)}] 問題 {qid} ...", end=" ", flush=True)

            if f"{qid}_1" in existing_ids:
                print("skip (既存)")
                continue

            items = parse_question(qid, year_label)
            new_items = [q for q in items if q["id"] not in existing_ids]
            all_new.extend(new_items)
            existing_ids.update(q["id"] for q in new_items)
            print(f"→ {len(new_items)} 問追加")

            time.sleep(0.7)  # サーバー負荷軽減

    # 保存
    final = existing + all_new
    print(f"\n合計: 既存 {len(existing)} + 新規 {len(all_new)} = {len(final)} 問")

    if not all_new and existing:
        print("新規問題はありませんでした。")
        return

    build_js(final, output_js)
    print("index.html をブラウザで開くと新しい問題が使えます。")


if __name__ == "__main__":
    main()

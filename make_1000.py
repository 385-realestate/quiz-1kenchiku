"""
頻出1000問セレクター
全8年分の○×問題から、複数年にまたがって出題されているトピックを優先して
1000問をセレクトし questions.js を更新する。

使い方:
  python make_1000.py           # 1000問を選んで questions.js を更新
  python make_1000.py --stats   # 統計のみ表示（ファイル更新なし）
  python make_1000.py --top 1200  # 1200問選ぶ
"""

import json, re, sys, argparse
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")

TARGET = 1000  # デフォルト選択問題数


def load_questions(path="questions.js"):
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    m = re.search(r"const QUESTIONS = (\[.*\]);", txt, re.DOTALL)
    if not m:
        raise ValueError("questions.js のパースに失敗しました")
    return json.loads(m.group(1))


def save_questions(questions, path="questions.js"):
    header = (
        "// 1級建築施工管理技士 ○×問題データ（頻出選定済み）\n"
        f"// 収録問題数: {len(questions)} 問（全8年の頻出トピック優先）\n"
        "const QUESTIONS = "
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        json.dump(questions, f, ensure_ascii=False, indent=2)
        f.write(";\n")
    print(f"[完了] {path} に {len(questions)} 問を書き込みました")


def extract_topic_key(context):
    """
    問題文から「トピックキー」を抽出する。
    同じ知識を問う問題は同じトピックを含むため、
    問いの定型文（「〜に関する記述として」など）を除いた
    トピック部分の先頭40文字をキーとして使う。
    """
    text = context

    # 定型の問い文を除去（ここより後は問い方の表現なので不要）
    for pat in [
        r"に関する(一般的な|次の)?記述(として)?.*",
        r"について(の)?.*",
        r"として(最も|正しい|誤って).*",
        r"として不適当.*",
        r"に関して.*",
    ]:
        text = re.sub(pat, "", text)

    # 句読点・空白を正規化
    text = re.sub(r"[。、\s　]", "", text).strip()

    # 先頭40文字をキーとして返す（十分に特定的）
    return text[:40] if text else context[:40]


def score_questions(questions):
    """
    各問題に「頻出スコア」を付ける。
    スコア = そのトピックが何年分に登場するか (1〜8)
    """
    # ベース問ID → 年度・カテゴリ
    base_to_years = defaultdict(set)   # topic_key → 年度セット
    q_to_topic    = {}                 # question id → topic_key

    for q in questions:
        key = extract_topic_key(q["context"])
        q_to_topic[q["id"]] = key
        base_to_years[key].add(q["year"])

    # スコア計算
    scored = []
    for q in questions:
        key   = q_to_topic[q["id"]]
        years = base_to_years[key]
        score = len(years)  # 登場年度数

        # 最近年ほど重み増（令和6年・令和7年 +0.5）
        recency = 0.5 if q["year"] in ("令和6年", "令和7年") else 0
        scored.append((score + recency, q))

    return scored, base_to_years


def select_top_n(scored, n=TARGET):
    """
    スコア降順でソートし、上位 n 問を選ぶ。
    カテゴリ偏りを抑えるため、同スコア内ではカテゴリをバランスよく選ぶ。
    """
    scored_sorted = sorted(scored, key=lambda x: -x[0])

    selected = []
    cat_count = Counter()
    max_per_cat = n // 4  # 1カテゴリが全体の25%超えないよう上限（緩め）

    # スコア ≥ 3（3年以上頻出）を優先確保
    for score, q in scored_sorted:
        if score >= 3 and len(selected) < n:
            if cat_count[q["category"]] < max_per_cat:
                selected.append(q)
                cat_count[q["category"]] += 1

    # 不足分をスコア降順で補充
    used_ids = {q["id"] for q in selected}
    for score, q in scored_sorted:
        if len(selected) >= n:
            break
        if q["id"] not in used_ids:
            selected.append(q)
            used_ids.add(q["id"])

    # 元の年度・カテゴリ順に並べ直す（使いやすさのため）
    year_order = ["令和7年", "令和6年", "令和5年", "令和4年",
                  "令和3年", "令和2年", "令和元年", "平成30年"]
    year_idx = {y: i for i, y in enumerate(year_order)}
    selected.sort(key=lambda q: (year_idx.get(q["year"], 99), q["id"]))

    return selected


def print_stats(questions, scored, base_to_years):
    print(f"\n{'='*55}")
    print(f"  頻出分析レポート  （総問題数: {len(questions)} 問）")
    print(f"{'='*55}")

    year_cnt = Counter(q["year"] for q in questions)
    print("\n--- 年度別 ---")
    for y in ["令和7年","令和6年","令和5年","令和4年","令和3年","令和2年","令和元年","平成30年"]:
        if y in year_cnt:
            print(f"  {y}: {year_cnt[y]:4d} 問")

    cat_cnt = Counter(q["category"] for q in questions)
    print("\n--- カテゴリ別（上位10） ---")
    for cat, cnt in cat_cnt.most_common(10):
        print(f"  {cat}: {cnt:4d} 問")

    freq_dist = Counter(len(v) for v in base_to_years.values())
    print("\n--- トピックの頻出度分布 ---")
    total_topics = len(base_to_years)
    for freq in sorted(freq_dist.keys(), reverse=True):
        n_topics = freq_dist[freq]
        bar = "#" * min(n_topics // 5, 30)
        label = f"{freq}年分に登場"
        print(f"  {label}: {n_topics:4d} トピック  {bar}")
    print(f"  合計: {total_topics} トピック")

    scores = [s for s, _ in scored]
    print(f"\n--- スコア分布 ---")
    sc_cnt = Counter(int(s) for s in scores)
    for sc in sorted(sc_cnt.keys(), reverse=True):
        print(f"  スコア {sc}: {sc_cnt[sc]:4d} 問")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true", help="統計のみ表示")
    ap.add_argument("--top",   type=int, default=TARGET, help="選ぶ問題数")
    args = ap.parse_args()

    questions = load_questions()
    print(f"読み込み: {len(questions)} 問")

    # 設問文が短すぎる（数値のみ・空）問題を除外
    before = len(questions)
    questions = [q for q in questions if len(q.get("statement", "").strip()) >= 15]
    removed = before - len(questions)
    if removed:
        print(f"  → 設問不備（15文字未満/空）を {removed} 件除外: {len(questions)} 問に")

    scored, base_to_years = score_questions(questions)
    print_stats(questions, scored, base_to_years)

    if args.stats:
        return

    selected = select_top_n(scored, args.top)
    print(f"\n選定: {len(selected)} 問（目標 {args.top} 問）")

    # 選定後の内訳表示
    sel_year = Counter(q["year"] for q in selected)
    sel_cat  = Counter(q["category"] for q in selected)
    print("\n--- 選定結果 年度別 ---")
    for y in ["令和7年","令和6年","令和5年","令和4年","令和3年","令和2年","令和元年","平成30年"]:
        if y in sel_year:
            print(f"  {y}: {sel_year[y]:4d} 問")

    print("\n--- 選定結果 カテゴリ別 ---")
    for cat, cnt in sel_cat.most_common(15):
        print(f"  {cat}: {cnt:4d} 問")

    save_questions(selected)


if __name__ == "__main__":
    main()

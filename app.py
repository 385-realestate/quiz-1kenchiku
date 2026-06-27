import streamlit as st
import json, re, random

st.set_page_config(
    page_title="1級建築施工管理技士 ○×クイズ",
    page_icon="🏗️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
/* 全体幅を制限 */
.block-container { max-width: 640px !important; padding: 1rem 1rem 4rem !important; }
/* ○ボタン */
div[data-testid="column"]:first-child .stButton button {
    background: #e8f5e9 !important;
    border: 3px solid #43a047 !important;
    color: #1b5e20 !important;
    font-size: 2.8rem !important;
    height: 90px !important;
    border-radius: 14px !important;
    font-weight: bold !important;
}
/* ×ボタン */
div[data-testid="column"]:last-child .stButton button {
    background: #ffebee !important;
    border: 3px solid #e53935 !important;
    color: #b71c1c !important;
    font-size: 2.8rem !important;
    height: 90px !important;
    border-radius: 14px !important;
    font-weight: bold !important;
}
/* metricラベルを小さく */
[data-testid="stMetricLabel"] { font-size: 11px !important; }
[data-testid="stMetricValue"] { font-size: 20px !important; }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_questions():
    with open("questions.js", encoding="utf-8") as f:
        txt = f.read()
    m = re.search(r"const QUESTIONS = (\[.*\]);", txt, re.DOTALL)
    return json.loads(m.group(1))


QUESTIONS = load_questions()
YEARS = sorted(set(q["year"] for q in QUESTIONS))
CATS  = sorted(set(q["category"] for q in QUESTIONS))


# ── セッション初期化 ─────────────────────────────────────────────────
def init():
    defs = dict(
        screen="start", queue=[], idx=0,
        correct=0, total=0, wrong_ids=[],
        answered=False, last_ok=None,
        cumulative_wrong=set(), saved=None,
    )
    for k, v in defs.items():
        if k not in st.session_state:
            st.session_state[k] = v

init()
S = st.session_state


def handle_answer(user_ans: bool):
    q = S.queue[S.idx]
    ok = (user_ans == q["answer"])
    S.total += 1
    if ok:
        S.correct += 1
        S.cumulative_wrong.discard(q["id"])
    else:
        S.wrong_ids.append(q["id"])
        S.cumulative_wrong.add(q["id"])
    S.answered = True
    S.last_ok  = ok


def save_and_go_home():
    S.saved = dict(
        queue=S.queue, idx=S.idx,
        correct=S.correct, total=S.total,
        wrong_ids=S.wrong_ids[:],
    )
    S.screen = "start"
    st.rerun()


# ══════════════════════════════════════════════════════════════════════
# スタート画面
# ══════════════════════════════════════════════════════════════════════
if S.screen == "start":
    st.markdown("# 1級建築施工管理技士\n## ○×クイズ")

    # 続きから再開カード
    if S.saved:
        p = S.saved
        remain = len(p["queue"]) - p["idx"]
        rate   = round(p["correct"] / p["total"] * 100) if p["total"] else 0
        st.info(
            f"📝 **前回の続きがあります**\n\n"
            f"残り **{remain}問** ／ 回答済 {p['total']}問 ／ 正答率 {rate}%"
        )
        if st.button("続きから再開 ▶", type="primary", use_container_width=True, key="resume"):
            S.queue, S.idx   = p["queue"], p["idx"]
            S.correct, S.total = p["correct"], p["total"]
            S.wrong_ids      = p["wrong_ids"]
            S.answered = False
            S.saved    = None
            S.screen   = "quiz"
            st.rerun()
        st.divider()

    # フィルター
    sel_years = st.multiselect("出題年度（複数選択可）", YEARS, placeholder="全年度")
    sel_cats  = st.multiselect("カテゴリ（複数選択可）",  CATS,  placeholder="全カテゴリ")
    order     = st.radio("出題順", ["シャッフル", "順番通り", "累計苦手のみ"], horizontal=True)

    qs = QUESTIONS[:]
    if sel_years: qs = [q for q in qs if q["year"]     in sel_years]
    if sel_cats:  qs = [q for q in qs if q["category"] in sel_cats]
    if order == "累計苦手のみ":
        qs = [q for q in qs if q["id"] in S.cumulative_wrong]

    c1, c2 = st.columns(2)
    c1.write(f"出題数: **{len(qs)}問**")
    if S.cumulative_wrong:
        c2.caption(f"累計苦手: {len(S.cumulative_wrong)}問")

    if st.button("スタート ▶", type="primary", use_container_width=True):
        if not qs:
            st.error("条件に合う問題がありません。")
            st.stop()
        S.queue    = random.sample(qs, len(qs)) if order == "シャッフル" else qs[:]
        S.idx      = 0; S.correct = 0; S.total = 0; S.wrong_ids = []
        S.answered = False; S.saved = None; S.screen = "quiz"
        st.rerun()


# ══════════════════════════════════════════════════════════════════════
# クイズ画面
# ══════════════════════════════════════════════════════════════════════
elif S.screen == "quiz":
    queue = S.queue
    idx   = S.idx
    n     = len(queue)

    if idx >= n:
        S.screen = "results"
        st.rerun()

    q = queue[idx]

    # ホームへ
    if st.button("← ホームに戻る", key="home"):
        save_and_go_home()

    # 進捗バー
    st.progress((idx) / n)
    m1, m2, m3 = st.columns(3)
    m1.metric("回答済", f"{S.total}問")
    m2.metric("残り",   f"{n - idx - 1}問")
    m3.metric("正答率", f"{round(S.correct/S.total*100)}%" if S.total else "-%")

    st.divider()

    # 問題
    st.caption(f"#{idx+1}/{n}　{q['year']} ｜ {q['category']}")
    if q.get("context"):
        with st.expander("問題文", expanded=True):
            st.write(q["context"])

    st.markdown(f"### {q['statement']}")
    st.write("")

    # ── 未回答 ──
    if not S.answered:
        bc1, bc2 = st.columns(2)
        with bc1:
            if st.button("○", key="maru", use_container_width=True):
                handle_answer(True)
                st.rerun()
            st.caption("正しい", )
        with bc2:
            if st.button("×", key="batsu", use_container_width=True):
                handle_answer(False)
                st.rerun()
            st.caption("誤り")

    # ── 回答後フィードバック ──
    else:
        ok = S.last_ok
        correct_label = "○（正しい）" if q["answer"] else "×（誤り）"

        if ok:
            st.success("✓ 正解！")
        else:
            st.error(f"✗ 不正解　　正解: {correct_label}")

        exp = (q.get("explanation") or "").strip()
        if q["answer"] is False:
            if exp:
                st.markdown(f"**なぜ×か：** {exp}")
            else:
                st.markdown("**なぜ×か：**（解説文なし）")
        else:
            st.write(exp or "この記述は正しいです。")

        st.write("")
        fc1, fc2 = st.columns(2)
        with fc1:
            if st.button("次の問題 →", type="primary", use_container_width=True, key="next"):
                S.idx += 1
                S.answered = False
                if S.idx >= n:
                    S.screen = "results"
                st.rerun()
        with fc2:
            if st.button("← やり直す", use_container_width=True, key="undo"):
                S.total = max(0, S.total - 1)
                if not ok:
                    # wrong_ids から最後の該当IDを削除
                    for i in range(len(S.wrong_ids) - 1, -1, -1):
                        if S.wrong_ids[i] == q["id"]:
                            S.wrong_ids.pop(i)
                            break
                    S.cumulative_wrong.discard(q["id"])
                else:
                    S.correct = max(0, S.correct - 1)
                S.answered = False
                st.rerun()


# ══════════════════════════════════════════════════════════════════════
# 結果画面
# ══════════════════════════════════════════════════════════════════════
elif S.screen == "results":
    pct = round(S.correct / S.total * 100) if S.total else 0
    st.markdown(f"# 結果: {pct}%")
    st.write(f"{S.total}問中 **{S.correct}問正解**（ミス {S.total - S.correct}問）")

    if pct >= 80:
        st.balloons()
        st.success("素晴らしい成績です！")
    elif pct >= 60:
        st.info("もう少しで合格ライン！")
    else:
        st.warning("復習して再チャレンジしましょう。")

    st.divider()

    wrong_qs = [q for q in S.queue if q["id"] in set(S.wrong_ids)]

    if st.button("もう一度（全問）", type="primary", use_container_width=True, key="retry_all"):
        S.queue    = random.sample(S.queue, len(S.queue))
        S.idx      = 0; S.correct = 0; S.total = 0
        S.wrong_ids = []; S.answered = False; S.screen = "quiz"
        st.rerun()

    if wrong_qs:
        if st.button(f"間違えた問題のみ（{len(wrong_qs)}問）", use_container_width=True, key="retry_wrong"):
            S.queue    = random.sample(wrong_qs, len(wrong_qs))
            S.idx      = 0; S.correct = 0; S.total = 0
            S.wrong_ids = []; S.answered = False; S.screen = "quiz"
            st.rerun()

    if S.cumulative_wrong:
        cw_qs = [q for q in QUESTIONS if q["id"] in S.cumulative_wrong]
        if cw_qs:
            if st.button(f"累計苦手問題（{len(cw_qs)}問）", use_container_width=True, key="retry_cw"):
                S.queue    = random.sample(cw_qs, len(cw_qs))
                S.idx      = 0; S.correct = 0; S.total = 0
                S.wrong_ids = []; S.answered = False; S.screen = "quiz"
                st.rerun()

    if st.button("問題選択に戻る", use_container_width=True, key="go_home"):
        S.screen = "start"
        st.rerun()

    # 間違い一覧
    if wrong_qs:
        with st.expander(f"間違えた問題一覧（{len(wrong_qs)}問）"):
            for wq in wrong_qs:
                exp = (wq.get("explanation") or "").strip()
                cl  = "○（正しい）" if wq["answer"] else "×（誤り）"
                st.markdown(f"**{wq['statement']}**")
                st.caption(f"正解: {cl}")
                if wq["answer"] is False:
                    st.write(f"なぜ×か： {exp or '（解説なし）'}")
                else:
                    st.write(exp or "この記述は正しいです。")
                st.divider()

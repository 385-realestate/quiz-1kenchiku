import streamlit as st
import json, re, random
from streamlit_js_eval import streamlit_js_eval

st.set_page_config(
    page_title="1級施工管理技士○×テスト",
    page_icon="🏗️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<meta name="apple-mobile-web-app-title" content="1級施工管理技士○×テスト">
<meta name="apple-mobile-web-app-capable" content="yes">
<style>
.block-container { max-width: 640px !important; padding: 2.5rem 1rem 4rem !important; }
.stButton > button {
    border-radius: 10px !important; font-size: 15px !important;
    font-weight: 600 !important; min-height: 44px !important;
}
.ans-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; margin:12px 0 4px; }
.ans-btn {
    display:block; text-decoration:none; border-radius:14px;
    font-size:3.2rem; text-align:center; padding:18px 8px 12px;
    font-weight:bold; line-height:1.1; transition:opacity .15s;
}
.ans-btn:active { opacity:.75; }
.ans-btn small { display:block; font-size:.35em; margin-top:4px; }
.ans-maru  { background:#eef4ee; border:2px solid #7aab7a; color:#2d5a2d; }
.ans-batsu { background:#f5eeed; border:2px solid #b87070; color:#7a2d2d; }
[data-testid="stMetricLabel"] p { font-size:11px !important; }
[data-testid="stMetricValue"]   { font-size:20px !important; }
hr { margin:.6rem 0 !important; }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_questions():
    with open("questions.js", encoding="utf-8") as f:
        txt = f.read()
    m = re.search(r"const QUESTIONS = (\[.*\]);", txt, re.DOTALL)
    return json.loads(m.group(1))

QUESTIONS = load_questions()
QMAP  = {q["id"]: q for q in QUESTIONS}
YEARS = sorted(set(q["year"]     for q in QUESTIONS))
CATS  = sorted(set(q["category"] for q in QUESTIONS))

STORAGE_KEY = "k1_quiz_v1"

# ── localStorage ─────────────────────────────────────────────────────
def ls_get():
    """localStorageから読み込む（初回はNone、2回目以降に値が返る）"""
    return streamlit_js_eval(
        js_expressions=f"localStorage.getItem('{STORAGE_KEY}')",
        key="ls_get"
    )

def ls_set(data: dict):
    """localStorageに保存"""
    n = st.session_state.get("_save_n", 0) + 1
    st.session_state["_save_n"] = n
    safe = json.dumps(data, ensure_ascii=False).replace("\\", "\\\\").replace("'", "\\'")
    streamlit_js_eval(
        js_expressions=f"localStorage.setItem('{STORAGE_KEY}', '{safe}'); null",
        key=f"ls_set_{n}"
    )

def ls_del():
    """localStorageから削除"""
    n = st.session_state.get("_save_n", 0) + 1
    st.session_state["_save_n"] = n
    streamlit_js_eval(
        js_expressions=f"localStorage.removeItem('{STORAGE_KEY}'); null",
        key=f"ls_del_{n}"
    )

def save_progress():
    S = st.session_state
    if not S.queue:
        return
    ls_set({
        "queue_ids":        [q["id"] for q in S.queue],
        "idx":              S.idx,
        "correct":          S.correct,
        "total":            S.total,
        "wrong_ids":        S.wrong_ids,
        "answered":         S.answered,
        "last_ok":          S.last_ok,
        "cumulative_wrong": list(S.cumulative_wrong),
    })

# ── セッション初期化 ──────────────────────────────────────────────────
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

# ── localStorageから復元（ページ更新・再起動対策）──────────────────
raw = ls_get()   # 初回None、次のrerunで実際の値が返る

if raw and not st.session_state.get("_storage_restored"):
    try:
        data  = json.loads(raw)
        queue = [QMAP[id] for id in data.get("queue_ids", []) if id in QMAP]
        if queue:
            S.queue    = queue
            S.idx      = min(data.get("idx", 0), len(queue) - 1)
            S.correct  = data.get("correct", 0)
            S.total    = data.get("total",   0)
            S.wrong_ids = data.get("wrong_ids", [])
            S.answered  = data.get("answered",  False)
            S.last_ok   = data.get("last_ok",   None)
            S.cumulative_wrong = set(data.get("cumulative_wrong", []))
            S.screen   = "quiz"
    except Exception:
        pass
    st.session_state["_storage_restored"] = True
    st.rerun()

if not st.session_state.get("_storage_restored"):
    st.session_state["_storage_restored"] = True   # データなし確定


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


# ── ○×ボタン（クエリパラメータ経由）─────────────────────────────────
params = st.query_params
if "ans" in params and S.screen == "quiz" and not S.answered:
    handle_answer(params["ans"] == "1")
    st.query_params.clear()
    save_progress()
    st.rerun()


# ══════════════════════════════════════════════════════════════════════
# スタート画面
# ══════════════════════════════════════════════════════════════════════
if S.screen == "start":
    st.markdown("# 1級建築施工管理技士\n## ○×クイズ")

    if S.saved:
        p = S.saved
        remain = len(p["queue"]) - p["idx"]
        rate   = round(p["correct"] / p["total"] * 100) if p["total"] else 0
        st.info(f"📝 **前回の続きがあります**\n\n残り **{remain}問** ／ 回答済 {p['total']}問 ／ 正答率 {rate}%")
        if st.button("続きから再開 ▶", type="primary", use_container_width=True, key="resume"):
            S.queue, S.idx     = p["queue"], p["idx"]
            S.correct, S.total = p["correct"], p["total"]
            S.wrong_ids = p["wrong_ids"]
            S.answered = False; S.saved = None; S.screen = "quiz"
            save_progress(); st.rerun()
        st.divider()

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
            st.error("条件に合う問題がありません。"); st.stop()
        ls_del()
        S.queue    = random.sample(qs, len(qs)) if order == "シャッフル" else qs[:]
        S.idx      = 0; S.correct = 0; S.total = 0; S.wrong_ids = []
        S.answered = False; S.saved = None; S.screen = "quiz"
        save_progress(); st.rerun()


# ══════════════════════════════════════════════════════════════════════
# クイズ画面
# ══════════════════════════════════════════════════════════════════════
elif S.screen == "quiz":
    queue = S.queue; idx = S.idx; n = len(queue)

    if idx >= n:
        S.screen = "results"; st.rerun()

    q = queue[idx]

    if st.button("← ホームに戻る", key="home"):
        S.saved = dict(queue=queue, idx=idx, correct=S.correct,
                       total=S.total, wrong_ids=S.wrong_ids[:])
        save_progress(); S.screen = "start"; st.rerun()

    st.progress(idx / n)
    m1, m2, m3 = st.columns(3)
    m1.metric("回答済", f"{S.total}問")
    m2.metric("残り",   f"{n - idx - 1}問")
    m3.metric("正答率", f"{round(S.correct/S.total*100)}%" if S.total else "-%")
    st.divider()

    st.caption(f"#{idx+1}/{n}　{q['year']} ｜ {q['category']}")
    if q.get("context"):
        with st.expander("問題文", expanded=True):
            st.write(q["context"])

    st.markdown(f"### {q['statement']}")

    if not S.answered:
        st.markdown(f"""
<div class="ans-grid">
  <a class="ans-btn ans-maru"  href="?ans=1">○<small>正しい</small></a>
  <a class="ans-btn ans-batsu" href="?ans=0">×<small>誤り</small></a>
</div>""", unsafe_allow_html=True)

    else:
        ok = S.last_ok
        cl = "○（正しい）" if q["answer"] else "×（誤り）"
        if ok: st.success("✓ 正解！",              icon=None)
        else:  st.warning(f"✗ 不正解　正解: {cl}", icon=None)

        exp = (q.get("explanation") or "").strip()
        if q["answer"] is False:
            st.markdown(f"**なぜ×か：** {exp or '（解説文なし）'}")
        else:
            st.write(exp or "この記述は正しいです。")

        st.write("")
        fc1, fc2 = st.columns(2)
        with fc1:
            if st.button("次の問題 →", type="primary", use_container_width=True, key="next"):
                S.idx += 1; S.answered = False
                if S.idx >= n: S.screen = "results"; ls_del()
                else: save_progress()
                st.rerun()
        with fc2:
            if st.button("← やり直す", use_container_width=True, key="undo"):
                S.total = max(0, S.total - 1)
                if not ok:
                    for i in range(len(S.wrong_ids)-1, -1, -1):
                        if S.wrong_ids[i] == q["id"]: S.wrong_ids.pop(i); break
                    S.cumulative_wrong.discard(q["id"])
                else:
                    S.correct = max(0, S.correct - 1)
                S.answered = False; save_progress(); st.rerun()


# ══════════════════════════════════════════════════════════════════════
# 結果画面
# ══════════════════════════════════════════════════════════════════════
elif S.screen == "results":
    pct = round(S.correct / S.total * 100) if S.total else 0
    st.markdown(f"# 結果: {pct}%")
    st.write(f"{S.total}問中 **{S.correct}問正解**（ミス {S.total - S.correct}問）")
    if pct >= 80: st.balloons(); st.success("素晴らしい成績です！")
    elif pct >= 60: st.info("もう少しで合格ライン！")
    else: st.warning("復習して再チャレンジしましょう。")
    st.divider()

    wrong_qs = [q for q in S.queue if q["id"] in set(S.wrong_ids)]

    if st.button("もう一度（全問）", type="primary", use_container_width=True, key="r_all"):
        S.queue = random.sample(S.queue, len(S.queue))
        S.idx=0; S.correct=0; S.total=0; S.wrong_ids=[]; S.answered=False; S.screen="quiz"
        save_progress(); st.rerun()
    if wrong_qs:
        if st.button(f"間違えた問題のみ（{len(wrong_qs)}問）", use_container_width=True, key="r_w"):
            S.queue=random.sample(wrong_qs,len(wrong_qs))
            S.idx=0;S.correct=0;S.total=0;S.wrong_ids=[];S.answered=False;S.screen="quiz"
            save_progress(); st.rerun()
    if S.cumulative_wrong:
        cw=[q for q in QUESTIONS if q["id"] in S.cumulative_wrong]
        if cw:
            if st.button(f"累計苦手問題（{len(cw)}問）", use_container_width=True, key="r_cw"):
                S.queue=random.sample(cw,len(cw))
                S.idx=0;S.correct=0;S.total=0;S.wrong_ids=[];S.answered=False;S.screen="quiz"
                save_progress(); st.rerun()
    if st.button("問題選択に戻る", use_container_width=True, key="r_home"):
        S.screen="start"; st.rerun()

    if wrong_qs:
        with st.expander(f"間違えた問題一覧（{len(wrong_qs)}問）"):
            for wq in wrong_qs:
                exp=(wq.get("explanation") or "").strip()
                cl="○（正しい）" if wq["answer"] else "×（誤り）"
                st.markdown(f"**{wq['statement']}**")
                st.caption(f"正解: {cl}")
                if wq["answer"] is False: st.write(f"なぜ×か： {exp or '（解説なし）'}")
                else: st.write(exp or "この記述は正しいです。")
                st.divider()

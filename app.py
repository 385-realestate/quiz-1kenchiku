import hashlib
import streamlit as st
import streamlit.components.v1 as components
from streamlit_js_eval import streamlit_js_eval

st.set_page_config(
    page_title="1級施工管理技士○×テスト",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── パスワード認証（localStorage永続化）──────────────────────
AUTH_TOKEN = "kenchiku_auth_ok"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "save_token" not in st.session_state:
    st.session_state.save_token = False

# ログイン成功後の次レンダリングでlocalStorageに保存
# （st.rerun()より前に実行するとJSが走る前にページが切り替わるため分離）
if st.session_state.save_token:
    streamlit_js_eval(
        js_expressions=f"localStorage.setItem('auth_token', '{AUTH_TOKEN}')",
        key="save_auth"
    )
    st.session_state.save_token = False

# localStorageに認証済みトークンがあれば自動ログイン
if not st.session_state.authenticated:
    saved = streamlit_js_eval(
        js_expressions="localStorage.getItem('auth_token')",
        key="check_auth"
    )
    if saved == AUTH_TOKEN:
        st.session_state.authenticated = True

if not st.session_state.authenticated:
    st.markdown("""
    <style>
    .login-wrap {
        max-width: 420px;
        margin: 80px auto 0;
        padding: 40px 36px;
        background: #1e3a6e;
        border-radius: 12px;
        text-align: center;
        color: #fff;
    }
    .login-wrap h2 { font-size: 1.5rem; margin-bottom: 4px; }
    .login-wrap p  { font-size: 0.85rem; color: #b0bec5; margin-bottom: 24px; }
    .stTextInput [data-baseweb="input"] + div,
    small.st-emotion-cache-1dp5vir,
    [data-testid="InputInstructions"] { display: none !important; }
    [data-testid="stStatusWidget"] { display: none !important; }
    #MainMenu, header, footer { display: none !important; }
    .block-container { max-width: 480px !important; padding-top: 0 !important; }
    </style>
    <div class="login-wrap">
      <h2>🏗️ 1級建築施工管理技士</h2>
      <p>○×クイズ — 過去問&頻出知識</p>
    </div>
    """, unsafe_allow_html=True)

    pw = st.text_input("アクセスパスワード", type="password", placeholder="パスワードを入力")
    if st.button("入る", use_container_width=True):
        if pw == st.secrets["APP_PASSWORD"]:
            st.session_state.authenticated = True
            st.session_state.save_token = True  # 次レンダリングでlocalStorageへ保存
            st.rerun()
        else:
            st.error("パスワードが違います")
    st.stop()
# ───────────────────────────────────────────────────────────

# Streamlit のクロム（ツールバー・バッジ・パディング）を全て非表示
st.markdown("""
<style>
#MainMenu,
header[data-testid="stHeader"],
footer,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stAppViewFooter"],
[data-testid="manage-app-button"],
[data-testid="stDeployButton"],
div[class*="viewerBadge"],
div[class*="ViewerBadge"],
div[class*="badge"],
div[class*="deploy"],
div[class*="Deploy"],
a[href*="streamlit.io"],
a[href*="share.streamlit.io"] { display: none !important; }
.block-container   { padding: 0 !important; max-width: 100% !important; }
[data-testid="stVerticalBlock"]    { gap: 0 !important; padding: 0 !important; }
[data-testid="stAppViewContainer"] { padding: 0 !important; }
iframe { display: block; border: none; }
</style>
<script>
// Streamlit Cloud の "Manage app" ボタンを定期的に削除
(function remove() {
  document.querySelectorAll('button, div, a').forEach(el => {
    if (el.textContent.trim() === 'Manage app' ||
        el.getAttribute('aria-label') === 'Manage app') {
      el.style.display = 'none';
    }
  });
  setTimeout(remove, 800);
})();
</script>
""", unsafe_allow_html=True)

# 画面の高さを1回だけ取得（2回目以降は session_state から使う）
if "wh" not in st.session_state:
    raw = streamlit_js_eval(js_expressions="window.innerHeight", key="get_wh")
    if raw:
        st.session_state.wh = int(raw)

h = st.session_state.get("wh", 800)

# questions.js をインライン化した index.html を構築
# questions_hash が変わると自動でキャッシュ破棄
@st.cache_data
def build_html(questions_hash: str):
    with open("questions.js", encoding="utf-8") as f:
        js = f.read()
    with open("index.html", encoding="utf-8") as f:
        html = f.read()

    # 親フレーム（Streamlit）の "Manage app" ボタンを非表示にするJS
    hide_js = """
<script>
(function hideManage() {
  try {
    var docs = [document];
    try { docs.push(window.parent.document); } catch(e) {}
    docs.forEach(function(doc) {
      // テキストで照合してボタン自体とその親コンテナを非表示
      doc.querySelectorAll('button, a, div').forEach(function(el) {
        if ((el.innerText || '').trim().replace(/[<>]/g,'').trim() === 'Manage app') {
          var target = el;
          // 小さい親要素まで遡って非表示
          while (target.parentElement &&
                 target.parentElement.getBoundingClientRect().height < 200) {
            target = target.parentElement;
          }
          target.style.setProperty('display', 'none', 'important');
        }
      });
      // CSSクラス名でも照合
      doc.querySelectorAll('[class*="deploy"],[class*="Deploy"],[class*="manage"]')
        .forEach(function(el){ el.style.setProperty('display','none','important'); });
    });
  } catch(e) {}
  setTimeout(hideManage, 600);
})();
</script>
"""
    html = html.replace('<script src="questions.js"></script>',
                        f'<script>{js}</script>')
    html = html.replace('</body>', hide_js + '</body>')
    return html

with open("questions.js", encoding="utf-8") as _f:
    _q_hash = hashlib.md5(_f.read().encode()).hexdigest()[:8]
components.html(build_html(_q_hash), height=h, scrolling=True)

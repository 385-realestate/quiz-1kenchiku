import streamlit as st
import streamlit.components.v1 as components
from streamlit_js_eval import streamlit_js_eval

st.set_page_config(
    page_title="1級施工管理技士○×テスト",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Streamlit のクロム（ツールバー・パディング）を全て非表示
st.markdown("""
<style>
#MainMenu,
header[data-testid="stHeader"],
footer,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] { display: none !important; }
.block-container  { padding: 0 !important; max-width: 100% !important; }
[data-testid="stVerticalBlock"]   { gap: 0 !important; padding: 0 !important; }
[data-testid="stAppViewContainer"] { padding: 0 !important; }
iframe { display: block; border: none; }
</style>
""", unsafe_allow_html=True)

# 画面の高さを1回だけ取得（2回目以降は session_state から使う）
if "wh" not in st.session_state:
    raw = streamlit_js_eval(js_expressions="window.innerHeight", key="get_wh")
    if raw:
        st.session_state.wh = int(raw)

h = st.session_state.get("wh", 800)

# questions.js をインライン化した index.html を構築
@st.cache_data
def build_html():
    with open("questions.js", encoding="utf-8") as f:
        js = f.read()
    with open("index.html", encoding="utf-8") as f:
        html = f.read()
    return html.replace('<script src="questions.js"></script>',
                        f'<script>{js}</script>')

components.html(build_html(), height=h, scrolling=True)

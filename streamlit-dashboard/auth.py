"""
auth.py — Módulo de autenticação simples para o Dashboard.
Implementa login com session_state do Streamlit.
"""
import streamlit as st
from config import AUTH_USERS


def check_auth() -> bool:
    """Verifica se o utilizador está autenticado."""
    return st.session_state.get("authenticated", False)


def login_page():
    """Renderiza a página de login com visual premium."""
    st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none; }
        .login-container {
            max-width: 420px;
            margin: 8vh auto;
            padding: 3rem 2.5rem;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(27,33,57,0.08);
        }
        .login-logo {
            text-align: center;
            font-size: 2.4rem;
            font-weight: 800;
            background: linear-gradient(135deg, #3B63FB, #22D3EE);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.3rem;
        }
        .login-subtitle {
            text-align: center;
            color: #7B8AA6;
            font-size: 0.95rem;
            margin-bottom: 2rem;
        }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-logo">📊 ESTG</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-subtitle">Gestão de Ocupação de Espaços</div>', unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("Utilizador", placeholder="admin")
            password = st.text_input("Palavra-passe", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Entrar", use_container_width=True)

            if submitted:
                if username in AUTH_USERS and AUTH_USERS[username] == password:
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = username
                    st.rerun()
                else:
                    st.error("❌ Credenciais inválidas.")

        st.markdown(
            '<p style="text-align:center;color:#94A3B8;font-size:0.8rem;margin-top:1.5rem;">'
            'Acesso restrito — ESTG/IPLeiria</p>',
            unsafe_allow_html=True,
        )


def logout():
    """Encerra a sessão."""
    st.session_state["authenticated"] = False
    st.session_state.pop("username", None)
    st.rerun()

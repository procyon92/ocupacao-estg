"""
auth.py — Módulo de autenticação simples para o Dashboard.
Implementa login com session_state do Streamlit.
"""
import os
import base64
import streamlit as st
from config import AUTH_USERS


def check_auth() -> bool:
    """Verifica se o utilizador está autenticado."""
    return st.session_state.get("authenticated", False)


def _img_to_b64(path: str) -> str:
    """Converte uma imagem para base64 para embedding inline em HTML."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def login_page():
    """Renderiza a página de login — card centrado com fundo gradiente."""
    st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none; }
        [data-testid="stAppViewContainer"] > .main,
        .stApp {
            background: linear-gradient(135deg, #1B2139 0%, #141929 100%) !important;
        }
        .stApp > header { display: none; }

        [data-testid="InputInstructions"] {
            display: none !important;
        }

        /* Card central */
        [data-testid="column"]:nth-of-type(2) {
            max-width: 420px !important;
            margin: 10vh auto !important;
            background: white !important;
            border-radius: 20px !important;
            padding: 2.8rem 2.2rem !important;
            box-shadow: 0 25px 50px rgba(0,0,0,0.25) !important;
        }

        .login-subtitle {
            text-align: center;
            color: #7B8AA6;
            font-size: 0.95rem;
            margin-top: 0.4rem;
            margin-bottom: 1.5rem;
        }

        /* Labels do form */
        [data-testid="stForm"] label p {
            color: #1B2139 !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
        }

        /* Inputs */
        [data-testid="column"]:nth-of-type(2) input {
            color: #1B2139 !important;
            background: #F8FAFC !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 10px !important;
            padding: 0.65rem 0.8rem !important;
            font-size: 0.9rem !important;
        }
        [data-testid="column"]:nth-of-type(2) input:focus {
            border-color: #3B63FB !important;
            box-shadow: 0 0 0 3px rgba(59,99,251,0.15) !important;
        }
        [data-testid="column"]:nth-of-type(2) input::placeholder {
            color: #94A3B8 !important;
        }
        [data-testid="column"]:nth-of-type(2) input[type="password"] {
            padding-right: 3rem !important;
        }

        /* Botão */
        [data-testid="column"]:nth-of-type(2) .stButton button {
            background: linear-gradient(135deg, #3B63FB, #2246D4) !important;
            color: white !important;
            border: none !important;
            border-radius: 10px !important;
            padding: 0.65rem 1.5rem !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            transition: all 0.2s ease !important;
        }
        [data-testid="column"]:nth-of-type(2) .stButton button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(59,99,251,0.3);
        }

        /* Erros */
        [data-testid="column"]:nth-of-type(2) .stAlert {
            background: #FEF2F2 !important;
            border: 1px solid #FECACA !important;
            color: #991B1B !important;
            border-radius: 10px !important;
            font-size: 0.85rem !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Carregar logo como base64 para embedding inline
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
    try:
        logo_b64 = _img_to_b64(logo_path)
        logo_html = (
            f'<img src="data:image/png;base64,{logo_b64}" '
            f'style="height:72px;width:auto;object-fit:contain;display:block;margin:0 auto 0.5rem;"/>'
        )
    except FileNotFoundError:
        # Fallback se o logo não existir
        logo_html = (
            '<div style="display:inline-flex;align-items:center;justify-content:center;'
            'width:64px;height:64px;border-radius:16px;margin:0 auto 0.5rem;'
            'background:linear-gradient(135deg,#3B63FB,#22D3EE);">'
            '<span style="color:white;font-size:1.8rem;font-weight:800;">E</span></div>'
        )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"""
        <div style="text-align:center;margin-bottom:1.2rem;">
            {logo_html}
            <div class="login-subtitle">Gestão de Ocupação de Espaços</div>
        </div>
        """, unsafe_allow_html=True)

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
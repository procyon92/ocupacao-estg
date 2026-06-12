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
    """Renderiza a página de login — card centrado com fundo gradiente."""
    st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none; }
        [data-testid="stAppViewContainer"] > .main,
        .stApp {
            background: linear-gradient(135deg, #1B2139 0%, #141929 100%) !important;
        }
        .stApp > header { display: none; }

        /* Hide the intrusive "Press Enter to apply" instruction */
        [data-testid="InputInstructions"] {
            display: none !important;
        }

        /* Style the middle column as the login card */
        [data-testid="column"]:nth-of-type(2) {
            max-width: 420px !important;
            margin: 10vh auto !important;
            background: white !important;
            border-radius: 20px !important;
            padding: 2.8rem 2.2rem !important;
            box-shadow: 0 25px 50px rgba(0,0,0,0.25) !important;
        }

        /* Logo text */
        .login-logo {
            text-align: center;
            font-size: 2.4rem;
            font-weight: 800;
            background: linear-gradient(135deg, #3B63FB, #22D3EE);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.2rem;
        }
        .login-subtitle {
            text-align: center;
            color: #7B8AA6;
            font-size: 0.95rem;
            margin-bottom: 1.5rem;
        }

        /* Labels inside the form */
        [data-testid="stForm"] label p {
            color: #1B2139 !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
        }

        /* Text inputs inside the card column */
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

        /* Password input — room for the eye icon */
        [data-testid="column"]:nth-of-type(2) input[type="password"] {
            padding-right: 3rem !important;
        }

        /* Submit button */
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

        /* Error messages */
        [data-testid="column"]:nth-of-type(2) .stAlert {
            background: #FEF2F2 !important;
            border: 1px solid #FECACA !important;
            color: #991B1B !important;
            border-radius: 10px !important;
            font-size: 0.85rem !important;
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
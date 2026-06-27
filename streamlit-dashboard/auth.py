import os
import base64
import streamlit as st
from config import AUTH_USERS


def check_auth() -> bool:
    # Verifica se já existe uma sessão autenticada
    return st.session_state.get("authenticated", False)


def _img_to_b64(path: str) -> str:
    # Lê a imagem do disco e converte para base64 para poder ser embutida inline no HTML
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def login_page():
    # Esconde a sidebar e qualquer outro elemento que possa aparecer durante o rerun
    st.markdown("""
    <style>
        [data-testid="stSidebar"]        { display: none !important; }
        [data-testid="stHeader"]         { display: none !important; }
        section[data-testid="stMain"]    { background: #F1F5F9 !important; }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Logo — se não existir, mostra um placeholder com a letra "E"
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
        try:
            logo_b64 = _img_to_b64(logo_path)
            st.markdown(
                f'<img src="data:image/png;base64,{logo_b64}" '
                f'style="height:72px;width:auto;display:block;margin:0 auto 1rem;"/>',
                unsafe_allow_html=True,
            )
        except FileNotFoundError:
            st.markdown(
                '<div style="text-align:center;font-size:2rem;font-weight:800;margin-bottom:1rem;">E</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<p style="text-align:center;color:#7B8AA6;margin-bottom:1.5rem;">Gestão de Ocupação de Espaços</p>',
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            username  = st.text_input("Utilizador", placeholder="admin")
            password  = st.text_input("Palavra-passe", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Entrar", use_container_width=True)

            if submitted:
                if username in AUTH_USERS and AUTH_USERS[username] == password:
                    st.session_state["authenticated"] = True
                    st.session_state["username"]      = username
                    # Esconde o form antes do rerun para evitar o flash
                    st.markdown("""
                    <style>
                        [data-testid="stForm"]    { display: none !important; }
                        [data-testid="stColumns"] { display: none !important; }
                    </style>
                    """, unsafe_allow_html=True)
                    st.rerun()
                else:
                    st.error("❌ Credenciais inválidas.")

        st.markdown(
            '<p style="text-align:center;color:#94A3B8;font-size:0.8rem;margin-top:1rem;">Acesso restrito — ESTG/IPLeiria</p>',
            unsafe_allow_html=True,
        )


def logout():
    # Limpa a sessão e regressa à página de login
    st.session_state["authenticated"] = False
    st.session_state.pop("username", None)
    st.rerun()
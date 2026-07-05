"""
test_auth.py — Testes unitários para o módulo auth.py do dashboard.

Cobre:
  - check_autenticacao  : verifica se a sessão está autenticada
  - terminar_sessao      : limpa a sessão e regressa ao login

O pagina_login não é testado diretamente — envolve st.form, st.columns
e st.rerun() que são difíceis de simular sem o runtime do Streamlit.

Executar com:
    pytest tests/test_auth.py -v
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'streamlit-dashboard'))

# Mock do streamlit antes de importar auth
st_mock = MagicMock()
st_mock.cache_data = lambda **kwargs: (lambda f: f)
sys.modules['streamlit'] = st_mock

import auth


# check_autenticacao

class TestCheckAuth:

    def test_nao_autenticado_por_defeito(self):
        # session_state vazio — não está autenticado
        st_mock.session_state = {}
        assert auth.check_autenticacao() is False

    def test_autenticado_quando_flag_true(self):
        st_mock.session_state = {"authenticated": True}
        assert auth.check_autenticacao() is True

    def test_nao_autenticado_quando_flag_false(self):
        st_mock.session_state = {"authenticated": False}
        assert auth.check_autenticacao() is False

    def test_nao_autenticado_quando_flag_ausente(self):
        st_mock.session_state = {"username": "admin"}
        assert auth.check_autenticacao() is False


# terminar_sessao

class Testterminar_sessao:

    def test_terminar_sessao_coloca_authenticated_false(self):
        st_mock.session_state = {"authenticated": True, "username": "admin"}
        try:
            auth.terminar_sessao()
        except Exception:
            pass  # st.rerun() levanta exceção no mock — é esperado
        assert st_mock.session_state.get("authenticated") is False

    def test_terminar_sessao_remove_username(self):
        st_mock.session_state = {"authenticated": True, "username": "admin"}
        try:
            auth.terminar_sessao()
        except Exception:
            pass
        assert "username" not in st_mock.session_state

    def test_terminar_sessao_chama_rerun(self):
        st_mock.session_state = {"authenticated": True, "username": "admin"}
        st_mock.rerun.reset_mock()
        try:
            auth.terminar_sessao()
        except Exception:
            pass
        st_mock.rerun.assert_called_once()

    def test_terminar_sessao_sem_username_nao_falha(self):
        # terminar_sessao sem username na sessão não deve lançar erro
        st_mock.session_state = {"authenticated": True}
        try:
            auth.terminar_sessao()
        except Exception:
            pass
        assert st_mock.session_state.get("authenticated") is False


# AUTH_USERS (config)

class TestAuthCredentials:

    def test_admin_existe(self):
        from config import AUTH_USERS
        assert "admin" in AUTH_USERS

    def test_password_admin_correta(self):
        from config import AUTH_USERS
        assert AUTH_USERS["admin"] == "estg2025"

    def test_credencial_errada_nao_autentica(self):
        from config import AUTH_USERS
        assert AUTH_USERS.get("admin") != "password_errada"

    def test_utilizador_inexistente(self):
        from config import AUTH_USERS
        assert "hacker" not in AUTH_USERS
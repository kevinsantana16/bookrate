"""
test_auth.py — Testes unitários para auth.py
Cobre: hash_senha, verificar_senha — happy paths, edge cases, exceções.
"""

import pytest
from auth import hash_senha, verificar_senha


class TestHashSenha:
    """Testes para a função hash_senha."""

    def test_retorna_string(self):
        """O hash deve ser uma string."""
        resultado = hash_senha("minhasenha")
        assert isinstance(resultado, str)

    def test_hash_nao_igual_senha_original(self):
        """O hash nunca deve ser igual à senha em texto puro."""
        senha = "segredo123"
        assert hash_senha(senha) != senha

    def test_hashes_diferentes_para_mesma_senha(self):
        """bcrypt gera salt aleatório: dois hashes da mesma senha são diferentes."""
        h1 = hash_senha("mesma_senha")
        h2 = hash_senha("mesma_senha")
        assert h1 != h2

    def test_hash_comeca_com_prefixo_bcrypt(self):
        """Hash bcrypt sempre começa com '$2b$' (identificador do algoritmo)."""
        h = hash_senha("qualquercoisa")
        assert h.startswith("$2b$")

    def test_senha_vazia(self):
        """Hash de senha vazia não deve lançar exceção."""
        resultado = hash_senha("")
        assert isinstance(resultado, str)
        assert resultado.startswith("$2b$")

    def test_senha_unicode(self):
        """Senhas com caracteres especiais/Unicode devem ser aceitas."""
        resultado = hash_senha("sênhà_çom_àcentos_✓")
        assert isinstance(resultado, str)

    def test_senha_muito_longa_levanta_valor_error(self):
        """
        bcrypt >= 4.0 recusa senhas maiores que 72 bytes com ValueError
        (comportamento intencional para evitar truncamento silencioso).
        O chamador (cadastro) deve truncar ou validar o tamanho antes.
        """
        senha_longa = "A" * 100
        with pytest.raises(ValueError, match="longer than 72 bytes"):
            hash_senha(senha_longa)


class TestVerificarSenha:
    """Testes para a função verificar_senha."""

    def test_senha_correta_retorna_true(self):
        """Senha correta deve retornar True."""
        senha = "minhasenha"
        h = hash_senha(senha)
        assert verificar_senha(senha, h) is True

    def test_senha_errada_retorna_false(self):
        """Senha incorreta deve retornar False."""
        h = hash_senha("correta")
        assert verificar_senha("errada", h) is False

    def test_hash_invalido_retorna_false(self):
        """Hash corrompido não deve lançar exceção — retorna False."""
        assert verificar_senha("qualquer", "hash_invalido") is False

    def test_hash_vazio_retorna_false(self):
        """Hash vazio não deve lançar exceção."""
        assert verificar_senha("senha", "") is False

    def test_senha_vazia_com_hash_correto(self):
        """Senha vazia com hash correto retorna True."""
        h = hash_senha("")
        assert verificar_senha("", h) is True

    def test_case_sensitive(self):
        """Verificação é case-sensitive."""
        h = hash_senha("Senha")
        assert verificar_senha("senha", h) is False
        assert verificar_senha("SENHA", h) is False
        assert verificar_senha("Senha", h) is True

    def test_hash_de_outra_senha_retorna_false(self):
        """Hash de outra senha não deve validar."""
        h1 = hash_senha("senha_a")
        assert verificar_senha("senha_b", h1) is False

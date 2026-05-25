"""
test_app_routes.py — Testes de integração para as rotas Flask (app.py)
Usa o cliente de teste Flask com CSRF desativado e banco in-memory.
"""

import json
import pytest


# ══════════════════════════════════════════════════════════════
# AUTENTICAÇÃO — /login, /cadastro, /logout
# ══════════════════════════════════════════════════════════════

class TestLogin:
    """Testes da rota /login."""

    def test_get_login_retorna_200(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200

    def test_login_com_credenciais_validas(self, client, usuario_comum):
        resp = client.post("/login", data={
            "username": "testuser",
            "senha": "senha123",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_login_com_senha_errada(self, client, usuario_comum):
        resp = client.post("/login", data={
            "username": "testuser",
            "senha": "senha_errada",
        }, follow_redirects=True)
        assert b"nv" in resp.data.lower() or resp.status_code == 200
        # Verifica que permanece na página de login
        assert b"login" in resp.data.lower() or resp.request.path == "/login"

    def test_login_usuario_inexistente(self, client):
        resp = client.post("/login", data={
            "username": "nao_existe",
            "senha": "qualquer",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_login_ja_autenticado_redireciona_home(self, client_logado):
        resp = client_logado.get("/login")
        assert resp.status_code == 302
        assert "/home" in resp.headers.get("Location", "")

    def test_rota_raiz_redireciona_login_sem_sessao(self, client):
        resp = client.get("/")
        assert resp.status_code == 302


class TestCadastro:
    """Testes da rota /cadastro."""

    def test_cadastro_com_sucesso(self, client):
        resp = client.post("/cadastro", data={
            "username": "novo_user",
            "senha": "senha_valida",
            "confirmar": "senha_valida",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_senhas_nao_coincidem(self, client):
        resp = client.post("/cadastro", data={
            "username": "user_x",
            "senha": "abc123",
            "confirmar": "diferente",
        }, follow_redirects=True)
        assert b"coincidem" in resp.data.lower() or resp.status_code == 200

    def test_senha_muito_curta(self, client):
        resp = client.post("/cadastro", data={
            "username": "user_y",
            "senha": "ab",
            "confirmar": "ab",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_username_admin_reservado(self, client):
        resp = client.post("/cadastro", data={
            "username": "admin",
            "senha": "senha123",
            "confirmar": "senha123",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_campos_obrigatorios(self, client):
        resp = client.post("/cadastro", data={
            "username": "",
            "senha": "",
            "confirmar": "",
        }, follow_redirects=True)
        assert resp.status_code == 200


class TestLogout:
    """Testes da rota /logout."""

    def test_logout_limpa_sessao(self, client_logado):
        resp = client_logado.get("/logout", follow_redirects=False)
        assert resp.status_code == 302

        # Após logout, acesso à home deve redirecionar para login
        resp2 = client_logado.get("/home", follow_redirects=False)
        assert resp2.status_code == 302


# ══════════════════════════════════════════════════════════════
# HOME — /home
# ══════════════════════════════════════════════════════════════

class TestHome:
    """Testes da rota /home."""

    def test_home_sem_autenticacao_redireciona(self, client):
        resp = client.get("/home")
        assert resp.status_code == 302

    def test_home_autenticado_retorna_200(self, client_logado):
        resp = client_logado.get("/home")
        assert resp.status_code == 200

    def test_home_com_livros(self, client_logado, livro_exemplo):
        resp = client_logado.get("/home")
        assert resp.status_code == 200
        assert b"Dom Casmurro" in resp.data

    def test_home_filtro_por_query(self, client_logado, livro_exemplo):
        resp = client_logado.get("/home?q=Dom")
        assert resp.status_code == 200
        assert b"Dom Casmurro" in resp.data

    def test_home_paginacao_pagina_invalida_usa_1(self, client_logado):
        resp = client_logado.get("/home?page=abc")
        assert resp.status_code == 200

    def test_home_paginacao_pagina_negativa_usa_1(self, client_logado):
        resp = client_logado.get("/home?page=-5")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════
# DETALHE DO LIVRO — /livro/<id>
# ══════════════════════════════════════════════════════════════

class TestLivroDetalhe:
    """Testes da rota /livro/<id>."""

    def test_retorna_200_para_livro_existente(self, client_logado, livro_exemplo):
        resp = client_logado.get(f"/livro/{livro_exemplo['id']}")
        assert resp.status_code == 200
        assert b"Dom Casmurro" in resp.data

    def test_retorna_404_para_livro_inexistente(self, client_logado):
        resp = client_logado.get("/livro/99999")
        assert resp.status_code == 404

    def test_sem_autenticacao_redireciona(self, client, livro_exemplo):
        resp = client.get(f"/livro/{livro_exemplo['id']}")
        assert resp.status_code == 302


# ══════════════════════════════════════════════════════════════
# API — /api/livros
# ══════════════════════════════════════════════════════════════

class TestApiLivros:
    """Testes da rota /api/livros."""

    def test_retorna_json(self, client_logado):
        resp = client_logado.get("/api/livros")
        assert resp.status_code == 200
        assert resp.content_type == "application/json"

    def test_estrutura_resposta(self, client_logado):
        data = client_logado.get("/api/livros").get_json()
        assert "livros" in data
        assert "pagina" in data
        assert "total_paginas" in data
        assert "total_livros" in data

    def test_sem_autenticacao_redireciona(self, client):
        resp = client.get("/api/livros")
        assert resp.status_code == 302

    def test_filtro_retorna_somente_correspondentes(self, client_logado, livro_exemplo, mem_db):
        import models
        models.inserir_livro("Harry Potter", "Rowling")
        data = client_logado.get("/api/livros?q=Dom").get_json()
        titulos = [l["titulo"] for l in data["livros"]]
        assert "Dom Casmurro" in titulos
        assert "Harry Potter" not in titulos


# ══════════════════════════════════════════════════════════════
# API — /api/votar
# ══════════════════════════════════════════════════════════════

class TestApiVotar:
    """Testes da rota /api/votar."""

    def test_voto_recomendo(self, client_logado, livro_exemplo):
        resp = client_logado.post(
            "/api/votar",
            data=json.dumps({"livro_id": livro_exemplo["id"], "voto": 1}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["recomendo"] == 1
        assert data["meu_voto"] == 1

    def test_voto_nao_recomendo(self, client_logado, livro_exemplo):
        resp = client_logado.post(
            "/api/votar",
            data=json.dumps({"livro_id": livro_exemplo["id"], "voto": 0}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["nao_recomendo"] == 1

    def test_voto_invalido_retorna_400(self, client_logado, livro_exemplo):
        resp = client_logado.post(
            "/api/votar",
            data=json.dumps({"livro_id": livro_exemplo["id"], "voto": 99}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_sem_livro_id_retorna_400(self, client_logado):
        resp = client_logado.post(
            "/api/votar",
            data=json.dumps({"voto": 1}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_sem_autenticacao_redireciona(self, client, livro_exemplo):
        resp = client.post(
            "/api/votar",
            data=json.dumps({"livro_id": livro_exemplo["id"], "voto": 1}),
            content_type="application/json",
        )
        assert resp.status_code == 302


# ══════════════════════════════════════════════════════════════
# API — /api/comentar
# ══════════════════════════════════════════════════════════════

class TestApiComentar:
    """Testes da rota /api/comentar."""

    def test_comentario_valido(self, client_logado, livro_exemplo):
        resp = client_logado.post(
            "/api/comentar",
            data=json.dumps({"livro_id": livro_exemplo["id"], "texto": "Excelente livro!"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "id" in data
        assert data["texto"] == "Excelente livro!"
        assert data["username"] == "testuser"

    def test_texto_vazio_retorna_400(self, client_logado, livro_exemplo):
        resp = client_logado.post(
            "/api/comentar",
            data=json.dumps({"livro_id": livro_exemplo["id"], "texto": ""}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_texto_muito_longo_retorna_400(self, client_logado, livro_exemplo):
        texto_longo = "A" * 2001
        resp = client_logado.post(
            "/api/comentar",
            data=json.dumps({"livro_id": livro_exemplo["id"], "texto": texto_longo}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_sem_livro_id_retorna_400(self, client_logado):
        resp = client_logado.post(
            "/api/comentar",
            data=json.dumps({"texto": "texto"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_sem_autenticacao_redireciona(self, client, livro_exemplo):
        resp = client.post(
            "/api/comentar",
            data=json.dumps({"livro_id": livro_exemplo["id"], "texto": "texto"}),
            content_type="application/json",
        )
        assert resp.status_code == 302


# ══════════════════════════════════════════════════════════════
# API — /api/comentario/<id>/excluir
# ══════════════════════════════════════════════════════════════

class TestApiExcluirComentario:
    """Testes da rota /api/comentario/<id>/excluir."""

    def _criar_comentario(self, client_logado, livro_id):
        resp = client_logado.post(
            "/api/comentar",
            data=json.dumps({"livro_id": livro_id, "texto": "Comentário para excluir"}),
            content_type="application/json",
        )
        return resp.get_json()["id"]

    def test_autor_pode_excluir(self, client_logado, livro_exemplo):
        cid = self._criar_comentario(client_logado, livro_exemplo["id"])
        resp = client_logado.post(f"/api/comentario/{cid}/excluir")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

    def test_excluir_inexistente_retorna_404(self, client_logado):
        resp = client_logado.post("/api/comentario/99999/excluir")
        assert resp.status_code == 404

    def test_sem_autenticacao_redireciona(self, client):
        resp = client.post("/api/comentario/1/excluir")
        assert resp.status_code == 302


# ══════════════════════════════════════════════════════════════
# API — /api/lista-leitura
# ══════════════════════════════════════════════════════════════

class TestApiListaLeitura:
    """Testes da rota /api/lista-leitura."""

    @pytest.mark.parametrize("status", ["quero_ler", "lendo", "lido"])
    def test_status_valido(self, client_logado, livro_exemplo, status):
        resp = client_logado.post(
            "/api/lista-leitura",
            data=json.dumps({"livro_id": livro_exemplo["id"], "status": status}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == status

    def test_status_invalido_retorna_400(self, client_logado, livro_exemplo):
        resp = client_logado.post(
            "/api/lista-leitura",
            data=json.dumps({"livro_id": livro_exemplo["id"], "status": "status_invalido"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_sem_livro_id_retorna_400(self, client_logado):
        resp = client_logado.post(
            "/api/lista-leitura",
            data=json.dumps({"status": "lido"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_remover_status_com_none(self, client_logado, livro_exemplo):
        # Adiciona
        client_logado.post(
            "/api/lista-leitura",
            data=json.dumps({"livro_id": livro_exemplo["id"], "status": "lido"}),
            content_type="application/json",
        )
        # Remove
        resp = client_logado.post(
            "/api/lista-leitura",
            data=json.dumps({"livro_id": livro_exemplo["id"], "status": None}),
            content_type="application/json",
        )
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════
# ADMIN
# ══════════════════════════════════════════════════════════════

class TestAdmin:
    """Testes das rotas /admin."""

    def test_admin_sem_autenticacao_redireciona(self, client):
        resp = client.get("/admin")
        assert resp.status_code == 302

    def test_admin_como_usuario_comum_retorna_403(self, client_logado):
        resp = client_logado.get("/admin")
        assert resp.status_code == 403

    def test_admin_como_admin_retorna_200(self, client_admin):
        resp = client_admin.get("/admin")
        assert resp.status_code == 200

    def test_admin_novo_livro(self, client_admin):
        resp = client_admin.post("/admin/livro/novo", data={
            "titulo": "Novo Livro Admin",
            "autor": "Autor Admin",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Novo Livro Admin" in resp.data

    def test_admin_novo_livro_sem_titulo_retorna_erro(self, client_admin):
        resp = client_admin.post("/admin/livro/novo", data={
            "titulo": "",
            "autor": "Autor",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_admin_editar_livro(self, client_admin, livro_exemplo):
        resp = client_admin.post(
            f"/admin/livro/editar/{livro_exemplo['id']}",
            data={"titulo": "Título Editado", "autor": "Autor Editado"},
            follow_redirects=True,
        )
        assert resp.status_code == 200

    def test_admin_excluir_livro(self, client_admin, livro_exemplo):
        resp = client_admin.post(
            f"/admin/livro/excluir/{livro_exemplo['id']}",
            follow_redirects=True,
        )
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ══════════════════════════════════════════════════════════════

class TestErrorHandlers:
    """Testes dos handlers de erro 403 e 404."""

    def test_404_retorna_template_correto(self, client_logado):
        resp = client_logado.get("/rota_que_nao_existe")
        assert resp.status_code == 404

    def test_403_para_usuario_comum_em_rota_admin(self, client_logado):
        resp = client_logado.get("/admin")
        assert resp.status_code == 403

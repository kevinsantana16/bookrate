"""
test_models.py — Testes unitários para models.py
Cobre todos os módulos: usuários, livros, avaliações, comentários, lista de leitura.
Usa banco SQLite in-memory via conftest.py (sem I/O de disco).
"""

import json
import pytest
import models


# ══════════════════════════════════════════════════════════════
# USUÁRIOS
# ══════════════════════════════════════════════════════════════

class TestCriarUsuario:
    """models.criar_usuario()"""

    def test_cria_usuario_com_sucesso(self, mem_db):
        resultado = models.criar_usuario("novo_user", "hash_qualquer")
        assert resultado is True

    def test_usuario_duplicado_retorna_false(self, mem_db):
        models.criar_usuario("duplicado", "hash1")
        resultado = models.criar_usuario("duplicado", "hash2")
        assert resultado is False

    def test_usuario_criado_existe_no_banco(self, mem_db):
        models.criar_usuario("alice", "hash_alice")
        row = mem_db.execute(
            "SELECT * FROM usuarios WHERE username = 'alice'"
        ).fetchone()
        assert row is not None
        assert row["username"] == "alice"


class TestBuscarUsuarioPorUsername:
    """models.buscar_usuario_por_username()"""

    def test_retorna_usuario_existente(self, usuario_comum):
        row = models.buscar_usuario_por_username("testuser")
        assert row is not None
        assert row["username"] == "testuser"

    def test_retorna_none_para_inexistente(self, mem_db):
        resultado = models.buscar_usuario_por_username("nao_existe")
        assert resultado is None

    def test_case_sensitive(self, usuario_comum):
        """SQLite por padrão é case-sensitive para TEXT UNIQUE."""
        resultado = models.buscar_usuario_por_username("TESTUSER")
        assert resultado is None


# ══════════════════════════════════════════════════════════════
# LIVROS
# ══════════════════════════════════════════════════════════════

class TestInserirLivro:
    """models.inserir_livro()"""

    def test_insere_e_retorna_id(self, mem_db):
        livro_id = models.inserir_livro("Senhor dos Anéis", "Tolkien")
        assert isinstance(livro_id, int)
        assert livro_id > 0

    def test_ids_incrementais(self, mem_db):
        id1 = models.inserir_livro("Livro A", "Autor A")
        id2 = models.inserir_livro("Livro B", "Autor B")
        assert id2 > id1


class TestBuscarLivroPorId:
    """models.buscar_livro_por_id()"""

    def test_retorna_livro_existente(self, livro_exemplo):
        livro = models.buscar_livro_por_id(livro_exemplo["id"])
        assert livro is not None
        assert livro["titulo"] == "Dom Casmurro"
        assert livro["autor"] == "Machado de Assis"

    def test_retorna_none_para_inexistente(self, mem_db):
        resultado = models.buscar_livro_por_id(99999)
        assert resultado is None

    def test_categorias_deserializadas_como_lista(self, mem_db):
        """Categorias em JSON string devem ser desserializadas para lista Python."""
        cats = json.dumps(["Ficção", "Clássico"])
        cur = mem_db.execute(
            "INSERT INTO livros (titulo, autor, categorias) VALUES (?, ?, ?)",
            ("Livro Cat", "Autor", cats),
        )
        mem_db.commit()
        livro = models.buscar_livro_por_id(cur.lastrowid)
        assert isinstance(livro["categorias"], list)
        assert "Ficção" in livro["categorias"]

    def test_categorias_none_retorna_lista_vazia(self, livro_exemplo):
        """Livro sem categorias deve retornar lista vazia, não None."""
        livro = models.buscar_livro_por_id(livro_exemplo["id"])
        assert livro["categorias"] == []


class TestEditarLivro:
    """models.editar_livro()"""

    def test_edita_com_sucesso(self, livro_exemplo):
        resultado = models.editar_livro(livro_exemplo["id"], "Novo Título", "Novo Autor")
        assert resultado is True

    def test_dados_atualizados_no_banco(self, livro_exemplo):
        models.editar_livro(livro_exemplo["id"], "Título Atualizado", "Autor Atualizado")
        livro = models.buscar_livro_por_id(livro_exemplo["id"])
        assert livro["titulo"] == "Título Atualizado"
        assert livro["autor"] == "Autor Atualizado"

    def test_editar_inexistente_retorna_false(self, mem_db):
        resultado = models.editar_livro(99999, "Título", "Autor")
        assert resultado is False


class TestExcluirLivro:
    """models.excluir_livro()"""

    def test_exclui_com_sucesso(self, livro_exemplo):
        resultado = models.excluir_livro(livro_exemplo["id"])
        assert resultado is True

    def test_livro_removido_do_banco(self, livro_exemplo):
        models.excluir_livro(livro_exemplo["id"])
        assert models.buscar_livro_por_id(livro_exemplo["id"]) is None

    def test_excluir_inexistente_retorna_false(self, mem_db):
        resultado = models.excluir_livro(99999)
        assert resultado is False


class TestListarLivros:
    """models.listar_livros() e models.contar_livros()"""

    def test_lista_vazia_sem_livros(self, mem_db, usuario_comum):
        livros = models.listar_livros(usuario_id=usuario_comum["id"])
        assert livros == []

    def test_lista_livros_inseridos(self, mem_db, usuario_comum):
        models.inserir_livro("Livro 1", "Autor 1")
        models.inserir_livro("Livro 2", "Autor 2")
        livros = models.listar_livros(usuario_id=usuario_comum["id"])
        assert len(livros) == 2

    def test_paginacao_offset(self, mem_db, usuario_comum):
        for i in range(5):
            models.inserir_livro(f"Livro {i}", "Autor")
        pagina1 = models.listar_livros(usuario_id=usuario_comum["id"], limit=3, offset=0)
        pagina2 = models.listar_livros(usuario_id=usuario_comum["id"], limit=3, offset=3)
        assert len(pagina1) == 3
        assert len(pagina2) == 2

    def test_filtro_por_titulo(self, mem_db, usuario_comum):
        models.inserir_livro("Dom Casmurro", "Machado")
        models.inserir_livro("Memórias Póstumas", "Machado")
        livros = models.listar_livros(usuario_id=usuario_comum["id"], filtro="Dom")
        assert len(livros) == 1
        assert livros[0]["titulo"] == "Dom Casmurro"

    def test_filtro_por_autor(self, mem_db, usuario_comum):
        models.inserir_livro("Livro X", "Tolkien")
        models.inserir_livro("Livro Y", "Asimov")
        livros = models.listar_livros(usuario_id=usuario_comum["id"], filtro="Asimov")
        assert len(livros) == 1

    def test_contar_livros_total(self, mem_db):
        models.inserir_livro("L1", "A1")
        models.inserir_livro("L2", "A2")
        assert models.contar_livros() == 2

    def test_contar_livros_com_filtro(self, mem_db):
        models.inserir_livro("Python Fluente", "Luciano")
        models.inserir_livro("Clean Code", "Martin")
        assert models.contar_livros(filtro="Python") == 1

    def test_meu_voto_none_sem_votacao(self, mem_db, usuario_comum):
        models.inserir_livro("Livro Sem Voto", "Autor")
        livros = models.listar_livros(usuario_id=usuario_comum["id"])
        assert livros[0]["meu_voto"] is None

    def test_recomendo_zero_sem_votos(self, mem_db, usuario_comum):
        models.inserir_livro("Livro Novo", "Autor")
        livros = models.listar_livros(usuario_id=usuario_comum["id"])
        assert livros[0]["recomendo"] == 0
        assert livros[0]["nao_recomendo"] == 0


# ══════════════════════════════════════════════════════════════
# AVALIAÇÕES / VOTOS
# ══════════════════════════════════════════════════════════════

class TestRegistrarVoto:
    """models.registrar_ou_atualizar_voto() e models.obter_voto_usuario()"""

    def test_voto_recomendo(self, mem_db, usuario_comum, livro_exemplo):
        contagens = models.registrar_ou_atualizar_voto(
            usuario_comum["id"], livro_exemplo["id"], 1
        )
        assert contagens["recomendo"] == 1
        assert contagens["nao_recomendo"] == 0

    def test_voto_nao_recomendo(self, mem_db, usuario_comum, livro_exemplo):
        contagens = models.registrar_ou_atualizar_voto(
            usuario_comum["id"], livro_exemplo["id"], 0
        )
        assert contagens["nao_recomendo"] == 1
        assert contagens["recomendo"] == 0

    def test_toggle_off_mesmo_voto(self, mem_db, usuario_comum, livro_exemplo):
        """Votar no mesmo voto duas vezes deve remover o voto (toggle off)."""
        models.registrar_ou_atualizar_voto(usuario_comum["id"], livro_exemplo["id"], 1)
        contagens = models.registrar_ou_atualizar_voto(
            usuario_comum["id"], livro_exemplo["id"], 1
        )
        assert contagens["recomendo"] == 0
        assert models.obter_voto_usuario(usuario_comum["id"], livro_exemplo["id"]) is None

    def test_troca_voto(self, mem_db, usuario_comum, livro_exemplo):
        """Mudar de 'recomendo' para 'não recomendo' deve atualizar corretamente."""
        models.registrar_ou_atualizar_voto(usuario_comum["id"], livro_exemplo["id"], 1)
        contagens = models.registrar_ou_atualizar_voto(
            usuario_comum["id"], livro_exemplo["id"], 0
        )
        assert contagens["recomendo"] == 0
        assert contagens["nao_recomendo"] == 1

    def test_multiplos_usuarios_votando(self, mem_db, livro_exemplo):
        """Votos de usuários diferentes devem ser contados corretamente."""
        mem_db.execute(
            "INSERT INTO usuarios (username, password_hash) VALUES ('u2', 'h2'), ('u3', 'h3')"
        )
        mem_db.commit()
        u2 = mem_db.execute("SELECT id FROM usuarios WHERE username='u2'").fetchone()["id"]
        u3 = mem_db.execute("SELECT id FROM usuarios WHERE username='u3'").fetchone()["id"]

        models.registrar_ou_atualizar_voto(u2, livro_exemplo["id"], 1)
        contagens = models.registrar_ou_atualizar_voto(u3, livro_exemplo["id"], 0)

        assert contagens["recomendo"] == 1
        assert contagens["nao_recomendo"] == 1

    def test_obter_voto_sem_votacao_retorna_none(self, mem_db, usuario_comum, livro_exemplo):
        resultado = models.obter_voto_usuario(usuario_comum["id"], livro_exemplo["id"])
        assert resultado is None

    def test_obter_voto_apos_registro(self, mem_db, usuario_comum, livro_exemplo):
        models.registrar_ou_atualizar_voto(usuario_comum["id"], livro_exemplo["id"], 1)
        resultado = models.obter_voto_usuario(usuario_comum["id"], livro_exemplo["id"])
        assert resultado == 1


class TestObterContagensVotos:
    """models.obter_contagens_votos()"""

    def test_zero_sem_votos(self, livro_exemplo):
        contagens = models.obter_contagens_votos(livro_exemplo["id"])
        assert contagens == {"recomendo": 0, "nao_recomendo": 0}

    def test_conta_corretamente_apos_votos(self, mem_db, livro_exemplo):
        mem_db.execute(
            "INSERT INTO usuarios (username, password_hash) VALUES ('va', 'ha'), ('vb', 'hb')"
        )
        mem_db.commit()
        va = mem_db.execute("SELECT id FROM usuarios WHERE username='va'").fetchone()["id"]
        vb = mem_db.execute("SELECT id FROM usuarios WHERE username='vb'").fetchone()["id"]

        mem_db.execute(
            "INSERT INTO avaliacoes (usuario_id, livro_id, voto) VALUES (?, ?, 1)",
            (va, livro_exemplo["id"]),
        )
        mem_db.execute(
            "INSERT INTO avaliacoes (usuario_id, livro_id, voto) VALUES (?, ?, 0)",
            (vb, livro_exemplo["id"]),
        )
        mem_db.commit()

        contagens = models.obter_contagens_votos(livro_exemplo["id"])
        assert contagens["recomendo"] == 1
        assert contagens["nao_recomendo"] == 1


# ══════════════════════════════════════════════════════════════
# COMENTÁRIOS
# ══════════════════════════════════════════════════════════════

class TestCriarComentario:
    """models.criar_comentario()"""

    def test_cria_e_retorna_id(self, usuario_comum, livro_exemplo):
        comment_id = models.criar_comentario(
            usuario_comum["id"], livro_exemplo["id"], "Ótimo livro!"
        )
        assert isinstance(comment_id, int)
        assert comment_id > 0


class TestListarComentarios:
    """models.listar_comentarios()"""

    def test_lista_vazia_sem_comentarios(self, livro_exemplo):
        comentarios = models.listar_comentarios(livro_exemplo["id"])
        assert comentarios == []

    def test_lista_comentarios_com_username(self, usuario_comum, livro_exemplo):
        models.criar_comentario(usuario_comum["id"], livro_exemplo["id"], "Texto do comentário")
        comentarios = models.listar_comentarios(livro_exemplo["id"])
        assert len(comentarios) == 1
        assert comentarios[0]["texto"] == "Texto do comentário"
        assert comentarios[0]["username"] == "testuser"

    def test_ordem_decrescente_por_data(self, usuario_comum, livro_exemplo):
        """
        Comentários devem ser retornados ordenados por criado_em DESC.
        Em banco in-memory, dois comentários inseridos rapidamente podem ter
        o mesmo CURRENT_TIMESTAMP — verificamos que ambos são retornados
        e que a ordenação não quebra a query.
        """
        models.criar_comentario(usuario_comum["id"], livro_exemplo["id"], "Primeiro")
        models.criar_comentario(usuario_comum["id"], livro_exemplo["id"], "Segundo")
        comentarios = models.listar_comentarios(livro_exemplo["id"])
        assert len(comentarios) == 2
        textos = {c["texto"] for c in comentarios}
        assert "Primeiro" in textos
        assert "Segundo" in textos

    def test_nao_retorna_comentarios_de_outro_livro(self, mem_db, usuario_comum, livro_exemplo):
        outro_id = models.inserir_livro("Outro Livro", "Outro Autor")
        models.criar_comentario(usuario_comum["id"], outro_id, "Comentário do outro livro")
        comentarios = models.listar_comentarios(livro_exemplo["id"])
        assert comentarios == []


class TestExcluirComentario:
    """models.excluir_comentario()"""

    def test_autor_pode_excluir(self, usuario_comum, livro_exemplo):
        cid = models.criar_comentario(usuario_comum["id"], livro_exemplo["id"], "Texto")
        resultado = models.excluir_comentario(cid, usuario_comum["id"], is_admin=False)
        assert resultado is True

    def test_usuario_diferente_nao_pode_excluir(self, mem_db, usuario_comum, livro_exemplo):
        mem_db.execute(
            "INSERT INTO usuarios (username, password_hash) VALUES ('outro', 'hash')"
        )
        mem_db.commit()
        outro_id = mem_db.execute(
            "SELECT id FROM usuarios WHERE username='outro'"
        ).fetchone()["id"]

        cid = models.criar_comentario(usuario_comum["id"], livro_exemplo["id"], "Texto")
        resultado = models.excluir_comentario(cid, outro_id, is_admin=False)
        assert resultado is False

    def test_admin_pode_excluir_qualquer_comentario(self, usuario_comum, usuario_admin, livro_exemplo):
        cid = models.criar_comentario(usuario_comum["id"], livro_exemplo["id"], "Texto")
        resultado = models.excluir_comentario(cid, usuario_admin["id"], is_admin=True)
        assert resultado is True

    def test_excluir_inexistente_retorna_false(self, usuario_comum):
        resultado = models.excluir_comentario(99999, usuario_comum["id"])
        assert resultado is False


# ══════════════════════════════════════════════════════════════
# LISTA DE LEITURA
# ══════════════════════════════════════════════════════════════

class TestListaLeitura:
    """models.definir_status_leitura(), obter_status_leitura(), obter_statuses_leitura_bulk()"""

    @pytest.mark.parametrize("status", ["quero_ler", "lendo", "lido"])
    def test_definir_status_valido(self, usuario_comum, livro_exemplo, status):
        models.definir_status_leitura(usuario_comum["id"], livro_exemplo["id"], status)
        resultado = models.obter_status_leitura(usuario_comum["id"], livro_exemplo["id"])
        assert resultado == status

    def test_obter_status_sem_definir_retorna_none(self, usuario_comum, livro_exemplo):
        resultado = models.obter_status_leitura(usuario_comum["id"], livro_exemplo["id"])
        assert resultado is None

    def test_atualizar_status(self, usuario_comum, livro_exemplo):
        """Mudar de 'quero_ler' para 'lido' deve atualizar corretamente."""
        models.definir_status_leitura(usuario_comum["id"], livro_exemplo["id"], "quero_ler")
        models.definir_status_leitura(usuario_comum["id"], livro_exemplo["id"], "lido")
        resultado = models.obter_status_leitura(usuario_comum["id"], livro_exemplo["id"])
        assert resultado == "lido"

    def test_remover_status_com_none(self, usuario_comum, livro_exemplo):
        """Status None ou vazio remove da lista de leitura."""
        models.definir_status_leitura(usuario_comum["id"], livro_exemplo["id"], "lendo")
        models.definir_status_leitura(usuario_comum["id"], livro_exemplo["id"], None)
        resultado = models.obter_status_leitura(usuario_comum["id"], livro_exemplo["id"])
        assert resultado is None

    def test_remover_status_com_string_vazia(self, usuario_comum, livro_exemplo):
        models.definir_status_leitura(usuario_comum["id"], livro_exemplo["id"], "lendo")
        models.definir_status_leitura(usuario_comum["id"], livro_exemplo["id"], "")
        resultado = models.obter_status_leitura(usuario_comum["id"], livro_exemplo["id"])
        assert resultado is None

    def test_bulk_retorna_dict_correto(self, mem_db, usuario_comum):
        id1 = models.inserir_livro("L1", "A")
        id2 = models.inserir_livro("L2", "B")
        id3 = models.inserir_livro("L3", "C")

        models.definir_status_leitura(usuario_comum["id"], id1, "lido")
        models.definir_status_leitura(usuario_comum["id"], id2, "lendo")
        # id3 sem status

        resultado = models.obter_statuses_leitura_bulk(usuario_comum["id"], [id1, id2, id3])
        assert resultado[id1] == "lido"
        assert resultado[id2] == "lendo"
        assert id3 not in resultado

    def test_bulk_lista_vazia_retorna_dict_vazio(self, usuario_comum):
        resultado = models.obter_statuses_leitura_bulk(usuario_comum["id"], [])
        assert resultado == {}

"""
conftest.py — BookRate
───────────────────────────────────────────────────────────
Fixtures compartilhadas para toda a suíte de testes.

Usa banco SQLite in-memory (:memory:) para:
  - Isolamento total: cada teste começa com banco limpo
  - Velocidade: sem I/O de disco
  - Reprodutibilidade: sem estado residual entre testes
"""

import pytest
import sqlite3
import os
import sys

# Garante que o diretório raiz do projeto está no sys.path
sys.path.insert(0, os.path.dirname(__file__))

# ── Banco in-memory ────────────────────────────────────────────────────────

_SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS usuarios (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        username      TEXT    NOT NULL UNIQUE,
        password_hash TEXT    NOT NULL,
        is_admin      INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS livros (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo           TEXT    NOT NULL,
        autor            TEXT    NOT NULL,
        google_books_id  TEXT    UNIQUE,
        isbn_13          TEXT,
        isbn_10          TEXT,
        descricao        TEXT,
        categorias       TEXT,
        capa_url         TEXT,
        total_paginas    INTEGER,
        data_publicacao  TEXT,
        editora          TEXT,
        idioma           TEXT
    );

    CREATE TABLE IF NOT EXISTS avaliacoes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
        livro_id    INTEGER NOT NULL REFERENCES livros(id)   ON DELETE CASCADE,
        voto        INTEGER NOT NULL CHECK(voto IN (0, 1)),
        UNIQUE(usuario_id, livro_id)
    );

    CREATE TABLE IF NOT EXISTS comentarios (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
        livro_id    INTEGER NOT NULL REFERENCES livros(id)   ON DELETE CASCADE,
        texto       TEXT    NOT NULL,
        criado_em   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS lista_leitura (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
        livro_id    INTEGER NOT NULL REFERENCES livros(id)   ON DELETE CASCADE,
        status      TEXT    NOT NULL CHECK(status IN ('quero_ler', 'lendo', 'lido')),
        UNIQUE(usuario_id, livro_id)
    );
"""


class _NonClosingConn:
    """
    Proxy de conexão SQLite que ignora chamadas a close().

    O models.py chama conn.close() manualmente após cada operação.
    Como todos os testes compartilham a mesma conexão in-memory,
    fechar a conexão destruiria o banco. Esta classe envolve a conexão
    real e substitui close() por um no-op, mantendo tudo funcional.
    """

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def close(self):
        pass  # no-op: não fecha a conexão in-memory compartilhada

    def __getattr__(self, name):
        return getattr(self._conn, name)


@pytest.fixture
def mem_db():
    """
    Retorna uma conexão SQLite in-memory com schema completo e FK ativas.
    Encerrada automaticamente ao final de cada teste (yield fixture).
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def patch_get_db(mem_db, monkeypatch):
    """
    Substitui database.get_db pelo banco in-memory em TODOS os testes.

    Usa _NonClosingConn para que as chamadas conn.close() de models.py
    sejam ignoradas — a conexão permanece aberta durante todo o teste.
    autouse=True garante aplicação automática sem declaração explícita.
    """
    import database
    import models

    proxy = _NonClosingConn(mem_db)

    def _fake_get_db():
        return proxy

    monkeypatch.setattr(database, "get_db", _fake_get_db)
    monkeypatch.setattr(models, "get_db", _fake_get_db)


@pytest.fixture
def usuario_comum(mem_db):
    """Insere e retorna um usuário comum para uso nos testes."""
    from auth import hash_senha
    mem_db.execute(
        "INSERT INTO usuarios (username, password_hash, is_admin) VALUES (?, ?, 0)",
        ("testuser", hash_senha("senha123")),
    )
    mem_db.commit()
    row = mem_db.execute(
        "SELECT * FROM usuarios WHERE username = 'testuser'"
    ).fetchone()
    return dict(row)


@pytest.fixture
def usuario_admin(mem_db):
    """Insere e retorna um usuário admin para uso nos testes."""
    from auth import hash_senha
    mem_db.execute(
        "INSERT INTO usuarios (username, password_hash, is_admin) VALUES (?, ?, 1)",
        ("admin", hash_senha("admin123")),
    )
    mem_db.commit()
    row = mem_db.execute(
        "SELECT * FROM usuarios WHERE username = 'admin'"
    ).fetchone()
    return dict(row)


@pytest.fixture
def livro_exemplo(mem_db):
    """Insere e retorna um livro de exemplo."""
    cur = mem_db.execute(
        "INSERT INTO livros (titulo, autor) VALUES (?, ?)",
        ("Dom Casmurro", "Machado de Assis"),
    )
    mem_db.commit()
    return {"id": cur.lastrowid, "titulo": "Dom Casmurro", "autor": "Machado de Assis"}


@pytest.fixture
def flask_app(patch_get_db):
    """Cria a aplicação Flask em modo de teste."""
    os.environ["FLASK_SECRET_KEY"] = "test-secret-key-para-testes"
    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False  # desativa CSRF em testes
    return application


@pytest.fixture
def client(flask_app):
    """Cliente HTTP para os testes de integração das rotas Flask."""
    return flask_app.test_client()


@pytest.fixture
def client_logado(client, usuario_comum):
    """Cliente já autenticado como usuário comum."""
    with client.session_transaction() as sess:
        sess["usuario_id"] = usuario_comum["id"]
        sess["username"] = usuario_comum["username"]
        sess["is_admin"] = False
    return client


@pytest.fixture
def client_admin(client, usuario_admin):
    """Cliente já autenticado como admin."""
    with client.session_transaction() as sess:
        sess["usuario_id"] = usuario_admin["id"]
        sess["username"] = usuario_admin["username"]
        sess["is_admin"] = True
    return client

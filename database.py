import sqlite3
import os
from auth import hash_senha
from flask import g, has_app_context

DB_PATH = os.path.join(os.path.dirname(__file__), "livros.db")


def _abrir_conexao():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


class _RequestConnection:
    """Proxy para a conexao compartilhada do request."""

    def __init__(self, conn):
        self._conn = conn

    def close(self):
        pass

    def real_close(self):
        self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_db():
    """Retorna uma conexão por request Flask ou uma conexão independente."""
    if has_app_context():
        if "db" not in g:
            g.db = _RequestConnection(_abrir_conexao())
        return g.db
    return _abrir_conexao()


def close_db(conn) -> None:
    """Fecha conexões independentes, mantendo a conexão do request aberta."""
    if has_app_context() and getattr(g, "db", None) is conn:
        return
    conn.close()


def _migrar_colunas(cur):
    """
    Adiciona colunas novas à tabela livros em bancos existentes.
    SQLite não suporta 'ADD COLUMN IF NOT EXISTS', então usamos try/except.
    """
    novas_colunas = [
        ("google_books_id", "TEXT"),
        ("isbn_13",         "TEXT"),
        ("isbn_10",         "TEXT"),
        ("descricao",       "TEXT"),
        ("categorias",      "TEXT"),
        ("capa_url",        "TEXT"),
        ("total_paginas",   "INTEGER"),
        ("data_publicacao", "TEXT"),
        ("editora",         "TEXT"),
        ("idioma",          "TEXT"),
    ]
    existentes = {row[1] for row in cur.execute("PRAGMA table_info(livros)").fetchall()}
    for col, tipo in novas_colunas:
        if col not in existentes:
            cur.execute(f"ALTER TABLE livros ADD COLUMN {col} {tipo}")


def init_db():
    """Cria tabelas, migra colunas e semeia dados iniciais se necessário."""
    conn = get_db()
    cur = conn.cursor()

    # ── Tabelas base ──────────────────────────────────────────────────────────
    cur.executescript("""
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
    """)

    # ── Migração de colunas para bancos já existentes ─────────────────────────
    _migrar_colunas(cur)
    conn.commit()

    # ── Índices ───────────────────────────────────────────────────────────────
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_livros_google_id
        ON livros(google_books_id)
        WHERE google_books_id IS NOT NULL
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_avaliacoes_livro_id
        ON avaliacoes(livro_id)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_comentarios_livro_id
        ON comentarios(livro_id)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_lista_leitura_usuario
        ON lista_leitura(usuario_id, livro_id)
    """)

    # ── Usuário admin ─────────────────────────────────────────────────────────
    admin_username = os.environ.get("BOOKRATE_ADMIN_USERNAME")
    admin_password = os.environ.get("BOOKRATE_ADMIN_PASSWORD")
    if admin_username and admin_password:
        senha_bytes = len(admin_password.encode("utf-8"))
        if len(admin_password) < 12 or senha_bytes > 72:
            raise ValueError("BOOKRATE_ADMIN_PASSWORD deve ter entre 12 e 72 bytes.")
        admin = cur.execute(
            "SELECT id FROM usuarios WHERE username = ?", (admin_username,)
        ).fetchone()
        if not admin:
            cur.execute(
                "INSERT INTO usuarios (username, password_hash, is_admin) VALUES (?, ?, 1)",
                (admin_username, hash_senha(admin_password)),
            )
            print(f"[DB] Usuário administrador criado: {admin_username}")

    conn.commit()
    conn.close()

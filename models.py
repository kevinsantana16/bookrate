import json
import sqlite3
from database import get_db


# ──────────────────────────────────────────────
# USUÁRIOS
# ──────────────────────────────────────────────

def criar_usuario(username: str, password_hash: str) -> bool:
    """Insere novo usuário. Retorna False se o username já existir."""
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO usuarios (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def buscar_usuario_por_username(username: str):
    """Retorna a linha do usuário ou None."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    return row


# ──────────────────────────────────────────────
# LIVROS
# ──────────────────────────────────────────────

def _deserializar_categorias(livro: dict) -> dict:
    """Converte o campo 'categorias' de JSON string para lista Python."""
    raw = livro.get("categorias")
    if raw:
        try:
            livro["categorias"] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            livro["categorias"] = [raw]
    else:
        livro["categorias"] = []
    return livro


def listar_livros(usuario_id: int, offset: int = 0, limit: int = 12, filtro: str = "") -> list:
    """
    Retorna uma página de livros com contagens de votos e voto do usuário,
    tudo em uma única query (elimina o problema N+1).
    Ordenação estável por id DESC para paginação consistente.
    """
    conn = get_db()

    base_query = """
        SELECT l.*,
               COALESCE(v.recomendo, 0)     AS recomendo,
               COALESCE(v.nao_recomendo, 0) AS nao_recomendo,
               a.voto                       AS meu_voto
        FROM livros l
        LEFT JOIN (
            SELECT livro_id,
                   SUM(CASE WHEN voto = 1 THEN 1 ELSE 0 END) AS recomendo,
                   SUM(CASE WHEN voto = 0 THEN 1 ELSE 0 END) AS nao_recomendo
            FROM avaliacoes
            GROUP BY livro_id
        ) v ON l.id = v.livro_id
        LEFT JOIN avaliacoes a ON l.id = a.livro_id AND a.usuario_id = ?
    """

    if filtro:
        query = base_query + " WHERE l.titulo LIKE ? OR l.autor LIKE ? ORDER BY l.id DESC LIMIT ? OFFSET ?"
        params = (usuario_id, f"%{filtro}%", f"%{filtro}%", limit, offset)
    else:
        query = base_query + " ORDER BY l.id DESC LIMIT ? OFFSET ?"
        params = (usuario_id, limit, offset)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    livros = []
    for r in rows:
        livro = dict(r)
        # meu_voto fica None se o usuário ainda não votou
        if livro["meu_voto"] is None:
            livro["meu_voto"] = None
        livros.append(_deserializar_categorias(livro))
    return livros


def contar_livros(filtro: str = "") -> int:
    """Total de livros (usado para calcular número de páginas)."""
    conn = get_db()
    if filtro:
        count = conn.execute(
            "SELECT COUNT(*) FROM livros WHERE titulo LIKE ? OR autor LIKE ?",
            (f"%{filtro}%", f"%{filtro}%"),
        ).fetchone()[0]
    else:
        count = conn.execute("SELECT COUNT(*) FROM livros").fetchone()[0]
    conn.close()
    return count


def buscar_livro_por_id(livro_id: int):
    """Retorna um livro pelo id ou None."""
    conn = get_db()
    row = conn.execute("SELECT * FROM livros WHERE id = ?", (livro_id,)).fetchone()
    conn.close()
    return _deserializar_categorias(dict(row)) if row else None


def buscar_livro_detalhes(livro_id: int, usuario_id: int):
    """
    Retorna um livro com contagens de votos e voto do usuário,
    ideal para a página de detalhes.
    """
    conn = get_db()
    row = conn.execute(
        """
        SELECT l.*,
               COALESCE(v.recomendo, 0)     AS recomendo,
               COALESCE(v.nao_recomendo, 0) AS nao_recomendo,
               a.voto                       AS meu_voto
        FROM livros l
        LEFT JOIN (
            SELECT livro_id,
                   SUM(CASE WHEN voto = 1 THEN 1 ELSE 0 END) AS recomendo,
                   SUM(CASE WHEN voto = 0 THEN 1 ELSE 0 END) AS nao_recomendo
            FROM avaliacoes
            WHERE livro_id = ?
        ) v ON l.id = v.livro_id
        LEFT JOIN avaliacoes a ON l.id = a.livro_id AND a.usuario_id = ?
        WHERE l.id = ?
        """,
        (livro_id, usuario_id, livro_id),
    ).fetchone()
    conn.close()
    if not row:
        return None
    livro = dict(row)
    return _deserializar_categorias(livro)


def inserir_livro(titulo: str, autor: str) -> int:
    """Insere livro e retorna o novo id."""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO livros (titulo, autor) VALUES (?, ?)", (titulo, autor)
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def editar_livro(livro_id: int, titulo: str, autor: str) -> bool:
    """Edita título e autor de um livro. Retorna True se encontrou e editou."""
    conn = get_db()
    cur = conn.execute(
        "UPDATE livros SET titulo = ?, autor = ? WHERE id = ?",
        (titulo, autor, livro_id),
    )
    conn.commit()
    alterado = cur.rowcount > 0
    conn.close()
    return alterado


def excluir_livro(livro_id: int) -> bool:
    """Exclui livro e suas avaliações (CASCADE). Retorna True se excluiu."""
    conn = get_db()
    cur = conn.execute("DELETE FROM livros WHERE id = ?", (livro_id,))
    conn.commit()
    excluido = cur.rowcount > 0
    conn.close()
    return excluido


def listar_todos_livros() -> list:
    """Lista todos os livros ordenados por título (para a tela admin)."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM livros ORDER BY titulo ASC").fetchall()
    conn.close()
    return [_deserializar_categorias(dict(r)) for r in rows]


# ──────────────────────────────────────────────
# AVALIAÇÕES / VOTOS
# ──────────────────────────────────────────────

def obter_contagens_votos(livro_id: int) -> dict:
    """
    Retorna {'recomendo': N, 'nao_recomendo': M} para um livro.
    Usa uma única query com SUM(CASE) para eficiência.
    """
    conn = get_db()
    row = conn.execute(
        """
        SELECT
            SUM(CASE WHEN voto = 1 THEN 1 ELSE 0 END) AS recomendo,
            SUM(CASE WHEN voto = 0 THEN 1 ELSE 0 END) AS nao_recomendo
        FROM avaliacoes
        WHERE livro_id = ?
        """,
        (livro_id,),
    ).fetchone()
    conn.close()
    return {
        "recomendo":     int(row["recomendo"]     or 0),
        "nao_recomendo": int(row["nao_recomendo"] or 0),
    }


def obter_voto_usuario(usuario_id: int, livro_id: int):
    """Retorna o voto atual (0 ou 1) do usuário para o livro, ou None."""
    conn = get_db()
    row = conn.execute(
        "SELECT voto FROM avaliacoes WHERE usuario_id = ? AND livro_id = ?",
        (usuario_id, livro_id),
    ).fetchone()
    conn.close()
    return row["voto"] if row else None


def registrar_ou_atualizar_voto(usuario_id: int, livro_id: int, novo_voto: int) -> dict:
    """
    Insere ou atualiza o voto do usuário para um livro.
    Se o usuário votar no mesmo voto já registrado, o voto é removido (toggle off).
    Retorna os novos contadores.
    Lança sqlite3.IntegrityError se livro_id não existir.
    """
    conn = get_db()
    voto_atual = conn.execute(
        "SELECT voto FROM avaliacoes WHERE usuario_id = ? AND livro_id = ?",
        (usuario_id, livro_id),
    ).fetchone()

    if voto_atual is not None and voto_atual["voto"] == novo_voto:
        # Mesmo voto: remover (toggle off)
        conn.execute(
            "DELETE FROM avaliacoes WHERE usuario_id = ? AND livro_id = ?",
            (usuario_id, livro_id),
        )
    else:
        # Novo voto ou troca: INSERT OR REPLACE
        conn.execute(
            """
            INSERT INTO avaliacoes (usuario_id, livro_id, voto)
            VALUES (?, ?, ?)
            ON CONFLICT(usuario_id, livro_id) DO UPDATE SET voto = excluded.voto
            """,
            (usuario_id, livro_id, novo_voto),
        )

    conn.commit()
    conn.close()
    return obter_contagens_votos(livro_id)


# ──────────────────────────────────────────────
# COMENTÁRIOS / RESENHAS
# ──────────────────────────────────────────────

def criar_comentario(usuario_id: int, livro_id: int, texto: str) -> int:
    """Insere um comentário e retorna o novo id."""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO comentarios (usuario_id, livro_id, texto) VALUES (?, ?, ?)",
        (usuario_id, livro_id, texto),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def listar_comentarios(livro_id: int) -> list:
    """Retorna todos os comentários de um livro, com username do autor."""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT c.id, c.texto, c.criado_em, c.usuario_id,
               u.username, u.is_admin
        FROM comentarios c
        JOIN usuarios u ON c.usuario_id = u.id
        WHERE c.livro_id = ?
        ORDER BY c.criado_em DESC
        """,
        (livro_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def excluir_comentario(comentario_id: int, usuario_id: int, is_admin: bool = False) -> bool:
    """
    Exclui um comentário. Apenas o autor ou um admin pode excluir.
    Retorna True se excluiu.
    """
    conn = get_db()
    if is_admin:
        cur = conn.execute("DELETE FROM comentarios WHERE id = ?", (comentario_id,))
    else:
        cur = conn.execute(
            "DELETE FROM comentarios WHERE id = ? AND usuario_id = ?",
            (comentario_id, usuario_id),
        )
    conn.commit()
    excluido = cur.rowcount > 0
    conn.close()
    return excluido


# ──────────────────────────────────────────────
# LISTA DE LEITURA
# ──────────────────────────────────────────────

def definir_status_leitura(usuario_id: int, livro_id: int, status: str) -> bool:
    """
    Define o status de leitura de um livro para o usuário.
    Status válidos: 'quero_ler', 'lendo', 'lido'.
    Se o status for None ou vazio, remove da lista.
    """
    conn = get_db()
    if not status:
        conn.execute(
            "DELETE FROM lista_leitura WHERE usuario_id = ? AND livro_id = ?",
            (usuario_id, livro_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO lista_leitura (usuario_id, livro_id, status)
            VALUES (?, ?, ?)
            ON CONFLICT(usuario_id, livro_id) DO UPDATE SET status = excluded.status
            """,
            (usuario_id, livro_id, status),
        )
    conn.commit()
    conn.close()
    return True


def obter_status_leitura(usuario_id: int, livro_id: int):
    """Retorna o status de leitura do usuário para o livro, ou None."""
    conn = get_db()
    row = conn.execute(
        "SELECT status FROM lista_leitura WHERE usuario_id = ? AND livro_id = ?",
        (usuario_id, livro_id),
    ).fetchone()
    conn.close()
    return row["status"] if row else None


def obter_statuses_leitura_bulk(usuario_id: int, livro_ids: list) -> dict:
    """
    Retorna um dict { livro_id: status } para uma lista de livros.
    Usado para enriquecer a listagem de cards sem N+1.
    """
    if not livro_ids:
        return {}
    conn = get_db()
    placeholders = ",".join("?" for _ in livro_ids)
    rows = conn.execute(
        f"SELECT livro_id, status FROM lista_leitura WHERE usuario_id = ? AND livro_id IN ({placeholders})",
        [usuario_id] + list(livro_ids),
    ).fetchall()
    conn.close()
    return {r["livro_id"]: r["status"] for r in rows}

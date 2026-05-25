"""
google_books_seeder.py
──────────────────────────────────────────────────────────────
Script de integração com a Google Books API.

Como usar:
    python google_books_seeder.py

Responsabilidades:
  1. Migração idempotente: adiciona novas colunas à tabela 'livros'
     se ainda não existirem (seguro para re-execução).
  2. Busca livros via google_books_client (paginação + backoff).
  3. Persistência via Upsert — padrão ON CONFLICT idêntico ao
     usado em models.py (registrar_ou_atualizar_voto).
  4. Relatório final: inseridos vs. atualizados.

Padrão de BD: sqlite3 puro + conn.row_factory = sqlite3.Row,
alinhado com database.py e models.py do projeto.
──────────────────────────────────────────────────────────────
"""

import os
import sys
from pathlib import Path

from database import get_db, init_db
from google_books_client import buscar_livros

# ──────────────────────────────────────────────
# CARREGAMENTO SEGURO DE VARIÁVEIS DE AMBIENTE
# ──────────────────────────────────────────────

def _carregar_env() -> None:
    """
    Carrega variáveis de ambiente a partir do ficheiro .env na raiz do projeto.
    Usa apenas a stdlib (os + pathlib) — sem dependências externas.

    Formato suportado:
        CHAVE=valor        # atribuição simples
        # comentário       # linhas ignoradas
        CHAVE=             # valor vazio (mantém None no os.environ)

    O ficheiro .env NUNCA deve ser versionado no Git (ver .gitignore).
    Use .env.example como template público sem segredos reais.
    """
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return  # sem .env é válido (variáveis podem vir do sistema)

    with env_path.open(encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, _, valor = linha.partition("=")
            chave = chave.strip()
            valor = valor.strip()
            # Remove aspas simples ou duplas envolventes (ex: KEY="value" → value)
            if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ('"', "'"):
                valor = valor[1:-1]
            # Não sobrescreve variáveis já definidas no ambiente do sistema
            os.environ.setdefault(chave, valor)


# Carrega o .env antes de ler qualquer configuração
_carregar_env()

# ──────────────────────────────────────────────
# CONFIGURAÇÃO — lida de variáveis de ambiente
# ──────────────────────────────────────────────

# Chave da Google Books API — definida em .env (NUNCA hardcoded aqui)
# Para configurar: edite o ficheiro .env e defina GOOGLE_BOOKS_API_KEY=SUA_CHAVE
API_KEY: str | None = os.environ.get("GOOGLE_BOOKS_API_KEY") or None

# Idioma dos resultados (ISO 639-1). Vazio = sem restrição.
IDIOMA: str | None = os.environ.get("GOOGLE_BOOKS_LANG") or None

# Queries de busca — personalize à vontade
QUERIES_DE_BUSCA: list[str] = [
    "romance brasileiro contemporâneo",
    "ficção científica clássica",
    "literatura portuguesa",
    "fantasia épica bestseller",
    "policial noir",
]


# ──────────────────────────────────────────────
# MIGRAÇÃO — adiciona colunas novas (idempotente)
# ──────────────────────────────────────────────

_NOVAS_COLUNAS = [
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


def _garantir_colunas(conn) -> None:
    """
    Adiciona as colunas novas à tabela 'livros' se ainda não existirem.
    Usa PRAGMA table_info para introspecção — totalmente seguro para
    re-execução sem erros (idempotente).
    """
    colunas_existentes = {
        row[1]
        for row in conn.execute("PRAGMA table_info(livros)").fetchall()
    }

    for nome, tipo in _NOVAS_COLUNAS:
        if nome not in colunas_existentes:
            conn.execute(f"ALTER TABLE livros ADD COLUMN {nome} {tipo}")
            print(f"[MIGRAÇÃO] Coluna '{nome}' ({tipo}) adicionada à tabela 'livros'.")

    # Índice único parcial para google_books_id (ignora NULLs dos livros do seed original)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_livros_google_books_id
        ON livros (google_books_id)
        WHERE google_books_id IS NOT NULL
    """)
    conn.commit()
    print("[MIGRAÇÃO] Schema verificado e atualizado.")


# ──────────────────────────────────────────────
# PERSISTÊNCIA — Upsert (INSERT ou UPDATE)
# ──────────────────────────────────────────────

def persistir_livros(livros: list) -> tuple:
    """
    Faz Upsert de cada livro na BD usando o padrão do projeto:
    verifica existência → INSERT ou UPDATE.

    Livros do seed original (google_books_id = NULL) são ignorados
    para não sobrescrever dados manuais.

    Returns:
        Tupla (inseridos: int, atualizados: int).
    """
    conn = get_db()
    inseridos = 0
    atualizados = 0

    for livro in livros:
        gid = livro.get("google_books_id")
        if not gid:
            continue  # pula entradas sem ID da API

        existe = conn.execute(
            "SELECT id FROM livros WHERE google_books_id = ?", (gid,)
        ).fetchone()

        if existe:
            # Livro já na BD → atualiza metadados (Upsert — parte UPDATE)
            conn.execute(
                """
                UPDATE livros SET
                    titulo          = ?,
                    autor           = ?,
                    editora         = ?,
                    data_publicacao = ?,
                    descricao       = ?,
                    isbn_13         = ?,
                    isbn_10         = ?,
                    total_paginas   = ?,
                    categorias      = ?,
                    idioma          = ?,
                    capa_url        = ?
                WHERE google_books_id = ?
                """,
                (
                    livro["titulo"],
                    livro["autor"],
                    livro.get("editora"),
                    livro.get("data_publicacao"),
                    livro.get("descricao"),
                    livro.get("isbn_13"),
                    livro.get("isbn_10"),
                    livro.get("total_paginas"),
                    livro.get("categorias"),
                    livro.get("idioma"),
                    livro.get("capa_url"),
                    gid,
                ),
            )
            atualizados += 1
        else:
            # Livro novo → insere (Upsert — parte INSERT)
            conn.execute(
                """
                INSERT INTO livros (
                    titulo, autor, google_books_id,
                    editora, data_publicacao, descricao,
                    isbn_13, isbn_10, total_paginas,
                    categorias, idioma, capa_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    livro["titulo"],
                    livro["autor"],
                    gid,
                    livro.get("editora"),
                    livro.get("data_publicacao"),
                    livro.get("descricao"),
                    livro.get("isbn_13"),
                    livro.get("isbn_10"),
                    livro.get("total_paginas"),
                    livro.get("categorias"),
                    livro.get("idioma"),
                    livro.get("capa_url"),
                ),
            )
            inseridos += 1

    conn.commit()
    conn.close()
    return inseridos, atualizados


# ──────────────────────────────────────────────
# PONTO DE ENTRADA
# ──────────────────────────────────────────────

def main() -> None:
    separador = "=" * 58
    print(separador)
    print("  Google Books Seeder — Sistema de Avaliação de Livros")
    print(separador)

    # 1. Garante que a BD base existe (cria tabelas se necessário)
    init_db()

    # 2. Migração idempotente das novas colunas
    conn = get_db()
    _garantir_colunas(conn)
    conn.close()

    total_inseridos = 0
    total_atualizados = 0
    queries_com_erro = []

    # 3. Processa cada query de busca
    for i, query in enumerate(QUERIES_DE_BUSCA, start=1):
        print(f"\n[{i}/{len(QUERIES_DE_BUSCA)}] Query: '{query}'")
        print("-" * 45)
        try:
            livros = buscar_livros(query, api_key=API_KEY, lang=IDIOMA)
            print(f"[API] {len(livros)} livros obtidos e mapeados.")

            ins, atu = persistir_livros(livros)
            total_inseridos += ins
            total_atualizados += atu

            print(f"[BD]  +{ins} inseridos | ~{atu} atualizados")

        except Exception as e:
            print(f"[ERRO] Falha ao processar '{query}': {e}", file=sys.stderr)
            queries_com_erro.append(query)

    # 4. Relatório final
    print(f"\n{separador}")
    print(f"  [OK] Concluido!")
    print(f"  +{total_inseridos} livros novos inseridos")
    print(f"  ~{total_atualizados} livros existentes atualizados")
    if queries_com_erro:
        print(f"  [ERRO] {len(queries_com_erro)} queries com erro: {queries_com_erro}")
    print(separador)


if __name__ == "__main__":
    main()

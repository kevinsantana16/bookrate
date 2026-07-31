"""
google_books_seeder.py
──────────────────────────────────────────────────────────────
Script de integração com a Google Books API.

Como usar:
    python google_books_seeder.py

Responsabilidades:
  1. Inicialização/migração do schema delegada a database.init_db().
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

    try:
        for livro in livros:
            if not isinstance(livro, dict):
                raise ValueError("Cada item importado deve ser um objeto.")

            gid = livro.get("google_books_id")
            titulo = livro.get("titulo")
            autor = livro.get("autor")
            if not isinstance(gid, str) or not gid.strip():
                continue
            if not isinstance(titulo, str) or not titulo.strip():
                raise ValueError("Livro importado sem título.")
            if not isinstance(autor, str) or not autor.strip():
                raise ValueError("Livro importado sem autor.")

            existe = conn.execute(
                "SELECT id FROM livros WHERE google_books_id = ?", (gid,)
            ).fetchone()

            conn.execute(
                """
                INSERT INTO livros (
                    titulo, autor, google_books_id,
                    editora, data_publicacao, descricao,
                    isbn_13, isbn_10, total_paginas,
                    categorias, idioma, capa_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT DO UPDATE SET
                    titulo = excluded.titulo,
                    autor = excluded.autor,
                    editora = excluded.editora,
                    data_publicacao = excluded.data_publicacao,
                    descricao = excluded.descricao,
                    isbn_13 = excluded.isbn_13,
                    isbn_10 = excluded.isbn_10,
                    total_paginas = excluded.total_paginas,
                    categorias = excluded.categorias,
                    idioma = excluded.idioma,
                    capa_url = excluded.capa_url
                """,
                (
                    titulo,
                    autor,
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
            if existe:
                atualizados += 1
            else:
                inseridos += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
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

    # init_db() é a fonte única de verdade do schema e das migrações.
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

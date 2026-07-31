"""
google_books_client.py
──────────────────────────────────────────────────────────────
Cliente isolado para a Google Books API.

Responsabilidades:
  - Fazer requisições HTTP com Exponential Backoff (429 / 5xx)
  - Iterar páginas automaticamente (startIndex / maxResults)
  - Mapear volumeInfo → dict compatível com o schema da BD

Sem dependências externas além da stdlib Python,
alinhado com o estilo zero-ORM do projeto.
──────────────────────────────────────────────────────────────
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

# ──────────────────────────────────────────────
# CONSTANTES
# ──────────────────────────────────────────────

BASE_URL    = "https://www.googleapis.com/books/v1/volumes"
MAX_RESULTS = 40      # máximo permitido pela API por chamada
MAX_RETRIES = 4       # tentativas antes de desistir (429 / 5xx)
DELAY_ENTRE_PAGINAS = 0.5   # segundos entre chamadas (respeita Rate Limit)
LIMITE_SEGURANCA    = 200   # máximo de livros por query (evita loops infinitos)


# ──────────────────────────────────────────────
# CAMADA HTTP — com Exponential Backoff
# ──────────────────────────────────────────────

# Headers enviados em todas as requisições
_HEADERS = {
    "User-Agent": "BookSeeder/1.0 (compatible; Python-urllib)",
    "Accept":     "application/json",
}


def _get(url: str) -> dict:
    """
    Faz GET na URL com Exponential Backoff para erros 429 / 5xx.
    Retorna o JSON parseado ou lança RuntimeError após MAX_RETRIES.
    Inclui User-Agent para melhor compatibilidade com a Google API.
    """
    delay = 2
    for tentativa in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))

        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                print(
                    f"[API] Erro HTTP {e.code}. "
                    f"Aguardando {delay}s (tentativa {tentativa}/{MAX_RETRIES})..."
                )
                if tentativa < MAX_RETRIES:
                    time.sleep(delay)
                delay *= 2  # dobra o tempo a cada tentativa
            else:
                raise  # outros erros HTTP são relançados imediatamente

        except urllib.error.URLError as e:
            print(f"[API] Erro de rede: {e.reason}. Aguardando {delay}s...")
            if tentativa < MAX_RETRIES:
                time.sleep(delay)
            delay *= 2

    raise RuntimeError(f"[API] Falha após {MAX_RETRIES} tentativas. URL: {url}")


# ──────────────────────────────────────────────
# PAGINAÇÃO — itera todos os resultados
# ──────────────────────────────────────────────

def buscar_livros(query: str, api_key: str = None, lang: str = None) -> list:
    """
    Busca todos os volumes que correspondem à query, com paginação automática.

    Args:
        query:   Termo de busca (ex: "ficção científica brasileira").
        api_key: Chave de API opcional (aumenta o limite diário de 1000 para 10000 req/dia).
        lang:    Restrição de idioma ISO 639-1 (ex: "pt", "en"). None = sem restrição.

    Returns:
        Lista de dicts mapeados para o schema da BD, prontos para persistência.
    """
    livros: list = []
    start_index = 0

    params: dict = {
        "q":          query,
        "maxResults": MAX_RESULTS,
        "printType":  "books",
    }
    if lang:
        params["langRestrict"] = lang
    if api_key:
        params["key"] = api_key

    while True:
        params["startIndex"] = start_index
        url = BASE_URL + "?" + urllib.parse.urlencode(params)

        print(f"[API] Requisição: startIndex={start_index} | query='{query}'")
        data = _get(url)

        items = data.get("items", [])
        if not items:
            print("[API] Sem mais resultados. Paginação concluída.")
            break

        for item in items:
            livro_mapeado = _mapear_volume(item)
            if livro_mapeado:
                livros.append(livro_mapeado)

        start_index += len(items)
        total_items = data.get("totalItems")
        if isinstance(total_items, int) and total_items > 0:
            # Para quando atingir o total real ou o limite de segurança.
            if start_index >= min(total_items, LIMITE_SEGURANCA):
                print(f"[API] Limite atingido ({start_index}/{total_items} items). Parando.")
                break
        elif len(items) < MAX_RESULTS or start_index >= LIMITE_SEGURANCA:
            # Resposta sem totalItems: uma página incompleta indica o fim.
            break

        time.sleep(DELAY_ENTRE_PAGINAS)  # pausa entre páginas → respeita Rate Limit

    return livros


# ──────────────────────────────────────────────
# PARSER — volumeInfo → dict da BD
# ──────────────────────────────────────────────

def _mapear_volume(item: dict):
    """
    Mapeia um item completo da API (items[]) para o schema da BD.

    Mapeamento:
        item.id                         → google_books_id
        volumeInfo.title                → titulo
        volumeInfo.authors (lista)      → autor  (concatenado com ", ")
        volumeInfo.publisher            → editora
        volumeInfo.publishedDate        → data_publicacao
        volumeInfo.description          → descricao
        volumeInfo.industryIdentifiers  → isbn_13, isbn_10
        volumeInfo.pageCount            → total_paginas
        volumeInfo.categories (lista)   → categorias (JSON serializado)
        volumeInfo.language             → idioma
        volumeInfo.imageLinks.thumbnail → capa_url

    Retorna None se o título estiver ausente (item inválido).
    """
    if not isinstance(item, dict):
        return None

    google_books_id = item.get("id")
    info: dict = item.get("volumeInfo") or {}
    if not isinstance(info, dict):
        return None

    titulo = info.get("title")
    if not titulo:
        return None  # descarta itens sem título mínimo

    # Autores: lista → string concatenada (retrocompatível com campo 'autor' TEXT)
    autores = info.get("authors") or ["Autor Desconhecido"]
    if not isinstance(autores, list) or not all(isinstance(autor, str) for autor in autores):
        autores = ["Autor Desconhecido"]
    autor = ", ".join(autores)

    # ISBNs: percorre a lista de identificadores
    isbn_13 = isbn_10 = None
    identificadores = info.get("industryIdentifiers") or []
    if not isinstance(identificadores, list):
        identificadores = []
    for identificador in identificadores:
        if not isinstance(identificador, dict):
            continue
        tipo = identificador.get("type", "")
        valor = identificador.get("identifier")
        if tipo == "ISBN_13":
            isbn_13 = valor
        elif tipo == "ISBN_10":
            isbn_10 = valor

    # Categorias: lista → JSON (SQLite não tem tipo array nativo)
    categorias_lista = info.get("categories") or []
    categorias = json.dumps(categorias_lista, ensure_ascii=False)

    # URL da capa: prefere https (segurança)
    image_links = info.get("imageLinks") or {}
    capa_url = image_links.get("thumbnail") if isinstance(image_links, dict) else ""
    if isinstance(capa_url, str) and capa_url:
        capa_url = capa_url.replace("http://", "https://", 1)
        parsed_url = urllib.parse.urlparse(capa_url)
        if parsed_url.scheme != "https" or not parsed_url.netloc:
            capa_url = ""
    else:
        capa_url = ""

    return {
        "google_books_id": google_books_id,
        "titulo":           titulo,
        "autor":            autor,
        "editora":          info.get("publisher"),
        "data_publicacao":  info.get("publishedDate"),
        "descricao":        info.get("description"),
        "isbn_13":          isbn_13,
        "isbn_10":          isbn_10,
        "total_paginas":    info.get("pageCount"),
        "categorias":       categorias,
        "idioma":           info.get("language"),
        "capa_url":         capa_url or None,
    }

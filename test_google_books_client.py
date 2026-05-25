"""
test_google_books_client.py — Testes para google_books_client.py
Usa mocks para simular chamadas HTTP — sem rede real nos testes.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
import urllib.error

import google_books_client as gbc


# ══════════════════════════════════════════════════════════════
# HELPERS — construtores de fixtures de API
# ══════════════════════════════════════════════════════════════

def _make_volume(title="Test Book", authors=None, google_id="gid_001",
                 isbn13=None, isbn10=None, categories=None,
                 page_count=None, publisher=None, language="pt",
                 published_date="2023", description=None, thumbnail=None):
    """Constrói um item de volume simulado da Google Books API."""
    volume_info = {"title": title}
    if authors:
        volume_info["authors"] = authors
    if categories:
        volume_info["categories"] = categories
    if page_count:
        volume_info["pageCount"] = page_count
    if publisher:
        volume_info["publisher"] = publisher
    if language:
        volume_info["language"] = language
    if published_date:
        volume_info["publishedDate"] = published_date
    if description:
        volume_info["description"] = description
    if thumbnail:
        volume_info["imageLinks"] = {"thumbnail": thumbnail}

    identifiers = []
    if isbn13:
        identifiers.append({"type": "ISBN_13", "identifier": isbn13})
    if isbn10:
        identifiers.append({"type": "ISBN_10", "identifier": isbn10})
    if identifiers:
        volume_info["industryIdentifiers"] = identifiers

    return {"id": google_id, "volumeInfo": volume_info}


def _make_api_response(items, total_items=None):
    """Constrói uma resposta simulada da API."""
    return {
        "items": items,
        "totalItems": total_items if total_items is not None else len(items),
    }


# ══════════════════════════════════════════════════════════════
# _mapear_volume()
# ══════════════════════════════════════════════════════════════

class TestMapearVolume:
    """Testes da função interna _mapear_volume."""

    def test_mapeamento_completo(self):
        item = _make_volume(
            title="Livro Completo",
            authors=["Autor A", "Autor B"],
            google_id="id_full",
            isbn13="9781234567890",
            isbn10="1234567890",
            categories=["Fiction", "Drama"],
            page_count=320,
            publisher="Editora X",
            language="pt",
            published_date="2022-01",
            description="Descrição do livro",
            thumbnail="http://example.com/capa.jpg",
        )
        resultado = gbc._mapear_volume(item)

        assert resultado is not None
        assert resultado["google_books_id"] == "id_full"
        assert resultado["titulo"] == "Livro Completo"
        assert resultado["autor"] == "Autor A, Autor B"
        assert resultado["isbn_13"] == "9781234567890"
        assert resultado["isbn_10"] == "1234567890"
        assert resultado["total_paginas"] == 320
        assert resultado["editora"] == "Editora X"
        assert resultado["idioma"] == "pt"
        assert resultado["data_publicacao"] == "2022-01"
        assert resultado["descricao"] == "Descrição do livro"

    def test_retorna_none_sem_titulo(self):
        """Item sem título deve retornar None."""
        item = {"id": "sem_titulo", "volumeInfo": {}}
        assert gbc._mapear_volume(item) is None

    def test_autor_desconhecido_sem_authors(self):
        item = _make_volume(title="Sem Autor", authors=None)
        resultado = gbc._mapear_volume(item)
        assert resultado["autor"] == "Autor Desconhecido"

    def test_multiplos_autores_concatenados(self):
        item = _make_volume(title="T", authors=["A1", "A2", "A3"])
        resultado = gbc._mapear_volume(item)
        assert resultado["autor"] == "A1, A2, A3"

    def test_capa_url_http_vira_https(self):
        """URL de capa com http:// deve ser convertida para https://."""
        item = _make_volume(title="T", thumbnail="http://books.google.com/capa.jpg")
        resultado = gbc._mapear_volume(item)
        assert resultado["capa_url"].startswith("https://")

    def test_capa_url_https_mantida(self):
        item = _make_volume(title="T", thumbnail="https://books.google.com/capa.jpg")
        resultado = gbc._mapear_volume(item)
        assert resultado["capa_url"].startswith("https://")

    def test_sem_capa_retorna_none(self):
        item = _make_volume(title="T", thumbnail=None)
        resultado = gbc._mapear_volume(item)
        assert resultado["capa_url"] is None

    def test_categorias_serializadas_como_json(self):
        item = _make_volume(title="T", categories=["Ficção", "Clássico"])
        resultado = gbc._mapear_volume(item)
        cats = json.loads(resultado["categorias"])
        assert "Ficção" in cats
        assert "Clássico" in cats

    def test_sem_categorias_retorna_json_lista_vazia(self):
        item = _make_volume(title="T", categories=None)
        resultado = gbc._mapear_volume(item)
        cats = json.loads(resultado["categorias"])
        assert cats == []

    def test_isbn_13_e_isbn_10_extraidos(self):
        item = _make_volume(title="T", isbn13="9780000000001", isbn10="0000000001")
        resultado = gbc._mapear_volume(item)
        assert resultado["isbn_13"] == "9780000000001"
        assert resultado["isbn_10"] == "0000000001"

    def test_sem_isbn_retorna_none(self):
        item = _make_volume(title="T")
        resultado = gbc._mapear_volume(item)
        assert resultado["isbn_13"] is None
        assert resultado["isbn_10"] is None

    def test_sem_volume_info(self):
        """Item sem volumeInfo deve retornar None (sem título)."""
        item = {"id": "x"}
        assert gbc._mapear_volume(item) is None


# ══════════════════════════════════════════════════════════════
# _get() — camada HTTP com backoff
# ══════════════════════════════════════════════════════════════

class TestGet:
    """Testes da função _get (HTTP com backoff)."""

    def test_sucesso_na_primeira_tentativa(self):
        payload = {"items": [], "totalItems": 0}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            resultado = gbc._get("https://example.com")
        assert resultado == payload

    def test_retenta_em_429(self):
        """Deve retentar em erro 429 e eventualmente levantar RuntimeError após MAX_RETRIES."""
        http_error = urllib.error.HTTPError(
            url="", code=429, msg="Too Many Requests", hdrs={}, fp=None
        )

        with patch("urllib.request.urlopen", side_effect=http_error):
            with patch("time.sleep"):  # evita espera real nos testes
                with pytest.raises(RuntimeError, match="Falha após"):
                    gbc._get("https://example.com")

    def test_levanta_http_error_nao_retentavel(self):
        """Erros HTTP que não são 429/500/503 devem ser relançados imediatamente."""
        http_error = urllib.error.HTTPError(
            url="", code=404, msg="Not Found", hdrs={}, fp=None
        )
        with patch("urllib.request.urlopen", side_effect=http_error):
            with pytest.raises(urllib.error.HTTPError):
                gbc._get("https://example.com")

    def test_retenta_em_erro_de_rede(self):
        """URLError (problema de rede) deve retentar."""
        url_error = urllib.error.URLError("Network unreachable")

        with patch("urllib.request.urlopen", side_effect=url_error):
            with patch("time.sleep"):
                with pytest.raises(RuntimeError):
                    gbc._get("https://example.com")


# ══════════════════════════════════════════════════════════════
# buscar_livros() — paginação e integração
# ══════════════════════════════════════════════════════════════

class TestBuscarLivros:
    """Testes de buscar_livros() com mock da camada _get."""

    def test_retorna_lista_vazia_sem_items(self):
        with patch.object(gbc, "_get", return_value={"items": [], "totalItems": 0}):
            resultado = gbc.buscar_livros("query sem resultado")
        assert resultado == []

    def test_mapeia_items_corretamente(self):
        item = _make_volume(title="Livro Paginado", authors=["Autor"])
        resposta = _make_api_response([item], total_items=1)

        with patch.object(gbc, "_get", return_value=resposta):
            resultado = gbc.buscar_livros("ficção")

        assert len(resultado) == 1
        assert resultado[0]["titulo"] == "Livro Paginado"

    def test_ignora_items_sem_titulo(self):
        """Items sem título (retornam None de _mapear_volume) devem ser descartados."""
        item_invalido = {"id": "x", "volumeInfo": {}}
        item_valido = _make_volume(title="Válido")
        resposta = _make_api_response([item_invalido, item_valido], total_items=2)

        with patch.object(gbc, "_get", return_value=resposta):
            resultado = gbc.buscar_livros("query")

        assert len(resultado) == 1
        assert resultado[0]["titulo"] == "Válido"

    def test_para_quando_sem_mais_items(self):
        """Deve parar de paginar quando a API retorna lista vazia."""
        respostas = [
            _make_api_response([_make_volume(title="L1")], total_items=1),
            {"totalItems": 1},  # sem 'items' → para
        ]
        with patch.object(gbc, "_get", side_effect=respostas):
            with patch("time.sleep"):
                resultado = gbc.buscar_livros("query")
        assert len(resultado) == 1

    def test_limite_seguranca_evita_loop_infinito(self):
        """LIMITE_SEGURANCA deve impedir paginação infinita."""
        # MAX_RESULTS=40, LIMITE_SEGURANCA=200 → máximo 5 páginas
        items = [_make_volume(title=f"L{i}", google_id=f"id{i}") for i in range(40)]

        # A função para quando start_index >= min(total_items, LIMITE_SEGURANCA)
        # Simulamos total_items muito alto — o LIMITE_SEGURANCA deve agir
        def _mock_get(url):
            return _make_api_response(items, total_items=999999)

        with patch.object(gbc, "_get", side_effect=_mock_get):
            with patch("time.sleep"):
                resultado = gbc.buscar_livros("query")

        # Não deve ultrapassar LIMITE_SEGURANCA resultados
        assert len(resultado) <= gbc.LIMITE_SEGURANCA

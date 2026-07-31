"""
app.py — BookRate
Application Factory com proteção CSRF, validação robusta e novas features.
"""

import os
import secrets
import sqlite3
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify, abort, g
)
from flask_wtf.csrf import CSRFProtect
from functools import wraps
from database import get_db, init_db
from auth import hash_senha, verificar_senha
import models

LIVROS_POR_PAGINA = 12
MAX_USERNAME_LENGTH = 80
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_BYTES = 72  # Limite efetivo do bcrypt
MAX_BOOK_FIELD_LENGTH = 300
MAX_IMPORT_BOOKS = 50

# ──────────────────────────────────────────────
# CARREGAMENTO SEGURO DE .env
# ──────────────────────────────────────────────

def _carregar_env() -> None:
    """Carrega variáveis de ambiente do .env (sem dependências externas)."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    with env_path.open(encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, _, valor = linha.partition("=")
            chave = chave.strip()
            valor = valor.strip()
            if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ('"', "'"):
                valor = valor[1:-1]
            os.environ.setdefault(chave, valor)

_carregar_env()


# ──────────────────────────────────────────────
# APPLICATION FACTORY
# ──────────────────────────────────────────────

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)

    # Chave secreta carregada de variável de ambiente (nunca hardcoded)
    ambiente = os.environ.get("APP_ENV", os.environ.get("FLASK_ENV", "development")).lower()
    secret_key = os.environ.get("FLASK_SECRET_KEY")
    if ambiente in {"production", "prod"} and not secret_key:
        raise RuntimeError("FLASK_SECRET_KEY deve ser definida em produção.")

    # Em desenvolvimento, uma chave aleatória evita um segredo conhecido.
    # As sessões serão invalidadas ao reiniciar o processo, comportamento aceitável
    # para o ambiente local.
    app.secret_key = secret_key or secrets.token_hex(32)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=ambiente in {"production", "prod"},
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    )

    # Proteção CSRF
    csrf.init_app(app)

    # Teardown: fecha conexão do banco ao final de cada request
    @app.teardown_appcontext
    def close_db_conn(e=None):
        db = g.pop("db", None)
        if db is not None:
            real_close = getattr(db, "real_close", None)
            if real_close is not None:
                real_close()
            else:
                db.close()

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if ambiente in {"production", "prod"}:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response

    # ──────────────────────────────────────────────
    # DECORATORS
    # ──────────────────────────────────────────────

    def _carregar_usuario_atual():
        usuario_id = session.get("usuario_id")
        if usuario_id is None:
            return None

        usuario = models.buscar_usuario_por_id(usuario_id)
        if usuario is None:
            session.clear()
            return None

        g.current_user = dict(usuario)
        return g.current_user

    @app.context_processor
    def inject_current_user():
        return {"current_user": getattr(g, "current_user", None)}

    def login_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if _carregar_usuario_atual() is None:
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return decorated

    def admin_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            usuario = _carregar_usuario_atual()
            if usuario is None:
                return redirect(url_for("login"))
            if not usuario["is_admin"]:
                abort(403)
            return f(*args, **kwargs)
        return decorated

    # ──────────────────────────────────────────────
    # HELPER — validação segura de paginação
    # ──────────────────────────────────────────────

    def _parse_pagina():
        """Converte o parâmetro 'page' com fallback seguro para 1."""
        try:
            return max(1, int(request.args.get("page", 1)))
        except (ValueError, TypeError):
            return 1

    def _parse_positive_int(value):
        """Aceita apenas inteiros positivos vindos de JSON."""
        if type(value) is not int or value <= 0:
            return None
        return value

    def _json_object():
        """Retorna um payload JSON objeto ou None para entrada inválida."""
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else None

    def _texto_formulario(nome):
        valor = request.form.get(nome, "").strip()
        return valor if len(valor) <= MAX_BOOK_FIELD_LENGTH else None

    # ──────────────────────────────────────────────
    # AUTH
    # ──────────────────────────────────────────────


    @app.route("/login", methods=["GET", "POST"])
    def login():
        if _carregar_usuario_atual() is not None:
            return redirect(url_for("home"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            senha = request.form.get("senha", "")

            usuario = models.buscar_usuario_por_username(username)
            if not usuario or not verificar_senha(senha, usuario["password_hash"]):
                flash("Usuário ou senha inválidos.", "error")
                return redirect(url_for("login"))

            # Evita reutilizar dados de uma sessao anterior apos autenticacao.
            session.clear()
            session["usuario_id"] = usuario["id"]
            return redirect(url_for("home"))

        return render_template("login.html")

    @app.route("/")
    @login_required
    def index():
        return redirect(url_for("home"))

    @app.route("/cadastro", methods=["GET", "POST"])
    def cadastro():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            senha = request.form.get("senha", "")
            confirmar = request.form.get("confirmar", "")

            if not username or not senha:
                flash("Preencha todos os campos.", "error")
                return redirect(url_for("login") + "#cadastro")

            if len(username) > MAX_USERNAME_LENGTH:
                flash(f"O usuario deve ter no maximo {MAX_USERNAME_LENGTH} caracteres.", "error")
                return redirect(url_for("login") + "#cadastro")

            if senha != confirmar:
                flash("As senhas não coincidem.", "error")
                return redirect(url_for("login") + "#cadastro")

            senha_bytes = len(senha.encode("utf-8"))
            if len(senha) < MIN_PASSWORD_LENGTH:
                flash(f"A senha deve ter ao menos {MIN_PASSWORD_LENGTH} caracteres.", "error")
                return redirect(url_for("login") + "#cadastro")

            if senha_bytes > MAX_PASSWORD_BYTES:
                flash("A senha excede o limite suportado pelo algoritmo de hash.", "error")
                return redirect(url_for("login") + "#cadastro")

            if username.lower() == "admin":
                flash("Este nome de usuário é reservado.", "error")
                return redirect(url_for("login") + "#cadastro")

            criado = models.criar_usuario(username, hash_senha(senha))
            if not criado:
                flash("Usuário já existe. Escolha outro nome.", "error")
                return redirect(url_for("login") + "#cadastro")

            flash("Conta criada com sucesso! Faça login.", "success")
            return redirect(url_for("login"))

        return redirect(url_for("login"))

    @app.route("/logout", methods=["POST"])
    def logout():
        session.clear()
        return redirect(url_for("login"))

    # ──────────────────────────────────────────────
    # HOME
    # ──────────────────────────────────────────────

    @app.route("/home")
    @login_required
    def home():
        pagina = _parse_pagina()
        filtro = request.args.get("q", "").strip()
        offset = (pagina - 1) * LIVROS_POR_PAGINA

        usuario_id = g.current_user["id"]
        livros = models.listar_livros(
            usuario_id=usuario_id,
            offset=offset,
            limit=LIVROS_POR_PAGINA,
            filtro=filtro,
        )
        total = models.contar_livros(filtro=filtro)
        total_paginas = max(1, -(-total // LIVROS_POR_PAGINA))

        # Enriquecer com status de leitura (batch, sem N+1)
        livro_ids = [l["id"] for l in livros]
        statuses = models.obter_statuses_leitura_bulk(usuario_id, livro_ids)
        for livro in livros:
            livro["status_leitura"] = statuses.get(livro["id"])

        return render_template(
            "home.html",
            livros=livros,
            pagina=pagina,
            total_paginas=total_paginas,
            total_livros=total,
            filtro=filtro,
        )

    # ──────────────────────────────────────────────
    # DETALHES DO LIVRO
    # ──────────────────────────────────────────────

    @app.route("/livro/<int:livro_id>")
    @login_required
    def livro_detalhe(livro_id):
        usuario_id = g.current_user["id"]
        livro = models.buscar_livro_detalhes(livro_id, usuario_id)
        if not livro:
            abort(404)

        comentarios = models.listar_comentarios(livro_id)
        status_leitura = models.obter_status_leitura(usuario_id, livro_id)

        return render_template(
            "livro.html",
            livro=livro,
            comentarios=comentarios,
            status_leitura=status_leitura,
        )

    # ──────────────────────────────────────────────
    # API — busca, votos, comentários, lista (AJAX)
    # ──────────────────────────────────────────────

    @app.route("/api/livros")
    @login_required
    def api_livros():
        pagina = _parse_pagina()
        filtro = request.args.get("q", "").strip()
        offset = (pagina - 1) * LIVROS_POR_PAGINA

        usuario_id = g.current_user["id"]
        livros = models.listar_livros(
            usuario_id=usuario_id,
            offset=offset,
            limit=LIVROS_POR_PAGINA,
            filtro=filtro,
        )
        total = models.contar_livros(filtro=filtro)
        total_paginas = max(1, -(-total // LIVROS_POR_PAGINA))

        # Status de leitura em batch
        livro_ids = [l["id"] for l in livros]
        statuses = models.obter_statuses_leitura_bulk(usuario_id, livro_ids)
        for livro in livros:
            livro["status_leitura"] = statuses.get(livro["id"])

        return jsonify({
            "livros": livros,
            "pagina": pagina,
            "total_paginas": total_paginas,
            "total_livros": total,
        })

    @app.route("/api/votar", methods=["POST"])
    @login_required
    def api_votar():
        data = _json_object()
        if data is None:
            return jsonify({"error": "JSON inválido"}), 400
        livro_id = data.get("livro_id")
        voto = data.get("voto")  # 1 = recomendo, 0 = não recomendo

        livro_id = _parse_positive_int(livro_id)
        if livro_id is None or type(voto) is not int or voto not in (0, 1):
            return jsonify({"error": "Dados inválidos"}), 400

        if models.buscar_livro_por_id(livro_id) is None:
            return jsonify({"error": "Livro não encontrado."}), 404

        usuario_id = g.current_user["id"]

        try:
            contagens = models.registrar_ou_atualizar_voto(usuario_id, livro_id, voto)
        except sqlite3.IntegrityError:
            return jsonify({"error": "Livro não encontrado."}), 404

        meu_voto = models.obter_voto_usuario(usuario_id, livro_id)

        return jsonify({
            "recomendo": contagens["recomendo"],
            "nao_recomendo": contagens["nao_recomendo"],
            "meu_voto": meu_voto,
        })

    @app.route("/api/comentar", methods=["POST"])
    @login_required
    def api_comentar():
        data = _json_object()
        if data is None:
            return jsonify({"error": "JSON inválido"}), 400
        livro_id = data.get("livro_id")
        texto_bruto = data.get("texto")
        texto = texto_bruto.strip() if isinstance(texto_bruto, str) else ""

        livro_id = _parse_positive_int(livro_id)
        if livro_id is None or not texto:
            return jsonify({"error": "Dados inválidos"}), 400

        if len(texto) > 2000:
            return jsonify({"error": "Comentário muito longo (máx. 2000 caracteres)"}), 400

        if models.buscar_livro_por_id(livro_id) is None:
            return jsonify({"error": "Livro não encontrado."}), 404

        usuario_id = g.current_user["id"]

        try:
            comment_id = models.criar_comentario(usuario_id, livro_id, texto)
        except sqlite3.IntegrityError:
            return jsonify({"error": "Livro não encontrado."}), 404

        return jsonify({
            "id": comment_id,
            "texto": texto,
            "username": g.current_user["username"],
            "usuario_id": usuario_id,
            "is_admin": bool(g.current_user["is_admin"]),
            "criado_em": "agora",
        })

    @app.route("/api/comentario/<int:comentario_id>/excluir", methods=["POST"])
    @login_required
    def api_excluir_comentario(comentario_id):
        usuario_id = g.current_user["id"]
        is_admin = bool(g.current_user["is_admin"])

        excluido = models.excluir_comentario(comentario_id, usuario_id, is_admin)
        if not excluido:
            return jsonify({"error": "Comentário não encontrado ou sem permissão."}), 404

        return jsonify({"ok": True})

    @app.route("/api/lista-leitura", methods=["POST"])
    @login_required
    def api_lista_leitura():
        data = _json_object()
        if data is None:
            return jsonify({"error": "JSON inválido"}), 400
        livro_id = data.get("livro_id")
        status = data.get("status")  # 'quero_ler', 'lendo', 'lido', ou None/''

        livro_id = _parse_positive_int(livro_id)
        if livro_id is None:
            return jsonify({"error": "Dados inválidos"}), 400

        if status not in (None, "", "quero_ler", "lendo", "lido"):
            return jsonify({"error": "Status inválido"}), 400

        if models.buscar_livro_por_id(livro_id) is None:
            return jsonify({"error": "Livro não encontrado."}), 404

        usuario_id = g.current_user["id"]
        models.definir_status_leitura(usuario_id, livro_id, status)

        return jsonify({"ok": True, "status": status})

    # ──────────────────────────────────────────────
    # ADMIN
    # ──────────────────────────────────────────────

    @app.route("/admin")
    @admin_required
    def admin():
        livros = models.listar_todos_livros()
        return render_template("admin.html", livros=livros)

    @app.route("/admin/livro/novo", methods=["POST"])
    @admin_required
    def admin_novo_livro():
        titulo = _texto_formulario("titulo")
        autor = _texto_formulario("autor")
        if not titulo or not autor:
            flash("Título e Autor são obrigatórios.", "error")
            return redirect(url_for("admin"))
        models.inserir_livro(titulo, autor)
        flash(f'Livro "{titulo}" adicionado com sucesso!', "success")
        return redirect(url_for("admin"))

    @app.route("/admin/livro/editar/<int:livro_id>", methods=["POST"])
    @admin_required
    def admin_editar_livro(livro_id):
        titulo = _texto_formulario("titulo")
        autor = _texto_formulario("autor")
        if not titulo or not autor:
            flash("Título e Autor são obrigatórios.", "error")
            return redirect(url_for("admin"))
        editado = models.editar_livro(livro_id, titulo, autor)
        if editado:
            flash(f'Livro "{titulo}" atualizado com sucesso!', "success")
        else:
            flash("Livro não encontrado.", "error")
        return redirect(url_for("admin"))

    @app.route("/admin/livro/excluir/<int:livro_id>", methods=["POST"])
    @admin_required
    def admin_excluir_livro(livro_id):
        livro = models.buscar_livro_por_id(livro_id)
        excluido = models.excluir_livro(livro_id)
        if excluido:
            flash(f'Livro "{livro["titulo"]}" excluído.', "success")
        else:
            flash("Livro não encontrado.", "error")
        return redirect(url_for("admin"))

    # ── ADMIN: IMPORTAR GOOGLE BOOKS ──

    @app.route("/admin/importar")
    @admin_required
    def admin_importar():
        return render_template("admin_importar.html")

    @app.route("/admin/importar/buscar")
    @admin_required
    def admin_importar_buscar():
        from google_books_client import buscar_livros as gb_buscar

        query = request.args.get("q", "").strip()
        if not query:
            return jsonify({"livros": []})
        if len(query) > 200:
            return jsonify({"error": "A busca deve ter no máximo 200 caracteres."}), 400

        api_key = os.environ.get("GOOGLE_BOOKS_API_KEY") or None
        lang = os.environ.get("GOOGLE_BOOKS_LANG") or None

        try:
            livros = gb_buscar(query, api_key=api_key, lang=lang)
        except Exception:
            app.logger.exception("Falha ao buscar livros na Google Books API")
            return jsonify({"error": "Não foi possível consultar a Google Books API."}), 502

        return jsonify({"livros": livros[:50]})

    @app.route("/admin/importar/salvar", methods=["POST"])
    @admin_required
    def admin_importar_salvar():
        from google_books_seeder import persistir_livros

        data = _json_object()
        if data is None:
            return jsonify({"error": "JSON inválido"}), 400

        livros = data.get("livros")

        if not isinstance(livros, list) or not livros:
            return jsonify({"error": "Nenhum livro selecionado"}), 400
        if len(livros) > MAX_IMPORT_BOOKS:
            return jsonify({"error": f"Selecione no máximo {MAX_IMPORT_BOOKS} livros."}), 400
        for livro in livros:
            if not isinstance(livro, dict):
                return jsonify({"error": "Formato de livro inválido."}), 400
            if not isinstance(livro.get("google_books_id"), str) or not livro["google_books_id"]:
                return jsonify({"error": "Livro sem identificador da Google Books."}), 400
            for campo in ("titulo", "autor"):
                valor = livro.get(campo)
                if not isinstance(valor, str) or not valor.strip() or len(valor) > MAX_BOOK_FIELD_LENGTH:
                    return jsonify({"error": "Livro com título ou autor inválido."}), 400

        try:
            inseridos, atualizados = persistir_livros(livros)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except sqlite3.Error:
            app.logger.exception("Falha ao persistir livros importados")
            return jsonify({"error": "Não foi possível salvar os livros importados."}), 500
        return jsonify({
            "inseridos": inseridos,
            "atualizados": atualizados,
        })

    # ──────────────────────────────────────────────
    # ERROR HANDLERS
    # ──────────────────────────────────────────────

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    return app


# ──────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app = create_app()
    print("\n[OK] Sistema de Avaliacao de Livros iniciado!")
    print("[>>] Acesse: http://127.0.0.1:5000")
    ambiente = os.environ.get("APP_ENV", os.environ.get("FLASK_ENV", "development")).lower()
    debug = ambiente not in {"production", "prod"} and os.environ.get(
        "FLASK_DEBUG", "0"
    ).lower() in {"1", "true", "yes"}
    app.run(debug=debug)

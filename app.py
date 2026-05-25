"""
app.py — BookRate
Application Factory com proteção CSRF, validação robusta e novas features.
"""

import os
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
    app.secret_key = os.environ.get(
        "FLASK_SECRET_KEY",
        "dev-fallback-insecure-troque-em-producao"
    )

    # Proteção CSRF
    csrf.init_app(app)

    # Teardown: fecha conexão do banco ao final de cada request
    @app.teardown_appcontext
    def close_db_conn(e=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    # ──────────────────────────────────────────────
    # DECORATORS
    # ──────────────────────────────────────────────

    def login_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "usuario_id" not in session:
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return decorated

    def admin_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "usuario_id" not in session:
                return redirect(url_for("login"))
            if not session.get("is_admin"):
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

    # ──────────────────────────────────────────────
    # AUTH
    # ──────────────────────────────────────────────

    @app.route("/")
    @login_required
    def index():
        return redirect(url_for("home"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if "usuario_id" in session:
            return redirect(url_for("home"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            senha = request.form.get("senha", "")

            usuario = models.buscar_usuario_por_username(username)
            if not usuario or not verificar_senha(senha, usuario["password_hash"]):
                flash("Usuário ou senha inválidos.", "error")
                return redirect(url_for("login"))

            session["usuario_id"] = usuario["id"]
            session["username"] = usuario["username"]
            session["is_admin"] = bool(usuario["is_admin"])
            return redirect(url_for("home"))

        return render_template("login.html")

    @app.route("/cadastro", methods=["GET", "POST"])
    def cadastro():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            senha = request.form.get("senha", "")
            confirmar = request.form.get("confirmar", "")

            if not username or not senha:
                flash("Preencha todos os campos.", "error")
                return redirect(url_for("login") + "#cadastro")

            if senha != confirmar:
                flash("As senhas não coincidem.", "error")
                return redirect(url_for("login") + "#cadastro")

            if len(senha) < 4:
                flash("A senha deve ter ao menos 4 caracteres.", "error")
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

    @app.route("/logout")
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

        usuario_id = session["usuario_id"]
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
        usuario_id = session["usuario_id"]
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

        usuario_id = session["usuario_id"]
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
        data = request.get_json()
        livro_id = data.get("livro_id")
        voto = data.get("voto")  # 1 = recomendo, 0 = não recomendo

        if livro_id is None or voto not in (0, 1):
            return jsonify({"error": "Dados inválidos"}), 400

        usuario_id = session["usuario_id"]

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
        data = request.get_json()
        livro_id = data.get("livro_id")
        texto = (data.get("texto") or "").strip()

        if not livro_id or not texto:
            return jsonify({"error": "Dados inválidos"}), 400

        if len(texto) > 2000:
            return jsonify({"error": "Comentário muito longo (máx. 2000 caracteres)"}), 400

        usuario_id = session["usuario_id"]

        try:
            comment_id = models.criar_comentario(usuario_id, livro_id, texto)
        except sqlite3.IntegrityError:
            return jsonify({"error": "Livro não encontrado."}), 404

        return jsonify({
            "id": comment_id,
            "texto": texto,
            "username": session["username"],
            "usuario_id": usuario_id,
            "is_admin": session.get("is_admin", False),
            "criado_em": "agora",
        })

    @app.route("/api/comentario/<int:comentario_id>/excluir", methods=["POST"])
    @login_required
    def api_excluir_comentario(comentario_id):
        usuario_id = session["usuario_id"]
        is_admin = session.get("is_admin", False)

        excluido = models.excluir_comentario(comentario_id, usuario_id, is_admin)
        if not excluido:
            return jsonify({"error": "Comentário não encontrado ou sem permissão."}), 404

        return jsonify({"ok": True})

    @app.route("/api/lista-leitura", methods=["POST"])
    @login_required
    def api_lista_leitura():
        data = request.get_json()
        livro_id = data.get("livro_id")
        status = data.get("status")  # 'quero_ler', 'lendo', 'lido', ou None/''

        if not livro_id:
            return jsonify({"error": "Dados inválidos"}), 400

        if status and status not in ("quero_ler", "lendo", "lido"):
            return jsonify({"error": "Status inválido"}), 400

        usuario_id = session["usuario_id"]
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
        titulo = request.form.get("titulo", "").strip()
        autor = request.form.get("autor", "").strip()
        if not titulo or not autor:
            flash("Título e Autor são obrigatórios.", "error")
            return redirect(url_for("admin"))
        models.inserir_livro(titulo, autor)
        flash(f'Livro "{titulo}" adicionado com sucesso!', "success")
        return redirect(url_for("admin"))

    @app.route("/admin/livro/editar/<int:livro_id>", methods=["POST"])
    @admin_required
    def admin_editar_livro(livro_id):
        titulo = request.form.get("titulo", "").strip()
        autor = request.form.get("autor", "").strip()
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

        api_key = os.environ.get("GOOGLE_BOOKS_API_KEY") or None
        lang = os.environ.get("GOOGLE_BOOKS_LANG") or None

        try:
            livros = gb_buscar(query, api_key=api_key, lang=lang)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify({"livros": livros[:50]})

    @app.route("/admin/importar/salvar", methods=["POST"])
    @admin_required
    def admin_importar_salvar():
        from google_books_seeder import persistir_livros

        data = request.get_json()
        livros = data.get("livros", [])

        if not livros:
            return jsonify({"error": "Nenhum livro selecionado"}), 400

        inseridos, atualizados = persistir_livros(livros)
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
    print("[**] Admin: usuario=admin  senha=admin123\n")
    app.run(debug=True)

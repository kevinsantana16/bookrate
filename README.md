# BookRate 📚

> Sistema web de avaliação de livros com busca integrada à Google Books API.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.0%2B-green)
![SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## ✨ Funcionalidades

- 📖 **Catálogo de livros** com busca por título e autor
- 👍 **Sistema de votos** — Recomendo / Não recomendo (com toggle)
- 💬 **Comentários/resenhas** por livro
- 📚 **Lista de leitura** — Quero ler / Lendo / Lido
- 🔍 **Importação via Google Books API** (painel admin)
- 🔐 **Autenticação** com bcrypt + sessões seguras
- 🛡️ **Proteção CSRF** em todos os formulários
- 📄 **Paginação** na listagem de livros

---

## 🚀 Como Rodar (Windows — Forma Rápida)

1. Certifique-se de ter o **Python 3.10+** instalado  
   → [https://www.python.org/downloads/](https://www.python.org/downloads/)  
   ⚠️ Marque **"Add Python to PATH"** durante a instalação

2. Clone o repositório:
   ```bash
   git clone https://github.com/SEU_USUARIO/bookrate.git
   cd bookrate
   ```

3. Configure as variáveis de ambiente:
   ```bash
   copy .env.example .env
   ```
   Edite o `.env` e defina uma `FLASK_SECRET_KEY` segura:
   ```
   FLASK_SECRET_KEY=sua_chave_secreta_aqui
   ```
   > 💡 Gere uma chave com: `python -c "import secrets; print(secrets.token_hex(32))"`

4. Clique duas vezes em **`iniciar.bat`** ou execute no terminal:
   ```bash
   iniciar.bat
   ```

5. Acesse: **http://127.0.0.1:5000**

---

## 🚀 Como Rodar (Linux / macOS)

```bash
# 1. Clone o repositório
git clone https://github.com/SEU_USUARIO/bookrate.git
cd bookrate

# 2. Crie e ative o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure as variáveis de ambiente
cp .env.example .env
# Edite .env e defina FLASK_SECRET_KEY

# 5. Inicie o servidor
python app.py
```

Acesse: **http://127.0.0.1:5000**

---

## 🔑 Acesso Admin Padrão

| Usuário | Senha |
|---------|-------|
| `admin` | `admin123` |

> ⚠️ **IMPORTANTE**: Troque a senha do admin após o primeiro login em produção.

---

## ⚙️ Variáveis de Ambiente (`.env`)

Copie `.env.example` para `.env` e configure:

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `FLASK_SECRET_KEY` | ✅ Sim | Chave para assinar cookies de sessão |
| `GOOGLE_BOOKS_API_KEY` | ❌ Não | Chave da Google Books API (aumenta limites) |
| `GOOGLE_BOOKS_LANG` | ❌ Não | Filtro de idioma (`pt`, `en`, etc.) |

> 🔑 Obtenha a chave da Google Books API em: https://console.cloud.google.com/apis/credentials

---

## 🧪 Rodando os Testes

```bash
# Instale as dependências de desenvolvimento
pip install -r requirements-dev.txt

# Execute todos os testes
pytest test_auth.py test_models.py test_google_books_client.py test_app_routes.py -v

# Com relatório de cobertura
pytest test_auth.py test_models.py test_google_books_client.py test_app_routes.py --cov=. --cov-report=term-missing
```

> ✅ A suíte tem **142 testes** e usa banco SQLite in-memory (sem estado persistente).

---

## 📁 Estrutura do Projeto

```
bookrate/
├── app.py                    # Application Factory Flask + todas as rotas
├── auth.py                   # Hash e verificação de senha (bcrypt)
├── database.py               # Conexão SQLite + inicialização do schema
├── models.py                 # Funções de acesso ao banco (sem ORM)
├── utils.py                  # Utilitários compartilhados (carregar .env)
├── google_books_client.py    # Cliente HTTP para a Google Books API
├── google_books_seeder.py    # Script de importação em lote de livros
│
├── templates/                # Templates HTML (Jinja2)
│   ├── base.html
│   ├── home.html
│   ├── livro.html
│   ├── login.html
│   ├── admin.html
│   └── admin_importar.html
│
├── static/
│   ├── css/style.css
│   └── js/main.js
│
├── conftest.py               # Fixtures de teste (banco in-memory)
├── test_auth.py              # Testes unitários — autenticação
├── test_models.py            # Testes unitários — modelos/banco
├── test_google_books_client.py # Testes unitários — cliente da API
├── test_app_routes.py        # Testes de integração — rotas Flask
│
├── requirements.txt          # Dependências de produção
├── requirements-dev.txt      # Dependências de desenvolvimento
├── iniciar.bat               # Script de inicialização (Windows)
├── .env.example              # Template de variáveis de ambiente
└── .gitignore
```

---

## 🛠️ Stack Tecnológica

- **Backend**: Python 3.10+ · Flask 3 · SQLite (sem ORM)
- **Autenticação**: bcrypt · Flask-WTF (CSRF)
- **Frontend**: HTML5 · Vanilla CSS · Vanilla JS
- **Integração**: Google Books API v1
- **Testes**: pytest · banco in-memory

---

## 📄 Licença

MIT License — fique à vontade para usar, modificar e distribuir.

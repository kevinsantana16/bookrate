# BookRate 📚

> Sistema web de avaliação de livros com busca integrada à Google Books API.
> 
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

- <img width="1900" height="916" alt="image" src="https://github.com/user-attachments/assets/f40c6e03-c053-40f9-8f7c-912154309800" />

<img width="1904" height="917" alt="image" src="https://github.com/user-attachments/assets/2ff260e3-ca92-4e91-8d0c-321a20eada40" />



---

## 🔑 Acesso Admin Padrão

| Usuário | Senha |
|---------|-------|
| `admin` | `admin123` |

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

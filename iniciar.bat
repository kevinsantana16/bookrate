@echo off
echo ============================================
echo  BookRate - Instalacao e Inicializacao
echo ============================================
echo.

REM Verifica se Python esta instalado
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo [ERRO] Python nao encontrado no PATH!
    echo.
    echo Por favor, instale o Python 3.10+ em:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANTE: Marque a opcao "Add Python to PATH"
    echo durante a instalacao.
    pause
    exit /b 1
)

REM Cria ambiente virtual se nao existir
IF NOT EXIST ".venv" (
    echo [1/4] Criando ambiente virtual...
    python -m venv .venv
)

REM Ativa o venv e instala dependencias
echo [2/4] Ativando ambiente virtual...
call .venv\Scripts\activate.bat

echo [3/4] Instalando dependencias de requirements.txt...
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q

REM Verifica se .env existe; senao, copia do exemplo
IF NOT EXIST ".env" (
    echo [4/4] Criando .env a partir de .env.example...
    copy .env.example .env >nul
    echo.
    echo [AVISO] Arquivo .env criado!
    echo         Edite o .env e defina uma FLASK_SECRET_KEY segura antes de usar em producao.
    echo         Gere uma chave com: python -c "import secrets; print(secrets.token_hex(32))"
    echo.
) ELSE (
    echo [4/4] Arquivo .env ja existe. Mantendo configuracoes atuais.
)

echo.
echo ============================================
echo  Iniciando o servidor...
echo ============================================
echo.
echo  Acesse:  http://127.0.0.1:5000
echo  Admin:   usuario=admin  senha=admin123
echo.
echo  Pressione Ctrl+C para encerrar o servidor.
echo ============================================
echo.
python app.py
pause

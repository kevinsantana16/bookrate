"""
utils.py — BookRate
───────────────────────────────────────────────────────────
Utilitários compartilhados entre os módulos do projeto.

Centraliza funcionalidades comuns para evitar duplicação (DRY):
  - Carregamento seguro de variáveis de ambiente (.env)
"""

import os
from pathlib import Path


def carregar_env(env_path: Path | None = None) -> None:
    """
    Carrega variáveis de ambiente do arquivo .env (sem dependências externas).

    Formato suportado:
        CHAVE=valor          # atribuição simples
        # comentário         # linhas ignoradas
        CHAVE="valor"        # aspas simples ou duplas são removidas
        CHAVE=               # valor vazio

    Regras:
        - Não sobrescreve variáveis já definidas no ambiente do sistema.
        - Silenciosamente ignorada se o arquivo não existir.
        - O arquivo .env NUNCA deve ser versionado (ver .gitignore).

    Args:
        env_path: Caminho opcional para o arquivo .env.
                  Padrão: .env na mesma pasta deste módulo.
    """
    if env_path is None:
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
            # Remove aspas envolventes: KEY="value" → value
            if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ('"', "'"):
                valor = valor[1:-1]
            os.environ.setdefault(chave, valor)

import bcrypt


def hash_senha(senha: str) -> str:
    """Gera o hash bcrypt de uma senha em texto puro."""
    senha_bytes = senha.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(senha_bytes, salt)
    return hashed.decode("utf-8")


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    """Verifica se a senha bate com o hash armazenado."""
    try:
        return bcrypt.checkpw(
            senha.encode("utf-8"),
            hash_armazenado.encode("utf-8"),
        )
    except Exception:
        return False

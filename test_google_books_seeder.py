def test_persistir_livros_faz_upsert_atomico(mem_db):
    import database
    import google_books_seeder as seeder
    seeder.get_db = database.get_db

    primeiro = {
        "google_books_id": "google-1",
        "titulo": "Titulo original",
        "autor": "Autor",
    }
    atualizado = {**primeiro, "titulo": "Titulo atualizado"}

    inseridos, atualizados = seeder.persistir_livros([primeiro, atualizado])

    assert (inseridos, atualizados) == (1, 1)
    livro = mem_db.execute(
        "SELECT titulo FROM livros WHERE google_books_id = ?",
        ("google-1",),
    ).fetchone()
    assert livro["titulo"] == "Titulo atualizado"


def test_persistir_livros_rejeita_item_invalido(mem_db):
    import database
    import google_books_seeder as seeder
    seeder.get_db = database.get_db

    try:
        seeder.persistir_livros([{"google_books_id": "google-2"}])
    except ValueError as exc:
        assert "título" in str(exc)
    else:
        raise AssertionError("Era esperado ValueError para livro sem título")

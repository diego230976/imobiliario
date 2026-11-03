from pathlib import Path

import duckdb
import pandas as pd

from pipeline import db


def test_pasta_raw_e_banco_sao_resolvidos_pelo_modulo() -> None:
    raiz = Path(db.__file__).resolve().parent.parent

    assert db.PASTA_RAW == raiz / "raw"


def test_conectar_cria_banco_ao_lado_da_pasta_raw(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(db, "PASTA_RAW", tmp_path / "raw")

    con = db.conectar()
    try:
        assert (tmp_path / "imobiliario.duckdb").is_file()
        assert con.execute("SELECT 1").fetchone() == (1,)
    finally:
        con.close()


def test_gravar_substitui_tabela_preserva_tipos_e_nao_deixa_objetos_temporarios(
    tmp_path: Path,
) -> None:
    con = duckdb.connect(str(tmp_path / "teste.duckdb"))
    try:
        db.criar_schema(con, "raw")
        # A primeira tabela inclui um nulo; a segunda comprova a substituição.
        primeiro = pd.DataFrame(
            {"texto": pd.Series(["a", None], dtype="object"), "inteiro": [1, 2]}
        )
        assert db.gravar(con, primeiro, "raw", "amostra") == 2
        segundo = pd.DataFrame({"novo": [3.5]})

        assert db.gravar(con, segundo, "raw", "amostra") == 1
        assert con.execute("SELECT * FROM raw.amostra").fetchall() == [(3.5,)]
        assert con.execute(
            "SELECT column_name, data_type "
            "FROM information_schema.columns "
            "WHERE table_schema = 'raw' AND table_name = 'amostra' "
            "ORDER BY ordinal_position"
        ).fetchall() == [("novo", "DOUBLE")]
        assert con.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = 'raw' AND table_name <> 'amostra'"
        ).fetchone() == (0,)
        assert con.execute(
            "SELECT COUNT(*) FROM information_schema.views "
            "WHERE table_schema = 'raw'"
        ).fetchone() == (0,)
    finally:
        con.close()

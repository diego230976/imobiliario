from datetime import date
from pathlib import Path

import duckdb
import pytest

from pipeline import mart


@pytest.fixture
def mart_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    source_path = mart.BANCO
    database_path = tmp_path / "imobiliario.duckdb"
    source = duckdb.connect(str(source_path), read_only=True)
    target = duckdb.connect(str(database_path))
    try:
        target.execute("CREATE SCHEMA refined")
        for tabela in mart.TABELAS_OBRIGATORIAS:
            df = source.execute(f"SELECT * FROM refined.{tabela}").fetchdf()
            target.register("df_origem", df)
            target.execute(
                f"CREATE TABLE refined.{tabela} AS SELECT * FROM df_origem"
            )
            target.unregister("df_origem")
    finally:
        target.close()
        source.close()

    monkeypatch.setattr(mart, "BANCO", database_path)
    monkeypatch.setattr(
        mart, "conectar", lambda: duckdb.connect(str(database_path))
    )
    return database_path


def test_mart_schema_grain_volume_nulls_and_kpi_precision(
    mart_database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mart.main()
    assert capsys.readouterr().out == (
        "mart.indicadores_imobiliarios: 2.790 "
        "(base_ifix: 2.790 | colunas: 19 | fan_out: 0)\n"
    )

    con = duckdb.connect(str(mart_database), read_only=True)
    try:
        colunas = con.execute(
            "SELECT column_name, data_type "
            "FROM information_schema.columns "
            "WHERE table_schema = 'mart' "
            "AND table_name = 'indicadores_imobiliarios' "
            "ORDER BY ordinal_position"
        ).fetchall()
        assert colunas == list(mart.TIPOS_ESPERADOS.items())
        assert len(colunas) == 19
        assert all(tipo != "VARCHAR" for _, tipo in colunas)

        assert con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT data), "
            "COUNT(*) FILTER (WHERE data IS NULL) "
            "FROM mart.indicadores_imobiliarios"
        ).fetchone() == (2790, 2790, 0)

        nulos = con.execute(
            "SELECT "
            + ", ".join(
                f'COUNT(*) FILTER (WHERE "{coluna}" IS NULL)'
                for coluna in mart.COLUNAS_SAIDA
            )
            + " FROM mart.indicadores_imobiliarios"
        ).fetchone()
        assert nulos[:-1] == (0,) * 18
        assert nulos[-1] == 1

        endpoints = con.execute(
            "SELECT data, juro_real_ex_ante, selic_diaria_pct, ifix_var_pct "
            "FROM mart.indicadores_imobiliarios "
            "WHERE data IN (DATE '2011-01-03', DATE '2022-04-18') "
            "ORDER BY data"
        ).fetchall()
        assert endpoints == [
            (date(2011, 1, 3), 4.76, 0.040526, None),
            (date(2022, 4, 18), 0.45, 0.044095, -0.2382),
        ]
    finally:
        con.close()


def test_mart_rerun_is_idempotent(
    mart_database: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mart.main()
    first_output = capsys.readouterr().out
    con = duckdb.connect(str(mart_database), read_only=True)
    try:
        first_rows = con.execute(
            "SELECT * FROM mart.indicadores_imobiliarios ORDER BY data"
        ).fetchall()
    finally:
        con.close()

    mart.main()
    second_output = capsys.readouterr().out
    con = duckdb.connect(str(mart_database), read_only=True)
    try:
        second_rows = con.execute(
            "SELECT * FROM mart.indicadores_imobiliarios ORDER BY data"
        ).fetchall()
    finally:
        con.close()

    assert second_output == first_output
    assert second_rows == first_rows
    assert first_output == (
        "mart.indicadores_imobiliarios: 2.790 "
        "(base_ifix: 2.790 | colunas: 19 | fan_out: 0)\n"
    )


@pytest.mark.parametrize(
    ("invalid_refined", "erro"),
    [
        ("DROP SCHEMA refined CASCADE", "Schema obrigatório"),
        ("DROP TABLE refined.google_trends", "Tabelas obrigatórias ausentes"),
        (
            "ALTER TABLE refined.selic DROP COLUMN selic_meta",
            "Colunas obrigatórias ausentes",
        ),
        ("DELETE FROM refined.google_trends", "Tabelas obrigatórias vazias"),
    ],
)
def test_preflight_failure_does_not_touch_mart(
    mart_database: Path,
    capsys: pytest.CaptureFixture[str],
    invalid_refined: str,
    erro: str,
) -> None:
    con = duckdb.connect(str(mart_database))
    try:
        con.execute("CREATE SCHEMA mart")
        con.execute("CREATE TABLE mart.marker AS SELECT 42 AS value")
        con.execute(invalid_refined)
    finally:
        con.close()

    with pytest.raises(SystemExit) as exc_info:
        mart.main()

    assert exc_info.value.code == 1
    assert erro in capsys.readouterr().err
    con = duckdb.connect(str(mart_database), read_only=True)
    try:
        assert con.execute("SELECT value FROM mart.marker").fetchone() == (42,)
        assert con.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = 'mart' "
            "AND table_name = 'indicadores_imobiliarios'"
        ).fetchone() == (0,)
    finally:
        con.close()


def test_missing_database_exits_before_connecting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(mart, "BANCO", tmp_path / "missing.duckdb")

    def fail_if_connected():
        raise AssertionError("conectar() não deveria ser chamado")

    monkeypatch.setattr(mart, "conectar", fail_if_connected)

    with pytest.raises(SystemExit) as exc_info:
        mart.main()

    assert exc_info.value.code == 1
    assert "Banco de dados não encontrado" in capsys.readouterr().err

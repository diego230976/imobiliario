from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from pipeline import transformacao


def _criar_raw(con: duckdb.DuckDBPyConnection, ifix_valor: str = "100") -> None:
    con.execute("CREATE SCHEMA raw")
    dados = {
        "dolar": (
            {"data": ["2020-01-01"], "dolar_fechamento": ["1,25"]},
            ("data", "dolar_fechamento"),
        ),
        "embi_brazil": (
            {"data": ["2020-01-01"], "embi_brazil": ["100"]},
            ("data", "embi_brazil"),
        ),
        "google_trends": (
            {
                "data": ["2020-01-01"],
                "fii_gt": ["10"],
                "fundos_imob_gt": ["20.5"],
                "ifix_gt": ["30"],
            },
            ("data", "fii_gt", "fundos_imob_gt", "ifix_gt"),
        ),
        "ifix": (
            {
                "data": ["2020-01-01", "2020-01-01"],
                "ifix_fech": [ifix_valor, ifix_valor],
            },
            ("data", "ifix_fech"),
        ),
        "incc": (
            {"data": ["2020-01-01"], "incc": ["500.5"]},
            ("data", "incc"),
        ),
        "investidores_fii": (
            {"data": ["2020-01-01"], "qtd_invest": ["200"]},
            ("data", "qtd_invest"),
        ),
        "ipca": (
            {
                "data": ["2020-01"],
                "ipca_mes": ["0.2"],
                "ipca_3_meses": ["0.6"],
                "ipca_6_meses": ["1.2"],
                "ipca_ano": ["0.2"],
                "ipca_12_meses": ["2.0"],
            },
            (
                "data",
                "ipca_mes",
                "ipca_3_meses",
                "ipca_6_meses",
                "ipca_ano",
                "ipca_12_meses",
            ),
        ),
        "pib_per_capita": (
            {
                "data": ["2020-01-01"],
                "pib_per_capta_usd": ["1000.75"],
            },
            ("data", "pib_per_capta_usd"),
        ),
        "selic": (
            {"data": ["2020-01-01"], "selic_meta": ["4.5"]},
            ("data", "selic_meta"),
        ),
    }

    for tabela, (colunas, ordem) in dados.items():
        df = pd.DataFrame(colunas, dtype="string")
        con.register("origem_teste", df)
        con.execute(
            f"CREATE TABLE raw.{tabela} AS "
            f"SELECT {', '.join(f'\"{coluna}\"' for coluna in ordem)} "
            "FROM origem_teste"
        )
        con.unregister("origem_teste")


def test_transformacao_remove_duplicata_exata_e_tipifica_datas_e_numericos(
    tmp_path: Path, monkeypatch
) -> None:
    banco = tmp_path / "imobiliario.duckdb"
    con = duckdb.connect(str(banco))
    try:
        _criar_raw(con)
    finally:
        con.close()
    monkeypatch.setattr(transformacao, "BANCO", banco)
    monkeypatch.setattr(
        transformacao, "conectar", lambda: duckdb.connect(str(banco))
    )

    transformacao.main()

    con = duckdb.connect(str(banco), read_only=True)
    try:
        assert con.execute("SELECT * FROM refined.ifix").fetchall() == [
            (date(2020, 1, 1), 100.0)
        ]
        assert con.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema = 'refined' AND table_name = 'dolar' "
            "AND column_name = 'data'"
        ).fetchone() == ("DATE",)
        assert con.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema = 'refined' AND table_name = 'dolar' "
            "AND column_name = 'dolar_fechamento'"
        ).fetchone() == ("DOUBLE",)
        assert con.execute(
            "SELECT dolar_fechamento FROM refined.dolar"
        ).fetchone() == (1.25,)
        assert con.execute(
            "SELECT data FROM refined.ipca"
        ).fetchone() == (date(2020, 1, 1),)
    finally:
        con.close()


def test_valor_numerico_invalido_encerra_sem_converter_para_nulo() -> None:
    origem = pd.DataFrame(
        {"data": ["2020-01-01"], "ifix_fech": ["não-numérico"]}
    )

    with pytest.raises(SystemExit) as exc_info:
        transformacao.transformar("ifix", origem)

    assert exc_info.value.code == 1


def test_dados_distintos_na_mesma_data_sao_rejeitados() -> None:
    origem = pd.DataFrame(
        {
            # A segunda linha diverge no valor para provocar conflito de chave.
            "data": ["2020-01-01", "2020-01-01"],
            "ifix_fech": ["100", "101"],
        }
    )

    with pytest.raises(SystemExit) as exc_info:
        transformacao.transformar("ifix", origem)

    assert exc_info.value.code == 1

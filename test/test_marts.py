import math
from datetime import date
from pathlib import Path

import duckdb
import pytest

from pipeline import mart


def _criar_refined(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA refined")
    # Dois pregões inventados permitem conferir o ASOF, o LAG e o grão do IFIX.
    con.execute(
        "CREATE TABLE refined.ifix(data DATE, ifix_fech DOUBLE)"
    )
    con.execute(
        "INSERT INTO refined.ifix VALUES "
        "('2020-01-02', 1000), ('2020-01-03', 1100)"
    )
    # Uma taxa vigente desde o primeiro dia deve ser carregada ao segundo pregão.
    con.execute(
        "CREATE TABLE refined.selic(data DATE, selic_meta DOUBLE)"
    )
    con.execute("INSERT INTO refined.selic VALUES ('2020-01-01', 10)")
    # IPCA mensal vigente nos dois pregões para definir o diferencial real.
    con.execute(
        "CREATE TABLE refined.ipca("
        "data DATE, ipca_mes DOUBLE, ipca_3_meses DOUBLE, "
        "ipca_6_meses DOUBLE, ipca_ano DOUBLE, ipca_12_meses DOUBLE)"
    )
    con.execute(
        "INSERT INTO refined.ipca VALUES "
        "('2020-01-01', 0.2, 0.6, 1.2, 0.2, 2)"
    )
    # As demais séries também têm uma observação anterior a ambos os pregões.
    con.execute(
        "CREATE TABLE refined.dolar(data DATE, dolar_fechamento DOUBLE)"
    )
    con.execute("INSERT INTO refined.dolar VALUES ('2020-01-01', 4)")
    con.execute("CREATE TABLE refined.incc(data DATE, incc DOUBLE)")
    con.execute("INSERT INTO refined.incc VALUES ('2020-01-01', 500)")
    con.execute(
        "CREATE TABLE refined.investidores_fii(data DATE, qtd_invest BIGINT)"
    )
    con.execute(
        "INSERT INTO refined.investidores_fii VALUES ('2020-01-01', 200)"
    )
    con.execute(
        "CREATE TABLE refined.embi_brazil(data DATE, embi_brazil BIGINT)"
    )
    con.execute(
        "INSERT INTO refined.embi_brazil VALUES ('2020-01-01', 100)"
    )
    con.execute(
        "CREATE TABLE refined.pib_per_capita("
        "data DATE, pib_per_capita_usd DOUBLE)"
    )
    con.execute(
        "INSERT INTO refined.pib_per_capita VALUES ('2020-01-01', 1000)"
    )
    con.execute(
        "CREATE TABLE refined.google_trends("
        "data DATE, fii_gt BIGINT, fundos_imob_gt DOUBLE, ifix_gt DOUBLE)"
    )
    con.execute(
        "INSERT INTO refined.google_trends VALUES ('2020-01-01', 10, 20, 30)"
    )


def _usar_banco(tmp_path: Path, monkeypatch) -> Path:
    banco = tmp_path / "imobiliario.duckdb"
    con = duckdb.connect(str(banco))
    try:
        _criar_refined(con)
    finally:
        con.close()
    monkeypatch.setattr(mart, "BANCO", banco)
    monkeypatch.setattr(mart, "conectar", lambda: duckdb.connect(str(banco)))
    return banco


def test_mart_aplica_asof_kpis_e_preserva_um_registro_por_pregao(
    tmp_path: Path, monkeypatch
) -> None:
    banco = _usar_banco(tmp_path, monkeypatch)

    mart.main()

    con = duckdb.connect(str(banco), read_only=True)
    try:
        linhas = con.execute(
            "SELECT data, ifix_fech, selic_meta, ipca_12_meses, "
            "juro_real_ex_ante, selic_diaria_pct, ifix_var_pct "
            "FROM mart.indicadores_imobiliarios ORDER BY data"
        ).fetchall()
        selic_diaria = round(((math.pow(1.0 + 10 / 100, 1 / 252) - 1) * 100), 6)
        assert linhas == [
            (date(2020, 1, 2), 1000.0, 10.0, 2.0, 8.0, selic_diaria, None),
            (
                date(2020, 1, 3),
                1100.0,
                10.0,
                2.0,
                8.0,
                selic_diaria,
                10.0,
            ),
        ]
        assert con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT data) "
            "FROM mart.indicadores_imobiliarios"
        ).fetchone() == (2, 2)
    finally:
        con.close()


def test_pre_requisito_ausente_nao_substitui_tabela_mart(
    tmp_path: Path, monkeypatch
) -> None:
    banco = _usar_banco(tmp_path, monkeypatch)
    con = duckdb.connect(str(banco))
    try:
        con.execute("CREATE SCHEMA mart")
        con.execute("CREATE TABLE mart.marker AS SELECT 7 AS valor")
        con.execute("DROP TABLE refined.google_trends")
    finally:
        con.close()

    with pytest.raises(SystemExit) as exc_info:
        mart.main()

    assert exc_info.value.code == 1
    con = duckdb.connect(str(banco), read_only=True)
    try:
        assert con.execute("SELECT valor FROM mart.marker").fetchone() == (7,)
        assert con.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = 'mart' "
            "AND table_name = 'indicadores_imobiliarios'"
        ).fetchone() == (0,)
    finally:
        con.close()


def test_mart_recusa_tabela_refined_vazia(
    tmp_path: Path, monkeypatch
) -> None:
    banco = _usar_banco(tmp_path, monkeypatch)
    con = duckdb.connect(str(banco))
    try:
        con.execute("DELETE FROM refined.google_trends")
    finally:
        con.close()

    with pytest.raises(SystemExit) as exc_info:
        mart.main()

    assert exc_info.value.code == 1


def test_formatador_de_milhar_do_mart() -> None:
    assert mart.formatar_milhar(98765) == "98.765"

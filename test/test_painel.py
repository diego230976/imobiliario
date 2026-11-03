from pathlib import Path

import duckdb
import pandas as pd

import painel


def _dados() -> pd.DataFrame:
    # As duas linhas representam pregões consecutivos para conferir os pontos.
    return pd.DataFrame(
        {
            "data": pd.to_datetime(["2020-01-02", "2020-01-03"]),
            "ifix_fech": [1000.0, 1010.0],
            "selic_meta": [10.0, 10.0],
            "ipca_mes": [0.2, 0.2],
            "ipca_3_meses": [0.6, 0.6],
            "ipca_6_meses": [1.2, 1.2],
            "ipca_ano": [0.2, 0.2],
            "ipca_12_meses": [2.0, 2.0],
            "dolar_fechamento": [4.0, 4.1],
            "incc": [500.0, 501.0],
            "qtd_invest": [200, 201],
            "embi_brazil": [100, 101],
            "pib_per_capita_usd": [1000.0, 1000.0],
            "fii_gt": [10, 11],
            "fundos_imob_gt": [20.0, 21.0],
            "ifix_gt": [30.0, 31.0],
            "juro_real_ex_ante": [8.0, 8.0],
            "selic_diaria_pct": [0.037879, 0.037879],
            "ifix_var_pct": [None, 1.0],
        }
    )


def test_formatadores_usam_milhar_e_decimal_brasileiros() -> None:
    assert painel.reais(1234.5, 2) == "R$ 1.234,50"
    assert painel.pct(12.345, 1) == "12,3%"
    assert painel.numero(-1234.5, 1) == "-1.234,5"


def test_graficos_devolvem_figuras_com_pontos_para_cada_linha() -> None:
    dados = _dados()

    for _, _, funcao in painel.GRAFICOS:
        figura = funcao(dados)
        assert len(figura.data) > 0
        assert all(len(traco.x) == len(dados) for traco in figura.data)


def test_ler_usa_banco_temporario_e_fecha_a_conexao(
    tmp_path: Path, monkeypatch
) -> None:
    banco = tmp_path / "painel.duckdb"
    con = duckdb.connect(str(banco))
    try:
        con.register("dados_teste", _dados())
        con.execute(
            "CREATE SCHEMA mart; "
            "CREATE TABLE mart.indicadores_imobiliarios AS "
            "SELECT * FROM dados_teste"
        )
        con.unregister("dados_teste")
    finally:
        con.close()
    monkeypatch.setattr(painel, "BANCO", banco)

    resultado = painel.ler()

    assert tuple(resultado.columns) == painel.COLUNAS_OBRIGATORIAS
    assert len(resultado) == 2
    con = duckdb.connect(str(banco))
    try:
        assert con.execute("SELECT COUNT(*) FROM mart.indicadores_imobiliarios").fetchone() == (2,)
    finally:
        con.close()

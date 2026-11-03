import pandas as pd
import pytest

import painel


@pytest.mark.parametrize(
    ("valor", "casas", "esperado"),
    [
        (1003862.14, 2, "1.003.862,14"),
        (-0.2382, 4, "-0,2382"),
        (96470, 0, "96.470"),
        (None, 2, "—"),
    ],
)
def test_formatacao_numerica_independente_de_locale(
    valor: float | None, casas: int, esperado: str
) -> None:
    assert painel.numero(valor, casas) == esperado


def test_formatadores_de_moeda_e_percentual() -> None:
    assert painel.reais(1003862.14) == "R$ 1.003.862,14"
    assert painel.pct(93.2) == "93,2%"


def test_leitura_retorna_tabela_mart_sem_manter_lock_do_banco() -> None:
    dados = painel.ler()
    assert tuple(dados.columns) == painel.COLUNAS_OBRIGATORIAS

    import duckdb

    con = duckdb.connect(str(painel.BANCO))
    try:
        assert con.execute(
            "SELECT COUNT(*) FROM mart.indicadores_imobiliarios"
        ).fetchone() == (2790,)
    finally:
        con.close()


@pytest.mark.parametrize(
    ("_, __, funcao"),
    painel.GRAFICOS,
)
def test_graficos_usam_as_datas_e_devolvem_figuras_plotly(
    _: str, __: str, funcao
) -> None:
    dados = pd.DataFrame(
        {
            "data": pd.to_datetime(["2022-04-14", "2022-04-18"]),
            "ifix_fech": [2790.0, 2801.91],
            "selic_meta": [11.75, 11.75],
            "selic_diaria_pct": [0.044095, 0.044095],
            "ipca_mes": [1.06, 1.06],
            "ipca_3_meses": [3.2, 3.2],
            "ipca_6_meses": [6.4, 6.4],
            "ipca_12_meses": [11.3, 11.3],
            "incc": [1000.0, 1000.0],
            "dolar_fechamento": [5.0, 5.1],
            "embi_brazil": [200, 201],
            "qtd_invest": [1500000, 1510000],
            "fii_gt": [20, 21],
            "fundos_imob_gt": [30.0, 31.0],
            "ifix_gt": [40.0, 41.0],
            "juro_real_ex_ante": [0.45, 0.45],
        }
    )

    figura = funcao(dados)
    assert len(figura.data) > 0
    assert all(len(traco.x) == 2 for traco in figura.data)


def test_html_de_grafico_usa_plotly_cdn_e_configuracao_responsiva() -> None:
    dados = pd.DataFrame(
        {
            "data": pd.to_datetime(["2022-04-18"]),
            "ifix_fech": [2801.91],
            "ipca_mes": [1.06],
            "ipca_12_meses": [11.3],
        }
    )

    conteudo = painel.html_do_grafico(painel.grafico_01_ifix_ipca(dados))

    assert "cdn.plot.ly" in conteudo
    assert "responsive" in conteudo

from datetime import datetime

import pandas as pd

import painel
import relatorio


def _dados() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "data": pd.to_datetime(["2022-04-14", "2022-04-18"]),
            "ifix_fech": [2790.0, 2801.91],
            "selic_meta": [11.75, 11.75],
            "selic_diaria_pct": [0.044095, 0.044095],
            "ipca_mes": [1.06, 1.06],
            "ipca_3_meses": [3.2, 3.2],
            "ipca_6_meses": [6.4, 6.4],
            "ipca_ano": [4.5, 4.5],
            "ipca_12_meses": [11.3, 11.3],
            "dolar_fechamento": [5.0, 5.1],
            "incc": [1000.0, 1000.0],
            "qtd_invest": [1500000, 1510000],
            "embi_brazil": [200, 201],
            "pib_per_capita_usd": [12000.0, 12000.0],
            "fii_gt": [20, 21],
            "fundos_imob_gt": [30.0, 31.0],
            "ifix_gt": [40.0, 41.0],
            "juro_real_ex_ante": [0.45, 0.45],
            "ifix_var_pct": [-0.2, -0.2382],
        }
    )


def test_relatorio_reutiliza_cartoes_graficos_e_ids_estaveis() -> None:
    gerado_em = datetime(2026, 10, 25, 14, 3)

    html = relatorio.gerar_html(_dados(), gerado_em)

    assert "2.801,91 pts" in html
    assert "-0,2382%" in html
    assert "0,45 p.p." in html
    assert "11,75% a.a." in html
    assert "11,30%" in html
    assert html.count("cdn.plot.ly") == 1
    assert all(f'id="g{indice:02d}"' in html for indice in range(1, 10))
    assert html.count('class="plotly-graph-div"') == 9
    assert html.count("Dados de 25/10/2026 14:03") == 1


def test_execucoes_so_diferem_pelo_horario_do_rodape() -> None:
    primeiro = relatorio.gerar_html(_dados(), datetime(2026, 10, 25, 14, 3))
    segundo = relatorio.gerar_html(_dados(), datetime(2026, 10, 25, 14, 4))

    assert primeiro.replace("14:03", "HORARIO") == segundo.replace(
        "14:04", "HORARIO"
    )


def test_relatorio_usa_a_mesma_lista_de_graficos_do_painel() -> None:
    html = relatorio.gerar_html(_dados(), datetime(2026, 10, 25, 14, 3))

    for identificador, titulo, _ in painel.GRAFICOS:
        assert f"{identificador} · {titulo}" in html

"""Camada de leitura e visualização para o painel imobiliário.

1. Lê apenas ``mart.indicadores_imobiliarios`` usando
   ``SELECT * FROM mart.indicadores_imobiliarios``. A conexão DuckDB é
   read-only e é fechada antes de devolver os dados, para não bloquear
   reexecuções do pipeline.
2. Não calcula métricas: apenas ordena, filtra e formata os valores existentes
   na Mart. Qualquer métrica ausente deve ser criada na camada SQL/Mart.
3. Formatação numérica determinística, independente do locale do sistema.
4. Cada função ``grafico_*`` recebe um DataFrame e devolve uma figura Plotly.
   As séries macroeconômicas usam eixo secundário quando têm unidade distinta
   do IFIX; valores são comparados no tempo, sem correlação ou volatilidade
   calculada pelo painel.
5. ``juro_real_ex_ante`` é exibido conforme a fórmula da Mart, como proxy
   retrospectiva baseada no IPCA observado, não como expectativa de inflação.
"""

from pathlib import Path
from typing import Final

import duckdb
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BANCO: Final = Path(__file__).resolve().parent / "imobiliario.duckdb"
TABELA: Final = "mart.indicadores_imobiliarios"

COLUNAS_OBRIGATORIAS: Final = (
    "data",
    "ifix_fech",
    "selic_meta",
    "ipca_mes",
    "ipca_3_meses",
    "ipca_6_meses",
    "ipca_ano",
    "ipca_12_meses",
    "dolar_fechamento",
    "incc",
    "qtd_invest",
    "embi_brazil",
    "pib_per_capita_usd",
    "fii_gt",
    "fundos_imob_gt",
    "ifix_gt",
    "juro_real_ex_ante",
    "selic_diaria_pct",
    "ifix_var_pct",
)

CORES: Final = (
    "#176B87",
    "#64CCC5",
    "#DAA520",
    "#7A5195",
    "#EF5675",
    "#2F4B7C",
    "#FFA600",
    "#008F7A",
    "#BC5090",
)

ROTULOS: Final = {
    "ifix_fech": "IFIX",
    "selic_meta": "Selic meta (% a.a.)",
    "selic_diaria_pct": "Selic diária equivalente (%)",
    "ipca_mes": "IPCA do mês (%)",
    "ipca_3_meses": "IPCA 3 meses (%)",
    "ipca_6_meses": "IPCA 6 meses (%)",
    "ipca_12_meses": "IPCA 12 meses (%)",
    "incc": "INCC",
    "dolar_fechamento": "Dólar (R$)",
    "embi_brazil": "EMBI Brasil (pontos)",
    "qtd_invest": "Investidores em FIIs",
    "fii_gt": "Busca: FII",
    "fundos_imob_gt": "Busca: fundos imobiliários",
    "ifix_gt": "Busca: IFIX",
    "juro_real_ex_ante": "Selic − IPCA 12m (p.p.)",
}


def ler() -> pd.DataFrame:
    """Lê a Mart com uma conexão somente de leitura, sempre fechada ao sair."""
    con = duckdb.connect(str(BANCO), read_only=True)
    try:
        return con.execute("SELECT * FROM mart.indicadores_imobiliarios").fetchdf()
    finally:
        con.close()


def _formatar(valor: object, casas: int) -> str:
    if pd.isna(valor):
        return "—"
    formatado = f"{float(valor):,.{casas}f}"
    return formatado.replace(",", "\0").replace(".", ",").replace("\0", ".")


def reais(valor: object, casas: int = 2) -> str:
    return f"R$ {_formatar(valor, casas)}"


def pct(valor: object, casas: int = 1) -> str:
    return f"{_formatar(valor, casas)}%"


def numero(valor: object, casas: int = 0) -> str:
    return _formatar(valor, casas)


def _figura_temporal(
    df: pd.DataFrame,
    series_principais: tuple[str, ...],
    unidade_principal: str,
    series_secundarias: tuple[str, ...] = (),
    unidade_secundaria: str = "",
) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": bool(series_secundarias)}]])
    for indice, coluna in enumerate(series_principais + series_secundarias):
        secundaria = coluna in series_secundarias
        fig.add_trace(
            go.Scatter(
                x=df["data"],
                y=df[coluna],
                mode="lines",
                name=ROTULOS[coluna],
                line={"color": CORES[indice % len(CORES)], "width": 2},
                connectgaps=False,
                hovertemplate=(
                    "%{x|%d/%m/%Y}<br>"
                    + ROTULOS[coluna]
                    + ": %{y:,.2f}<extra></extra>"
                ),
            ),
            secondary_y=secundaria,
        )

    fig.update_layout(
        template="plotly_white",
        autosize=True,
        margin={"l": 60, "r": 60 if series_secundarias else 24, "t": 64, "b": 48},
        legend={"orientation": "h", "y": 1.02, "x": 0},
        hovermode="x unified",
        separators=",.",
    )
    fig.update_xaxes(title_text="Data", showgrid=False)
    fig.update_yaxes(title_text=unidade_principal, secondary_y=False)
    if series_secundarias:
        fig.update_yaxes(
            title_text=unidade_secundaria,
            secondary_y=True,
            showgrid=False,
        )
    return fig


def grafico_01_ifix_ipca(df: pd.DataFrame) -> go.Figure:
    return _figura_temporal(
        df,
        ("ifix_fech",),
        "IFIX (pontos)",
        ("ipca_mes", "ipca_12_meses"),
        "IPCA (%)",
    )


def grafico_02_ifix_selic(df: pd.DataFrame) -> go.Figure:
    return _figura_temporal(
        df,
        ("ifix_fech",),
        "IFIX (pontos)",
        ("selic_meta", "selic_diaria_pct"),
        "Selic (%)",
    )


def grafico_03_incc_ifix(df: pd.DataFrame) -> go.Figure:
    return _figura_temporal(
        df,
        ("ifix_fech",),
        "IFIX (pontos)",
        ("incc",),
        "INCC (índice)",
    )


def grafico_04_dolar_ifix(df: pd.DataFrame) -> go.Figure:
    fig = _figura_temporal(
        df,
        ("ifix_fech",),
        "IFIX (pontos)",
        ("dolar_fechamento",),
        "Dólar (R$)",
    )
    fig.update_yaxes(tickprefix="R$ ", tickformat=",.2f", secondary_y=True)
    return fig


def grafico_05_embi_ifix(df: pd.DataFrame) -> go.Figure:
    return _figura_temporal(
        df,
        ("ifix_fech",),
        "IFIX (pontos)",
        ("embi_brazil",),
        "EMBI Brasil (pontos)",
    )


def grafico_06_investidores_ifix(df: pd.DataFrame) -> go.Figure:
    return _figura_temporal(
        df,
        ("ifix_fech",),
        "IFIX (pontos)",
        ("qtd_invest",),
        "Investidores (CPFs)",
    )


def grafico_07_google_ifix(df: pd.DataFrame) -> go.Figure:
    return _figura_temporal(
        df,
        ("ifix_fech",),
        "IFIX (pontos)",
        ("fii_gt", "fundos_imob_gt", "ifix_gt"),
        "Google Trends (índice)",
    )


def grafico_08_ipca_horizontes(df: pd.DataFrame) -> go.Figure:
    return _figura_temporal(
        df,
        ("ifix_fech",),
        "IFIX (pontos)",
        ("ipca_3_meses", "ipca_6_meses", "ipca_12_meses"),
        "IPCA (%)",
    )


def grafico_09_juro_real_ifix(df: pd.DataFrame) -> go.Figure:
    return _figura_temporal(
        df,
        ("ifix_fech",),
        "IFIX (pontos)",
        ("juro_real_ex_ante",),
        "Diferencial Selic − IPCA 12m (p.p.)",
    )


GRAFICOS: Final = (
    ("01", "IFIX e IPCA", grafico_01_ifix_ipca),
    ("02", "IFIX e Selic", grafico_02_ifix_selic),
    ("03", "INCC e IFIX", grafico_03_incc_ifix),
    ("04", "Dólar e IFIX", grafico_04_dolar_ifix),
    ("05", "EMBI Brasil e IFIX", grafico_05_embi_ifix),
    ("06", "Investidores em FIIs e IFIX", grafico_06_investidores_ifix),
    ("07", "Interesse de busca e IFIX", grafico_07_google_ifix),
    ("08", "IPCA em diferentes horizontes e IFIX", grafico_08_ipca_horizontes),
    ("09", "Diferencial Selic − IPCA 12m e IFIX", grafico_09_juro_real_ifix),
)


def html_do_grafico(fig: go.Figure) -> str:
    grafico = fig.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        config={"responsive": True, "displaylogo": False},
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>html,body{height:100%;width:100%;margin:0;overflow:hidden}"
        ".plotly-graph-div{height:100%!important;width:100%!important}"
        "</style></head><body>"
        f"{grafico}</body></html>"
    )

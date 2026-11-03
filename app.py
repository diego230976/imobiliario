"""Aplicação Streamlit para explorar a camada analítica mart."""

from datetime import date

import duckdb
import pandas as pd
import streamlit as st
from streamlit_elements import dashboard, elements, html, mui
from streamlit_elements.core.frame import new_element

import painel

st.set_page_config(
    page_title="Imobiliário · contexto de mercado",
    page_icon="📊",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def carregar_dados() -> pd.DataFrame:
    return painel.ler()


def layout_inicial() -> dict[str, list[dict[str, object]]]:
    layouts = {}
    for breakpoint, colunas, largura in (
        ("lg", 3, 4),
        ("md", 2, 4),
        ("sm", 1, 4),
        ("xs", 1, 2),
    ):
        layouts[breakpoint] = [
            dashboard.Item(
                identificador,
                (indice % colunas) * largura,
                (indice // colunas) * 3,
                largura,
                3,
                minW=min(2, largura),
                minH=2,
            )
            for indice, (identificador, _, _) in enumerate(painel.GRAFICOS)
        ]
    return layouts


def guardar_layout(layout: list[dict], layouts: dict[str, list[dict]]) -> None:
    st.session_state["layout_graficos"] = layouts


def falhar_painel(mensagem: str) -> None:
    st.error(
        f"{mensagem} Execute `uv run python -m pipeline.mart` "
        "para gerar a camada analítica."
    )
    st.stop()


st.title("Imobiliário · contexto de mercado")

if not painel.BANCO.is_file():
    falhar_painel(f"Banco de dados não encontrado: {painel.BANCO}")

try:
    dados = carregar_dados()
except (duckdb.Error, OSError) as exc:
    falhar_painel(f"Não foi possível ler {painel.TABELA}: {exc}")

colunas_faltantes = [
    coluna
    for coluna in painel.COLUNAS_OBRIGATORIAS
    if coluna not in dados.columns
]
if colunas_faltantes:
    falhar_painel(
        f"Colunas obrigatórias ausentes em {painel.TABELA}: "
        + ", ".join(colunas_faltantes)
    )
if dados.empty:
    falhar_painel(f"A tabela {painel.TABELA} está vazia.")

dados = dados.sort_values("data").reset_index(drop=True)
data_minima = pd.Timestamp(dados["data"].iloc[0]).date()
data_maxima = pd.Timestamp(dados["data"].iloc[-1]).date()
ultimo = dados.iloc[-1]

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
    div[data-testid="stMetric"] {
        background: #f5f8fa;
        border: 1px solid #e3ebef;
        border-radius: 0.75rem;
        padding: 0.75rem;
    }
    div[data-testid="stMetricValue"] {font-size: clamp(1rem, 2vw, 1.35rem);}
    div[data-testid="stMetricLabel"] {font-size: 0.85rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

cabecalho, seletor, acoes = st.columns([1.55, 1.55, 1])
with cabecalho:
    st.subheader("Contexto de mercado")
with seletor:
    periodo = st.date_input(
        "Período dos gráficos",
        value=(data_minima, data_maxima),
        min_value=data_minima,
        max_value=data_maxima,
        format="DD/MM/YYYY",
        key="periodo_graficos",
    )
with acoes:
    st.write("")
    if st.button("Recarregar dados", use_container_width=True):
        carregar_dados.clear()
        st.rerun()
    if st.button("Restaurar layout", use_container_width=True):
        st.session_state["layout_graficos"] = layout_inicial()
        st.session_state["layout_versao"] = st.session_state.get(
            "layout_versao", 0
        ) + 1
        st.rerun()

st.caption(
    "Os cartões valem para o histórico inteiro. "
    f"Último dado disponível: {data_maxima:%d/%m/%Y}."
)

cartoes = st.columns(5)
cartoes[0].metric("IFIX", f"{painel.numero(ultimo['ifix_fech'], 2)} pts")
cartoes[1].metric(
    "Variação diária do IFIX",
    painel.pct(ultimo["ifix_var_pct"], 4),
)
cartoes[2].metric(
    "Diferencial Selic − IPCA 12m",
    f"{painel.numero(ultimo['juro_real_ex_ante'], 2)} p.p.",
    help="Proxy retrospectiva baseada no IPCA observado em 12 meses.",
)
cartoes[3].metric(
    "Selic meta",
    f"{painel.pct(ultimo['selic_meta'], 2)} a.a.",
)
cartoes[4].metric(
    "IPCA 12 meses",
    painel.pct(ultimo["ipca_12_meses"], 2),
)

st.divider()
st.subheader("Séries históricas")

if not isinstance(periodo, tuple) or len(periodo) != 2:
    st.info("Selecione as datas inicial e final para exibir os gráficos.")
    st.stop()

inicio, fim = periodo
if not isinstance(inicio, date) or not isinstance(fim, date):
    st.info("Selecione as datas inicial e final para exibir os gráficos.")
    st.stop()

datas = dados["data"].dt.date
dados_periodo = dados.loc[(datas >= inicio) & (datas <= fim)]

if dados_periodo.empty:
    st.warning("Não há observações da Mart dentro do período selecionado.")
    st.stop()

if "layout_graficos" not in st.session_state:
    st.session_state["layout_graficos"] = layout_inicial()
if "layout_versao" not in st.session_state:
    st.session_state["layout_versao"] = 0

with elements(f"painel_imobiliario_{st.session_state['layout_versao']}"):
    # O atalho dashboard.Grid só expõe o layout "lg"; usar o factory permite
    # preservar e restaurar cada breakpoint responsivo na sessão.
    grid = new_element("dashboardGrid", "Grid")
    with grid(
        layouts=st.session_state["layout_graficos"],
        breakpoints={"lg": 1000, "md": 600, "sm": 400, "xs": 0},
        cols={"lg": 12, "md": 8, "sm": 4, "xs": 2},
        rowHeight=110,
        onLayoutChange=guardar_layout,
        draggableHandle=".grafico-cabecalho",
        margin=[16, 16],
    ):
        for identificador, titulo, funcao_grafico in painel.GRAFICOS:
            figura = funcao_grafico(dados_periodo)
            html_grafico = painel.html_do_grafico(figura)
            with mui.Paper(
                key=identificador,
                elevation=2,
                square=False,
                sx={
                    "height": "100%",
                    "width": "100%",
                    "overflow": "hidden",
                    "borderRadius": 2,
                    "display": "flex",
                    "flexDirection": "column",
                },
            ):
                mui.Typography(
                    f"{identificador} · {titulo}",
                    className="grafico-cabecalho",
                    sx={
                        "fontWeight": 600,
                        "fontSize": "0.95rem",
                        "px": 2,
                        "pt": 1.5,
                        "cursor": "move",
                    },
                )
                html.iframe(
                    srcDoc=html_grafico,
                    title=f"{identificador} · {titulo}",
                    style={
                        "width": "100%",
                        "height": "100%",
                        "border": "0",
                        "flex": "1",
                    },
                )

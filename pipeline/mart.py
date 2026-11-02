"""Constrói a camada mart a partir das nove séries do schema ``refined``.

A tabela ``mart.indicadores_imobiliarios`` tem uma linha por pregão de
``refined.ifix``. Cada série satélite é associada pela última observação
disponível na própria data ou antes dela, sem interpolação nem look-ahead.
As taxas e índices mensais/anuais permanecem vigentes até a próxima observação.

Os KPIs seguem as fórmulas do contrato: diferencial entre Selic meta e IPCA
acumulado em 12 meses, conversão da Selic anual para a convenção de 252 dias
úteis e variação percentual diária do IFIX. Apesar do nome contratual
``juro_real_ex_ante``, o IPCA de 12 meses é inflação observada, não expectativa
de inflação; portanto, o cálculo é um diferencial retrospectivo conforme a
definição do projeto, não uma medida econômica ex-ante estrita.

A tabela é recriada em cada execução. A validação prévia ocorre antes de
qualquer criação ou alteração do schema de destino, e a conexão é sempre
fechada pelo módulo chamador.
"""

import sys
from pathlib import Path

import pandas as pd

from pipeline.db import conectar, criar_schema, gravar

BANCO = Path(__file__).resolve().parent.parent / "imobiliario.duckdb"
SCHEMA_ORIGEM = "refined"
SCHEMA_DESTINO = "mart"
TABELA_DESTINO = "indicadores_imobiliarios"

TABELAS_OBRIGATORIAS = {
    "ifix": ("data", "ifix_fech"),
    "selic": ("data", "selic_meta"),
    "ipca": (
        "data",
        "ipca_mes",
        "ipca_3_meses",
        "ipca_6_meses",
        "ipca_ano",
        "ipca_12_meses",
    ),
    "dolar": ("data", "dolar_fechamento"),
    "incc": ("data", "incc"),
    "investidores_fii": ("data", "qtd_invest"),
    "embi_brazil": ("data", "embi_brazil"),
    "pib_per_capita": ("data", "pib_per_capita_usd"),
    "google_trends": ("data", "fii_gt", "fundos_imob_gt", "ifix_gt"),
}

COLUNAS_SAIDA = (
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

TIPOS_ESPERADOS = {
    "data": "DATE",
    "ifix_fech": "DOUBLE",
    "selic_meta": "DOUBLE",
    "ipca_mes": "DOUBLE",
    "ipca_3_meses": "DOUBLE",
    "ipca_6_meses": "DOUBLE",
    "ipca_ano": "DOUBLE",
    "ipca_12_meses": "DOUBLE",
    "dolar_fechamento": "DOUBLE",
    "incc": "DOUBLE",
    "qtd_invest": "BIGINT",
    "embi_brazil": "BIGINT",
    "pib_per_capita_usd": "DOUBLE",
    "fii_gt": "BIGINT",
    "fundos_imob_gt": "DOUBLE",
    "ifix_gt": "DOUBLE",
    "juro_real_ex_ante": "DOUBLE",
    "selic_diaria_pct": "DOUBLE",
    "ifix_var_pct": "DOUBLE",
}

COLUNAS_SEM_NULOS = COLUNAS_SAIDA[:-1]

QUERY_MART = """
WITH indicadores AS (
    SELECT
        i.data,
        i.ifix_fech,
        s.selic_meta,
        p.ipca_mes,
        p.ipca_3_meses,
        p.ipca_6_meses,
        p.ipca_ano,
        p.ipca_12_meses,
        d.dolar_fechamento,
        n.incc,
        v.qtd_invest,
        e.embi_brazil,
        b.pib_per_capita_usd,
        g.fii_gt,
        g.fundos_imob_gt,
        g.ifix_gt,
        ROUND(s.selic_meta - p.ipca_12_meses, 4) AS juro_real_ex_ante,
        ROUND(
            (POWER(1.0 + (s.selic_meta / 100.0), 1.0 / 252.0) - 1.0)
            * 100.0,
            6
        ) AS selic_diaria_pct
    FROM refined.ifix AS i
    ASOF LEFT JOIN refined.selic AS s ON i.data >= s.data
    ASOF LEFT JOIN refined.ipca AS p ON i.data >= p.data
    ASOF LEFT JOIN refined.dolar AS d ON i.data >= d.data
    ASOF LEFT JOIN refined.incc AS n ON i.data >= n.data
    ASOF LEFT JOIN refined.investidores_fii AS v ON i.data >= v.data
    ASOF LEFT JOIN refined.embi_brazil AS e ON i.data >= e.data
    ASOF LEFT JOIN refined.pib_per_capita AS b ON i.data >= b.data
    ASOF LEFT JOIN refined.google_trends AS g ON i.data >= g.data
)
SELECT
    data,
    ifix_fech,
    selic_meta,
    ipca_mes,
    ipca_3_meses,
    ipca_6_meses,
    ipca_ano,
    ipca_12_meses,
    dolar_fechamento,
    incc,
    qtd_invest,
    embi_brazil,
    pib_per_capita_usd,
    fii_gt,
    fundos_imob_gt,
    ifix_gt,
    juro_real_ex_ante,
    selic_diaria_pct,
    ROUND(
        (
            (
                ifix_fech
                - LAG(ifix_fech, 1) OVER (ORDER BY data ASC)
            )
            / NULLIF(LAG(ifix_fech, 1) OVER (ORDER BY data ASC), 0)
        )
        * 100.0,
        4
    ) AS ifix_var_pct
FROM indicadores
ORDER BY data ASC
"""


def falhar(mensagem: str) -> None:
    print(mensagem, file=sys.stderr)
    raise SystemExit(1)


def formatar_milhar(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def validar_pre_requisitos(con) -> int:
    esquemas = {
        linha[0]
        for linha in con.execute(
            "SELECT schema_name FROM information_schema.schemata"
        ).fetchall()
    }
    if SCHEMA_ORIGEM not in esquemas:
        falhar(f"Schema obrigatório não encontrado: {SCHEMA_ORIGEM}")

    tabelas_existentes = {
        linha[0]
        for linha in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = ? AND table_type = 'BASE TABLE'",
            [SCHEMA_ORIGEM],
        ).fetchall()
    }
    tabelas_faltantes = [
        tabela for tabela in TABELAS_OBRIGATORIAS if tabela not in tabelas_existentes
    ]
    if tabelas_faltantes:
        falhar(
            f"Tabelas obrigatórias ausentes em {SCHEMA_ORIGEM}: "
            + ", ".join(tabelas_faltantes)
        )

    colunas_por_tabela = {}
    for tabela in TABELAS_OBRIGATORIAS:
        colunas_por_tabela[tabela] = {
            linha[0]
            for linha in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = ? AND table_name = ?",
                [SCHEMA_ORIGEM, tabela],
            ).fetchall()
        }

    colunas_faltantes = [
        f"{tabela}.{coluna}"
        for tabela, colunas in TABELAS_OBRIGATORIAS.items()
        for coluna in colunas
        if coluna not in colunas_por_tabela[tabela]
    ]
    if colunas_faltantes:
        falhar(
            f"Colunas obrigatórias ausentes em {SCHEMA_ORIGEM}: "
            + ", ".join(colunas_faltantes)
        )

    contagens = {
        tabela: con.execute(
            f"SELECT COUNT(*) FROM {SCHEMA_ORIGEM}.{tabela}"
        ).fetchone()[0]
        for tabela in TABELAS_OBRIGATORIAS
    }
    tabelas_vazias = [
        tabela for tabela, contagem in contagens.items() if contagem == 0
    ]
    if tabelas_vazias:
        falhar(
            f"Tabelas obrigatórias vazias em {SCHEMA_ORIGEM}: "
            + ", ".join(tabelas_vazias)
        )

    return contagens["ifix"]


def validar_dataframe(df: pd.DataFrame, linhas_base: int) -> None:
    if list(df.columns) != list(COLUNAS_SAIDA):
        falhar(
            "Colunas inesperadas na consulta mart: "
            + ", ".join(str(coluna) for coluna in df.columns)
        )

    linhas_out = len(df)
    if linhas_out != linhas_base:
        falhar(
            f"Cardinalidade inválida: mart={formatar_milhar(linhas_out)} "
            f"| refined.ifix={formatar_milhar(linhas_base)}"
        )

    nulos_obrigatorios = df.loc[:, COLUNAS_SEM_NULOS].isna().sum()
    nulos_encontrados = {
        coluna: int(contagem)
        for coluna, contagem in nulos_obrigatorios.items()
        if contagem
    }
    if nulos_encontrados:
        detalhes = ", ".join(
            f"{coluna}={formatar_milhar(contagem)}"
            for coluna, contagem in nulos_encontrados.items()
        )
        falhar(f"Valores NULL em colunas obrigatórias: {detalhes}")

    mascara_nula_ifix = df["ifix_var_pct"].isna()
    datas_nulas_ifix = df.loc[mascara_nula_ifix, "data"]
    if (
        int(mascara_nula_ifix.sum()) != 1
        or datas_nulas_ifix.iloc[0] != df["data"].iloc[0]
    ):
        falhar(
            "ifix_var_pct deve ter exatamente um NULL na primeira data "
            "da série"
        )

    if df["data"].duplicated().any():
        falhar("Chave lógica duplicada em mart: data")


def validar_tabela_destino(con, linhas_base: int) -> None:
    qualificacao = f"{SCHEMA_DESTINO}.{TABELA_DESTINO}"
    colunas = con.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position",
        [SCHEMA_DESTINO, TABELA_DESTINO],
    ).fetchall()
    tipos_obtidos = dict(colunas)
    if tipos_obtidos != TIPOS_ESPERADOS or tuple(tipos_obtidos) != COLUNAS_SAIDA:
        falhar(f"Colunas ou tipos inesperados em {qualificacao}: {colunas}")

    expressoes_nulos = ", ".join(
        f'COUNT(*) FILTER (WHERE "{coluna}" IS NULL) AS "{coluna}"'
        for coluna in COLUNAS_SAIDA
    )
    valores = con.execute(
        f"SELECT COUNT(*), {expressoes_nulos} FROM {qualificacao}"
    ).fetchone()
    linhas_out = valores[0]
    nulos = dict(zip(COLUNAS_SAIDA, valores[1:]))

    if linhas_out != linhas_base:
        falhar(
            f"Cardinalidade inválida após gravar: mart="
            f"{formatar_milhar(linhas_out)} "
            f"| refined.ifix={formatar_milhar(linhas_base)}"
        )

    nulos_obrigatorios = {
        coluna: nulos[coluna] for coluna in COLUNAS_SEM_NULOS if nulos[coluna]
    }
    if nulos_obrigatorios:
        detalhes = ", ".join(
            f"{coluna}={formatar_milhar(contagem)}"
            for coluna, contagem in nulos_obrigatorios.items()
        )
        falhar(f"Valores NULL gravados em colunas obrigatórias: {detalhes}")

    if nulos["ifix_var_pct"] != 1:
        falhar(
            "ifix_var_pct deve ter exatamente um NULL após gravar; "
            f"encontrados {formatar_milhar(nulos['ifix_var_pct'])}"
        )

    primeira_data = con.execute(
        f"SELECT MIN(data) FROM {qualificacao}"
    ).fetchone()[0]
    data_nula = con.execute(
        f"SELECT data FROM {qualificacao} WHERE ifix_var_pct IS NULL"
    ).fetchone()[0]
    if data_nula != primeira_data:
        falhar(
            "O NULL de ifix_var_pct não está na primeira data: "
            f"{data_nula}"
        )


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    if not BANCO.is_file():
        falhar(f"Banco de dados não encontrado: {BANCO}")

    con = conectar()
    try:
        linhas_base = validar_pre_requisitos(con)
        df = con.execute(QUERY_MART).fetchdf()
        df["data"] = pd.to_datetime(df["data"]).dt.date
        validar_dataframe(df, linhas_base)

        criar_schema(con, SCHEMA_DESTINO)
        linhas_out = gravar(con, df, SCHEMA_DESTINO, TABELA_DESTINO)
        validar_tabela_destino(con, linhas_base)

        qtd_colunas = len(df.columns)
        fan_out = linhas_out - linhas_base
        print(
            f"{SCHEMA_DESTINO}.{TABELA_DESTINO}: "
            f"{formatar_milhar(linhas_out)} "
            f"(base_ifix: {formatar_milhar(linhas_base)} | "
            f"colunas: {formatar_milhar(qtd_colunas)} | "
            f"fan_out: {formatar_milhar(fan_out)})"
        )
    finally:
        con.close()


if __name__ == "__main__":
    main()

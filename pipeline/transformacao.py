"""Transforma as tabelas raw para a camada refined."""

import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from pipeline.db import conectar, criar_schema, gravar

SCHEMA_ORIGEM = "raw"
SCHEMA_DESTINO = "refined"
BANCO = Path(__file__).resolve().parent.parent / "imobiliario.duckdb"

TABELAS = {
    "dolar": {
        "data": "data",
        "dolar_fechamento": "dolar_fechamento",
    },
    "embi_brazil": {
        "data": "data",
        "embi_brazil": "embi_brazil",
    },
    "google_trends": {
        "data": "data",
        "fii_gt": "fii_gt",
        "fundos_imob_gt": "fundos_imob_gt",
        "ifix_gt": "ifix_gt",
    },
    "ifix": {
        "data": "data",
        "ifix_fech": "ifix_fech",
    },
    "incc": {
        "data": "data",
        "incc": "incc",
    },
    "investidores_fii": {
        "data": "data",
        "qtd_invest": "qtd_invest",
    },
    "ipca": {
        "data": "data",
        "ipca_mes": "ipca_mes",
        "ipca_3_meses": "ipca_3_meses",
        "ipca_6_meses": "ipca_6_meses",
        "ipca_ano": "ipca_ano",
        "ipca_12_meses": "ipca_12_meses",
    },
    "pib_per_capita": {
        "data": "data",
        "pib_per_capta_usd": "pib_per_capita_usd",
    },
    "selic": {
        "data": "data",
        "selic_meta": "selic_meta",
    },
}

COLUNAS_INTEIRAS = {
    ("embi_brazil", "embi_brazil"),
    ("google_trends", "fii_gt"),
    ("investidores_fii", "qtd_invest"),
}
FORMATOS_DATA = (
    (re.compile(r"\d{4}-\d{2}\Z"), "%Y-%m"),
    (re.compile(r"\d{4}-\d{2}-\d{2}\Z"), "%Y-%m-%d"),
)


def falhar(mensagem: str) -> None:
    print(mensagem, file=sys.stderr)
    raise SystemExit(1)


def formatar_milhar(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def validar_pre_requisitos(con) -> None:
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
    faltantes = [tabela for tabela in TABELAS if tabela not in tabelas_existentes]
    if faltantes:
        falhar(f"Tabelas obrigatórias ausentes em {SCHEMA_ORIGEM}: {', '.join(faltantes)}")

    colunas_por_tabela = {}
    for tabela in TABELAS:
        colunas_por_tabela[tabela] = {
            linha[0]
            for linha in con.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = ? AND table_name = ?",
                [SCHEMA_ORIGEM, tabela],
            ).fetchall()
        }

    faltas_de_coluna = [
        f"{tabela}.{origem}"
        for tabela, mapa in TABELAS.items()
        for origem in mapa
        if origem not in colunas_por_tabela[tabela]
    ]
    if faltas_de_coluna:
        falhar(
            "Colunas obrigatórias ausentes em raw: "
            + ", ".join(faltas_de_coluna)
        )


def converter_data(valor: object, tabela: str) -> date:
    if pd.isna(valor) or valor == "":
        falhar(f"Valor inválido em {tabela}.data: {valor!r} (data nula ou vazia)")

    texto = str(valor)
    for padrao, formato_origem in FORMATOS_DATA:
        if padrao.fullmatch(texto):
            try:
                data = datetime.strptime(texto, formato_origem).date()
                texto_brasileiro = data.strftime("%d-%m-%Y")
                return datetime.strptime(texto_brasileiro, "%d-%m-%Y").date()
            except ValueError:
                break

    falhar(f"Data inválida em {tabela}.data: {valor!r}")


def converter_numeros(serie: pd.Series, tabela: str, coluna: str) -> pd.Series:
    valores = []
    inteiro = (tabela, coluna) in COLUNAS_INTEIRAS
    minimo_bigint = -(2**63)
    maximo_bigint = 2**63 - 1

    for valor in serie:
        if pd.isna(valor):
            valores.append(pd.NA if inteiro else float("nan"))
            continue

        texto = str(valor).replace(",", ".")
        try:
            numero = Decimal(texto)
            if not numero.is_finite():
                raise InvalidOperation
            if inteiro:
                if numero != numero.to_integral_value():
                    raise InvalidOperation
                convertido = int(numero)
                if not minimo_bigint <= convertido <= maximo_bigint:
                    raise InvalidOperation
            else:
                convertido = float(numero)
                if not pd.notna(convertido) or convertido in (float("inf"), float("-inf")):
                    raise InvalidOperation
        except (InvalidOperation, ValueError, OverflowError):
            falhar(f"Valor numérico inválido em {tabela}.{coluna}: {valor!r}")
        valores.append(convertido)

    return pd.Series(valores, index=serie.index, dtype="Int64" if inteiro else "float64")


def transformar(tabela: str, origem: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    mapa = TABELAS[tabela]
    resultado = pd.DataFrame(index=origem.index)
    resultado["data"] = pd.Series(
        [converter_data(valor, tabela) for valor in origem["data"]],
        index=origem.index,
        dtype=object,
    )

    for coluna_origem, coluna_destino in mapa.items():
        if coluna_origem == "data":
            continue
        resultado[coluna_destino] = converter_numeros(
            origem[coluna_origem], tabela, coluna_origem
        )

    linhas_entrada = len(resultado)
    resultado = resultado.drop_duplicates()
    conflitos = resultado[resultado.duplicated(subset=["data"], keep=False)]
    if not conflitos.empty:
        datas = sorted({data.isoformat() for data in conflitos["data"]})
        falhar(f"Conflito de chave em {tabela}.data: {', '.join(datas)}")

    resultado = resultado.sort_values("data", kind="stable").reset_index(drop=True)
    return resultado, linhas_entrada


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    if not BANCO.is_file():
        falhar(f"Banco de dados não encontrado: {BANCO}")

    con = conectar()
    try:
        validar_pre_requisitos(con)

        transformadas = {}
        for tabela, mapa in TABELAS.items():
            colunas = ", ".join(f'"{coluna}"' for coluna in mapa)
            origem = con.execute(
                f"SELECT {colunas} FROM {SCHEMA_ORIGEM}.{tabela}"
            ).fetchdf()
            transformadas[tabela] = transformar(tabela, origem)

        criar_schema(con, SCHEMA_DESTINO)
        total_entrada = 0
        total_saida = 0
        for tabela, (df, linhas_entrada) in transformadas.items():
            linhas_saida = gravar(con, df, SCHEMA_DESTINO, tabela)
            removidos = linhas_entrada - linhas_saida
            total_entrada += linhas_entrada
            total_saida += linhas_saida
            print(
                f"{SCHEMA_DESTINO}.{tabela}: {formatar_milhar(linhas_saida)} "
                f"(in: {formatar_milhar(linhas_entrada)} | "
                f"removidos: {formatar_milhar(removidos)})"
            )
        print(
            f"Total: {formatar_milhar(total_saida)} "
            f"(in: {formatar_milhar(total_entrada)} | "
            f"removidos: {formatar_milhar(total_entrada - total_saida)})"
        )
    finally:
        con.close()


if __name__ == "__main__":
    main()

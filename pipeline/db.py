"""Especificação do módulo pipeline/db.py.

Expõe exatamente:
- PASTA_RAW: Path da pasta raw/ com os nove .csv.
- conectar(): abre o imobiliario.duckdb, criando se faltar.
- criar_schema(con, nome): executa CREATE SCHEMA IF NOT EXISTS.
- gravar(con, df, schema, tabela): grava o DataFrame e devolve a contagem lida do banco.

Regras:
- D1. CAMINHOS: PASTA_RAW e imobiliario.duckdb são resolvidos a partir da
  localização do próprio db.py (a pasta acima de pipeline/), nunca do diretório
  corrente.
- D2. TRÊS FUNÇÕES E UMA CONSTANTE, NADA MAIS: db.py não lê CSV, não conhece
  nome de tabela, não imprime nada e não converte tipo.
- D3. gravar: Recria a tabela (CREATE OR REPLACE TABLE schema.tabela) com as
  colunas e os tipos do DataFrame, sem alterar nada (str vira VARCHAR, nulo
  continua NULL), sem deixar view ou tabela temporária para trás, e devolve
  SELECT count(*) da tabela recém-gravada lido do banco.
- D4. CONEXÃO: conectar() devolve a conexão aberta; quem chama é quem fecha.
  Não guarda conexão global.
"""

from pathlib import Path
import duckdb

PASTA_RAW = Path(__file__).resolve().parent.parent / "raw"


def conectar():
    return duckdb.connect(PASTA_RAW.parent / "imobiliario.duckdb")


def criar_schema(con, nome):
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {nome}")


def gravar(con, df, schema, tabela):
    # O DuckDB lê a variável local `df` via replacement scan sem criar view/tabela temporária no catálogo
    con.execute(f"CREATE OR REPLACE TABLE {schema}.{tabela} AS SELECT * FROM df")
    return con.execute(f"SELECT count(*) FROM {schema}.{tabela}").fetchone()[0]


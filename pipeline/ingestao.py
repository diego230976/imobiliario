"""Especificação do módulo pipeline/ingestao.py.

Regras:
- 1. ESCOPO E NOMES: Grava no schema `raw` o mapa literal dos nove arquivos CSV
  (dolar.csv -> dolar, embi_brazil.csv -> embi_brazil,
  google_trends.csv -> google_trends, ifix.csv -> ifix, incc.csv -> incc,
  investidores_fii.csv -> investidores_fii, ipca.csv -> ipca,
  pib_per_capita.csv -> pib_per_capita, selic.csv -> selic).
- 2. PROIBIÇÕES: Nenhuma conversão de tipo, descarte/deduplicação de linha,
  alteração de nome de coluna ou correção/preenchimento/normalização de valor.
  Data continua texto e nulo continua nulo.
- 3. REEXECUÇÃO: Idempotente; cada tabela é recriada (CREATE OR REPLACE),
  nunca acrescentada.
- 4. LEITURA DO ARQUIVO: Leitura direta do .csv com encoding="utf-8" declarado,
  mantendo campos vazios como nulo.
- 5. TIPAGEM: Todas as colunas lidas como texto (dtype=str), sem inferência.
- 6. SAÍDA NA TELA: Reconfigura stdout para utf-8; imprime uma linha por tabela
  com nome qualificado (raw.<tabela>) e contagem vinda do banco formatada com
  ponto como separador de milhar, seguida de uma linha final com o total.
- 7. ERRO: Antes de abrir o banco, verifica a existência dos nove arquivos;
  se faltar algum, lista os ausentes, informa a pasta verificada e encerra com
  sys.exit(1) sem ingerir parcialmente.
"""

import sys
import pandas as pd
from pipeline.db import PASTA_RAW, conectar, criar_schema, gravar

SCHEMA = "raw"

ARQUIVOS_TABELAS = {
    "dolar.csv": "dolar",
    "embi_brazil.csv": "embi_brazil",
    "google_trends.csv": "google_trends",
    "ifix.csv": "ifix",
    "incc.csv": "incc",
    "investidores_fii.csv": "investidores_fii",
    "ipca.csv": "ipca",
    "pib_per_capita.csv": "pib_per_capita",
    "selic.csv": "selic",
}


def formatar_milhar(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    faltantes = [
        arquivo for arquivo in ARQUIVOS_TABELAS if not (PASTA_RAW / arquivo).is_file()
    ]
    if faltantes:
        print(f"Arquivos não encontrados na pasta {PASTA_RAW}: {', '.join(faltantes)}")
        sys.exit(1)

    con = conectar()
    try:
        criar_schema(con, SCHEMA)
        total = 0
        for arquivo, tabela in ARQUIVOS_TABELAS.items():
            df = pd.read_csv(PASTA_RAW / arquivo, encoding="utf-8", dtype=str)
            contagem = gravar(con, df, SCHEMA, tabela)
            total += contagem
            print(f"{SCHEMA}.{tabela}: {formatar_milhar(contagem)}")
        print(f"Total: {formatar_milhar(total)}")
    finally:
        con.close()


if __name__ == "__main__":
    main()


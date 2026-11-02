"""Especificação do módulo ui.py.

Regras:
- U1. O QUE FAZ: Abre o imobiliario.duckdb da raiz do projeto, instala e
  carrega a extensão `ui` do DuckDB (INSTALL ui; LOAD ui;) e executa
  CALL start_ui() para subir o servidor em http://localhost:4213 e abrir o
  navegador.
- U2. FICA DE PÉ ATÉ CTRL+C: Mantém o processo rodando enquanto a conexão
  estiver viva, imprime a URL e a instrução "Ctrl+C para encerrar", e ao
  receber Ctrl+C fecha a conexão e encerra sem traceback.
- U3. NÃO CRIA BANCO: Se imobiliario.duckdb não existir, informa que é preciso
  rodar a ingestão antes e encerra com sys.exit(1), sem usar conectar() de
  pipeline/db.py.
- U4. SEPARAÇÃO: ui.py e pipeline/ingestao.py não se importam.
- U5. SAÍDA NA TELA: Reconfigura stdout para utf-8.
"""

from pathlib import Path
import sys
import time
import duckdb

CAMINHO_BANCO = Path(__file__).resolve().parent / "imobiliario.duckdb"
URL_UI = "http://localhost:4213"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    if not CAMINHO_BANCO.is_file():
        print(
            f"Banco {CAMINHO_BANCO} não encontrado. É preciso rodar a ingestão antes."
        )
        sys.exit(1)

    con = duckdb.connect(CAMINHO_BANCO)
    try:
        con.execute("INSTALL ui; LOAD ui;")
        con.execute("CALL start_ui();")
        print(f"Servidor ativo em {URL_UI} — Ctrl+C para encerrar")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        con.close()


if __name__ == "__main__":
    main()


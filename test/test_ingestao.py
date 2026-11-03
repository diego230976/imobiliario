from pathlib import Path

import duckdb
import pytest

from pipeline import ingestao


def test_csvs_sao_ingestados_sem_perda_de_linhas_ou_inferencia_de_tipo(
    tmp_path: Path, monkeypatch
) -> None:
    pasta_raw = tmp_path / "raw"
    pasta_raw.mkdir()
    for arquivo in ingestao.ARQUIVOS_TABELAS:
        # A segunda linha vazia representa um nulo que a ingestão deve preservar.
        (pasta_raw / arquivo).write_text(
            "data,valor\n2020-01-01,001\n2020-01-02,\n", encoding="utf-8"
        )

    banco = tmp_path / "teste.duckdb"
    monkeypatch.setattr(ingestao, "PASTA_RAW", pasta_raw)
    monkeypatch.setattr(ingestao, "conectar", lambda: duckdb.connect(str(banco)))

    ingestao.main()

    con = duckdb.connect(str(banco), read_only=True)
    try:
        assert con.execute("SELECT * FROM raw.dolar ORDER BY data").fetchall() == [
            ("2020-01-01", "001"),
            ("2020-01-02", None),
        ]
        assert con.execute(
            "SELECT column_name, data_type "
            "FROM information_schema.columns "
            "WHERE table_schema = 'raw' AND table_name = 'dolar' "
            "ORDER BY ordinal_position"
        ).fetchall() == [("data", "VARCHAR"), ("valor", "VARCHAR")]
        assert con.execute(
            "SELECT COUNT(*) FROM raw.selic"
        ).fetchone() == (2,)
    finally:
        con.close()


def test_arquivo_ausente_encerra_antes_de_conectar(
    tmp_path: Path, monkeypatch
) -> None:
    pasta_raw = tmp_path / "raw"
    pasta_raw.mkdir()
    monkeypatch.setattr(ingestao, "PASTA_RAW", pasta_raw)

    def falhar_se_conectar():
        raise AssertionError("o banco não deveria ser aberto")

    monkeypatch.setattr(ingestao, "conectar", falhar_se_conectar)

    with pytest.raises(SystemExit) as exc_info:
        ingestao.main()

    assert exc_info.value.code == 1


def test_formatador_de_milhar_usa_ponto() -> None:
    assert ingestao.formatar_milhar(1234567) == "1.234.567"

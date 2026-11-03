import re
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

import painel
import relatorio


def _dados() -> pd.DataFrame:
    # Pregões consecutivos inventados alimentam cartões e linhas dos gráficos.
    return pd.DataFrame(
        {
            "data": pd.to_datetime(["2020-01-02", "2020-01-03"]),
            "ifix_fech": [1000.0, 1010.0],
            "selic_meta": [10.0, 10.0],
            "ipca_mes": [0.2, 0.2],
            "ipca_3_meses": [0.6, 0.6],
            "ipca_6_meses": [1.2, 1.2],
            "ipca_ano": [0.2, 0.2],
            "ipca_12_meses": [2.0, 2.0],
            "dolar_fechamento": [4.0, 4.1],
            "incc": [500.0, 501.0],
            "qtd_invest": [200, 201],
            "embi_brazil": [100, 101],
            "pib_per_capita_usd": [1000.0, 1000.0],
            "fii_gt": [10, 11],
            "fundos_imob_gt": [20.0, 21.0],
            "ifix_gt": [30.0, 31.0],
            "juro_real_ex_ante": [8.0, 8.0],
            "selic_diaria_pct": [0.037879, 0.037879],
            "ifix_var_pct": [None, 1.0],
        }
    )


def test_relatorio_gera_html_em_tmp_path_e_reutiliza_cartoes_graficos(
    tmp_path: Path, monkeypatch
) -> None:
    banco = tmp_path / "mart.duckdb"
    banco.touch()
    destino = tmp_path / "relatorio.html"
    monkeypatch.setattr(relatorio, "ARQUIVO_SAIDA", destino)
    monkeypatch.setattr(painel, "BANCO", banco)
    monkeypatch.setattr(painel, "ler", _dados)
    monkeypatch.setattr(
        relatorio,
        "datetime",
        type(
            "RelogioFixo",
            (datetime,),
            {
                "now": classmethod(
                    lambda cls, tz=None: datetime(2026, 1, 2, 3, 4, tzinfo=UTC)
                )
            },
        ),
    )

    relatorio.main()

    html = destino.read_text(encoding="utf-8")
    assert "1.010,00 pts" in html
    assert "1,0000%" in html
    assert len(re.findall(r'id="g\d{2}"', html)) == 9
    assert "Dados de " in html


def test_execucoes_do_relatorio_so_alteram_o_rodape(
    tmp_path: Path, monkeypatch
) -> None:
    banco = tmp_path / "mart.duckdb"
    banco.touch()
    destino = tmp_path / "relatorio.html"
    monkeypatch.setattr(relatorio, "ARQUIVO_SAIDA", destino)
    monkeypatch.setattr(painel, "BANCO", banco)
    monkeypatch.setattr(painel, "ler", _dados)
    momentos = iter(
        [
            datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
            datetime(2026, 1, 2, 3, 5, tzinfo=UTC),
        ]
    )
    monkeypatch.setattr(
        relatorio,
        "datetime",
        type(
            "RelogioIncremental",
            (datetime,),
            {"now": classmethod(lambda cls, tz=None: next(momentos))},
        ),
    )

    relatorio.main()
    primeiro = destino.read_text(encoding="utf-8")
    relatorio.main()
    segundo = destino.read_text(encoding="utf-8")

    rodape = re.compile(r"Dados de \d{2}/\d{2}/\d{4} \d{2}:\d{2}")
    assert rodape.sub("RODAPE", primeiro) == rodape.sub("RODAPE", segundo)
    assert rodape.search(primeiro).group() != rodape.search(segundo).group()

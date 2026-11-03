"""Gera um relatório HTML estático com os cartões e gráficos do painel.

O relatório reutiliza a leitura, os formatadores e as figuras de ``painel.py``.
Não depende do Streamlit e não calcula métricas; os gráficos usam todo o
histórico disponível, como no estado inicial do painel.
"""

import base64
import json
import re
import sys
import zlib
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Final

import pandas as pd
import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder

import painel

ARQUIVO_SAIDA: Final = Path(__file__).resolve().parent / "relatorio.html"


def _cartoes(ultimo: pd.Series) -> str:
    itens = (
        ("IFIX", f"{painel.numero(ultimo['ifix_fech'], 2)} pts"),
        ("Variação diária do IFIX", painel.pct(ultimo["ifix_var_pct"], 4)),
        (
            "Diferencial Selic − IPCA 12m",
            f"{painel.numero(ultimo['juro_real_ex_ante'], 2)} p.p.",
        ),
        ("Selic meta", f"{painel.pct(ultimo['selic_meta'], 2)} a.a."),
        ("IPCA 12 meses", painel.pct(ultimo["ipca_12_meses"], 2)),
    )
    return "\n".join(
        "<article class='cartao'>"
        f"<h2>{escape(rotulo)}</h2><p>{escape(valor)}</p>"
        "</article>"
        for rotulo, valor in itens
    )


def _graficos(dados: pd.DataFrame) -> tuple[str, str, str]:
    blocos: list[str] = []
    series_compartilhadas: list[list[object]] = []
    indices_series: dict[str, int] = {}
    templates_compartilhados: list[dict[str, object]] = []
    indices_templates: dict[str, int] = {}
    figuras: list[dict[str, object]] = []
    url_plotly: str | None = None

    for indice, (identificador, titulo, funcao) in enumerate(
        painel.GRAFICOS, start=1
    ):
        figura: go.Figure = funcao(dados)
        grafico_html = figura.to_html(
            full_html=False,
            include_plotlyjs="cdn" if indice == 1 else False,
            config={"responsive": True, "displaylogo": False},
            div_id=f"g{indice:02d}",
        )
        if indice == 1:
            cdn = re.search(
                r'<script[^>]+src="([^"]+)"[^>]*></script>', grafico_html
            )
            if cdn is None:
                raise ValueError("Não foi possível localizar o CDN do Plotly.")
            url_plotly = cdn.group(1)

        div = re.search(
            rf'<div id="g{indice:02d}" class="plotly-graph-div"[^>]*></div>',
            grafico_html,
        )
        if div is None:
            raise ValueError(f"Não foi possível gerar o gráfico g{indice:02d}.")

        figura_json = json.loads(figura.to_json())
        for traco in figura_json["data"]:
            for eixo in ("x", "y"):
                valores = traco.get(eixo)
                if not isinstance(valores, list) or not valores:
                    continue
                chave = json.dumps(
                    valores, ensure_ascii=False, separators=(",", ":")
                )
                if chave not in indices_series:
                    indices_series[chave] = len(series_compartilhadas)
                    series_compartilhadas.append(valores)
                traco[eixo] = {
                    "__serie_compartilhada__": indices_series[chave]
                }

        template = figura_json["layout"].get("template")
        if isinstance(template, dict):
            chave_template = json.dumps(
                template, ensure_ascii=False, separators=(",", ":")
            )
            if chave_template not in indices_templates:
                indices_templates[chave_template] = len(templates_compartilhados)
                templates_compartilhados.append(template)
            figura_json["layout"]["template"] = {
                "__template_compartilhado__": indices_templates[chave_template]
            }

        figuras.append(
            {
                "id": f"g{indice:02d}",
                "data": figura_json["data"],
                "layout": figura_json["layout"],
                "config": {"responsive": True, "displaylogo": False},
            }
        )
        blocos.append(
            "<article class='grafico'>"
            f"<h2>{escape(identificador)} · {escape(titulo)}</h2>"
            f"{div.group(0)}</article>"
        )

    if url_plotly is None:
        raise ValueError("A lista de gráficos do painel está vazia.")
    payload = json.dumps(
        {
            "series": series_compartilhadas,
            "templates": templates_compartilhados,
            "figuras": figuras,
        },
        cls=PlotlyJSONEncoder,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    comprimido = base64.b64encode(zlib.compress(payload, level=9)).decode(
        "ascii"
    )
    return "\n".join(blocos), escape(url_plotly, quote=True), comprimido


def gerar_html(
    dados: pd.DataFrame, gerado_em: datetime | None = None
) -> str:
    """Monta o HTML usando os dados e os gráficos já definidos pelo painel."""
    colunas_faltantes = [
        coluna
        for coluna in painel.COLUNAS_OBRIGATORIAS
        if coluna not in dados.columns
    ]
    if colunas_faltantes:
        raise ValueError(
            "Colunas obrigatórias ausentes em "
            f"{painel.TABELA}: {', '.join(colunas_faltantes)}"
        )
    if dados.empty:
        raise ValueError(f"A tabela {painel.TABELA} está vazia.")

    dados = dados.sort_values("data").reset_index(drop=True)
    momento = gerado_em or datetime.now().astimezone()
    rodape = f"Dados de {momento:%d/%m/%Y %H:%M}"
    graficos_html, url_plotly, payload = _graficos(dados)
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Imobiliário · contexto de mercado</title>
  <script src="{url_plotly}"></script>
  <style>
    :root {{ color-scheme: light; font-family: Arial, sans-serif; color: #31333f; }}
    body {{ margin: 0; background: #f0f2f6; }}
    main {{ max-width: 1440px; margin: 0 auto; padding: 24px; }}
    h1 {{ margin: 0 0 20px; font-size: 1.8rem; }}
    h2 {{ margin: 0; font-size: 1rem; }}
    .cartoes {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 16px; }}
    .cartao, .grafico {{ background: white; border: 1px solid #e3e8ef; border-radius: 12px; }}
    .cartao {{ padding: 16px; }}
    .cartao h2 {{ color: #5b6270; font-size: 0.9rem; }}
    .cartao p {{ margin: 10px 0 0; font-size: 1.5rem; font-weight: 600; }}
    h3 {{ margin: 28px 0 16px; font-size: 1.3rem; }}
    .graficos {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }}
    .grafico {{ min-width: 0; padding: 12px; }}
    .grafico h2 {{ padding: 4px 8px 8px; }}
    .grafico .plotly-graph-div {{ width: 100%; height: 390px !important; }}
    footer {{ margin-top: 24px; color: #626977; font-size: 0.9rem; }}
    #falha-relatorio {{ color: #a4262c; }}
    @media (max-width: 900px) {{
      .cartoes {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .graficos {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 600px) {{
      main {{ padding: 12px; }}
      .cartoes, .graficos {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>Imobiliário · contexto de mercado</h1>
    <section class="cartoes" aria-label="Indicadores mais recentes">
      {_cartoes(dados.iloc[-1])}
    </section>
    <h3>Séries históricas</h3>
    <section class="graficos" aria-label="Gráficos históricos">
      {graficos_html}
    </section>
    <p id="falha-relatorio" role="alert"></p>
    <footer>{escape(rodape)}</footer>
  </main>
  <script>
    async function desenharGraficos() {{
      try {{
        if (!("DecompressionStream" in window)) {{
          throw new Error("Este navegador não oferece suporte à descompactação do relatório.");
        }}
        const binario = atob("{payload}");
        const bytes = Uint8Array.from(binario, caractere => caractere.charCodeAt(0));
        const fluxo = new Blob([bytes]).stream().pipeThrough(
          new DecompressionStream("deflate")
        );
        const dadosRelatorio = JSON.parse(
          await new Response(fluxo).text()
        );
        await Promise.all(dadosRelatorio.figuras.map(figura => {{
          const dadosFigura = figura.data.map(traco => {{
            const copia = {{...traco}};
            for (const eixo of ["x", "y"]) {{
              const referencia = copia[eixo]?.__serie_compartilhada__;
              if (referencia !== undefined) {{
                copia[eixo] = dadosRelatorio.series[referencia];
              }}
            }}
            return copia;
          }});
          const layoutFigura = {{...figura.layout}};
          const templateCompartilhado =
            layoutFigura.template?.__template_compartilhado__;
          if (templateCompartilhado !== undefined) {{
            layoutFigura.template = dadosRelatorio.templates[templateCompartilhado];
          }}
          return Plotly.newPlot(
            figura.id, dadosFigura, layoutFigura, figura.config
          );
        }}));
      }} catch (erro) {{
        document.getElementById("falha-relatorio").textContent =
          `Não foi possível carregar os gráficos: ${{erro.message}}`;
      }}
    }}
    desenharGraficos();
  </script>
</body>
</html>
"""


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not painel.BANCO.is_file():
        raise FileNotFoundError(f"Banco de dados não encontrado: {painel.BANCO}")

    html = gerar_html(painel.ler())
    ARQUIVO_SAIDA.write_text(html, encoding="utf-8")
    tamanho_kb = ARQUIVO_SAIDA.stat().st_size / 1024
    print(f"Relatório: {ARQUIVO_SAIDA}")
    print(f"Tamanho: {tamanho_kb:.2f} KB")


if __name__ == "__main__":
    main()

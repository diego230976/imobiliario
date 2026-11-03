# Dados mercado imobiliário

## Camada mart

Gere `mart.indicadores_imobiliarios` a partir das nove tabelas de `refined`:

```powershell
uv run python -m pipeline.mart
```

O resultado usa os pregões de `refined.ifix` como grão e associa cada série
satélite à última observação disponível até a data do pregão, sem interpolação
ou uso de dados futuros. O KPI `juro_real_ex_ante` segue a fórmula contratual
`selic_meta - ipca_12_meses`; como o IPCA usado é observado e retrospectivo,
esse diferencial não representa uma medida ex-ante estrita.

Execute os testes de contrato com:

```powershell
uv run python -m pytest tests/test_mart.py
```

## Painel de contexto

Inicie o painel Streamlit com:

```powershell
uv run streamlit run app.py
```

O painel lê somente `mart.indicadores_imobiliarios`; gere ou atualize essa
tabela com `uv run python -m pipeline.mart`. Os nove gráficos podem ser
movidos e redimensionados, e o layout pode ser restaurado pelo próprio painel.
Os cartões mostram os valores da data mais recente disponível e não mudam com
o filtro de período dos gráficos. O navegador precisa acessar o CDN do Plotly
para carregar os gráficos incorporados.

Gere também um relatório HTML estático com os mesmos cartões e gráficos:

```powershell
uv run python relatorio.py
```

O comando grava `relatorio.html` na raiz do projeto; abra o arquivo no
navegador. O relatório usa o histórico completo disponível e carrega o Plotly
do CDN.

Execute os testes do painel e da Mart com:

```powershell
uv run python -m pytest tests/test_painel.py tests/test_mart.py tests/test_relatorio.py
```

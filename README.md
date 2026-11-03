# Mercado imobiliário brasileiro — FIIs e IFIX

## Objetivo do projeto

Construir um pipeline de dados e um painel para explorar indicadores do mercado
brasileiro de fundos imobiliários. O projeto integra séries do IFIX com
indicadores macroeconômicos e dados sobre investidores, organizando-os nas
camadas `raw`, `refined` e `mart`.

O painel permite acompanhar os indicadores mais recentes e comparar séries
históricas de IFIX, Selic, inflação, dólar, INCC, EMBI Brasil, investidores em
FIIs, PIB per capita e interesse de busca. O diferencial Selic menos IPCA de
12 meses é uma proxy retrospectiva baseada na inflação observada, não uma
medida ex-ante estrita.

## O que tem aqui

### Dados de `raw/`

| Arquivo | Indicador |
|---|---|
| `dolar.csv` | Dólar |
| `embi_brazil.csv` | EMBI Brasil |
| `google_trends.csv` | Interesse de busca relacionado a FIIs |
| `ifix.csv` | IFIX |
| `incc.csv` | INCC |
| `investidores_fii.csv` | Investidores em FIIs |
| `ipca.csv` | IPCA |
| `pib_per_capita.csv` | PIB per capita |
| `selic.csv` | Selic |

### Aplicação e pipeline

- `pipeline/ingestao.py`: carrega os CSVs para o schema `raw`.
- `pipeline/transformacao.py`: valida e transforma os dados para `refined`.
- `pipeline/mart.py`: consolida as séries em `mart.indicadores_imobiliarios`.
- `app.py` e `painel.py`: painel interativo Streamlit com cartões e nove gráficos.
- `relatorio.py`: gera um relatório HTML estático com os mesmos indicadores.
- `test/`: testes automatizados com bancos temporários e dados inventados.

## Como usar

Instale [Python](https://www.python.org/) e [`uv`](https://docs.astral.sh/uv/).
No PowerShell, execute os comandos a partir da raiz do projeto:

```powershell
# Instalar/sincronizar as dependências
uv sync

# Executar o pipeline, na ordem
uv run python -m pipeline.ingestao
uv run python -m pipeline.transformacao
uv run python -m pipeline.mart

# Iniciar o painel local
uv run streamlit run app.py

# Gerar o relatório HTML estático
uv run python relatorio.py

# Rodar os testes com cobertura
uv run pytest --cov
```

O painel lê `mart.indicadores_imobiliarios` em modo somente leitura. Para
atualizar os dados, execute novamente as etapas do pipeline. O navegador
precisa acessar o CDN do Plotly para exibir os gráficos.

### Painel publicado

[**Acessar o painel de contexto do mercado imobiliário**](https://diego230976-imobiliario-app-g4nxgk.streamlit.app)

## Origem dos dados e licença

O conjunto de dados de referência está publicado no Kaggle:
[Dados mercado imobiliário — Diogo Caliman](https://www.kaggle.com/datasets/diogocaliman/dados-fii).

Na página consultada, a licença do dataset aparece como **Unknown**
(não especificada). Este README não atribui uma licença aos dados. Consulte a
página original e os termos das fontes de cada série antes de redistribuí-los.
A licença do código deste repositório, se houver, é independente da licença
dos dados.

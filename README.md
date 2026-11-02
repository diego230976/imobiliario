# imobiliario

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

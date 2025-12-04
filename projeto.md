# Projeto Fatura AWS — Arquitetura MVC

Documento técnico que descreve o código do dashboard e como cada camada (Model, View, Controller) colabora para entregar a experiência interativa em Streamlit.

## Estrutura em camadas

```
main.py                          # Entry point (streamlit run main.py)
app/
├── main.py                      # Bootstrap da página Streamlit
├── controllers/
│   └── data_controller.py       # Regras de negócio, filtros e payload
├── models/
│   ├── cost_model.py            # Normalização dos CSVs e cálculos estatísticos
│   └── csv_loader.py            # Carregamento e validação de arquivos
└── views/
    └── dashboard_view.py        # Componentes de UI (sidebar, tabelas, gráficos)
```

## Fluxo de execução

1. `main.py` (raiz) serve apenas como entry point e delega para `app.main.main()`.
2. `app/main.py` configura a página e coordena a interação com a View:
   - captura uploads via `dashboard_view.render_file_uploader`;
   - delega carregamento e filtros ao controller (`load_datasets`, `apply_filters`);
   - monta o `DashboardPayload` e envia para a view renderizar.
3. `app/controllers/data_controller.py` é o elo entre a UI e os modelos:
   - valida os arquivos recebidos do Streamlit;
   - usa `csv_loader` para ler os CSVs;
   - usa `cost_model` para normalizar dados, calcular métricas, percentuais, rankings e destaques;
   - retorna tudo empacotado em `DashboardPayload`.
4. `app/models/csv_loader.py` encapsula a leitura robusta dos arquivos, tratando encoding e emitindo `CSVLoadError` para que o controller possa reportar ao usuário.
5. `app/models/cost_model.py` padroniza as 54 colunas, converte tipos, agrega serviços e meses, calcula métricas globais, percentuais e estatísticas — sempre retornando `pandas.DataFrame`/`Series`.
6. `app/views/dashboard_view.py` desenha a interface (sidebar e corpo principal) usando Streamlit + Altair:
   - componentes de entrada (upload, selectbox, multiselect, date_input, botões);
   - tabelas (`st.dataframe`) para dados brutos, totais, percentuais e rankings;
   - gráficos Altair (barras, pizza/donut, linha temporal);
   - feedback visual (mensagens de alerta, info e métricas).

## Interdependências

- **View → Controller**
  - `dashboard_view.render_file_uploader()` retorna os arquivos para `app.main`.
  - Após seleção e filtros, a View solicita novos dados e espera um `DashboardPayload`.
- **Controller → Models**
  - `load_datasets()` usa `csv_loader.load_csv` para criar `CSVData`.
  - `build_cost_dataset()` garante que o DataFrame resultante esteja normalizado antes de aplicar regras de negócio.
  - Funções como `aggregate_service_totals`, `calculate_overall_metrics`, `build_rankings` e `aggregate_monthly_totals` são invocadas para preencher o payload.
- **Controller ↔ View**
  - O controller devolve mensagens (erros de upload, avisos de filtro) que a View exibe com `st.warning`.
  - A View envia filtros (datas, serviços, coluna de gráfico) ao controller, que devolve novos dados filtrados.
- **Main (app/main.py)**
  - Atua como orquestrador de ciclo único: recebe entradas da View, passa pelo Controller/Models e injeta o payload de volta para renderização.

## Resumo textual do código

- `main.py`: script mínimo que só chama `app.main.main`.
- `app/main.py`: inicializa Streamlit (`st.set_page_config`), gerencia uploads, filtros e chama as funções do controller; no final passa `DashboardPayload` para a View.
- `app/controllers/data_controller.py`: define `DashboardPayload` (dataclass) e concentra a lógica:
  - `validate_file`, `load_datasets`, `apply_filters`, `prepare_dashboard_payload`.
- `app/models/csv_loader.py`: fornece `load_csv` que tenta múltiplos encodings e devolve `CSVData`.
- `app/models/cost_model.py`: contém constantes de colunas, `CostDataset`, normalização e cálculos auxiliares (totais, percentuais, rankings, estatísticas e destaques mensais).
- `app/views/dashboard_view.py`: implementa funções `render_*` que constroem sidebar, cards de métricas, tabelas e gráficos Altair, consumindo `DashboardPayload`.

Essa organização preserva a separação de responsabilidades: Models conhecem dados, Controller conhece a lógica de negócio e a View apenas apresenta/solicita ações, mantendo o dashboard escalável e fácil de evoluir.

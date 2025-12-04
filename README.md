# Projeto Fatura AWS

Dashboard Streamlit (SPA) que lê faturas AWS no formato CSV, normaliza as 54 colunas previstas e apresenta análises de custos por serviço em uma interface única.

## Stack e bibliotecas

- **uv** – CLI moderna para criar/rodar ambientes virtuais e executar o Streamlit com as dependências corretas (`uv run ...`).
- **Streamlit** – framework web reativo responsável por toda a UI, sidebar, inputs e renderização das tabelas.
- **Pandas** – processamento de dados: leitura dos CSVs, normalização das 54 colunas e cálculos estatísticos utilizados nas métricas.
- **Altair** – motor de visualização declarativa para montar os gráficos de barras, pizza/donut e séries temporais.

## Pré-requisitos

- Python 3.13+ (o projeto foi criado com `pyenv` e virtualenv `multi-clout`, mas qualquer ambiente compatível funciona).
- Dependências listadas em `requirements.txt` ou `pyproject.toml`.

## Instalação

```bash
pyenv activate multi-clout   # opcional, use seu ambiente preferido
pip install -r requirements.txt
```

## Execução local

```bash
uv run streamlit run main.py
```

## Estrutura do projeto

```
├── main.py                 # Entry point (streamlit run main.py)
├── app/
│   ├── main.py             # Configura a página e orquestra upload/filtros
│   ├── controllers/
│   │   └── data_controller.py   # Valida arquivos, aplica filtros e monta o payload
│   ├── models/
│   │   ├── cost_model.py        # Normalização dos 54 campos e cálculos estatísticos
│   │   └── csv_loader.py        # Carregamento seguro dos CSVs e tratamento de erros
│   └── views/
│       └── dashboard_view.py    # Componentes de UI (sidebar, tabelas, gráficos)
├── assets/                 # Logos/temas opcionais
├── data/                   # Área para armazenar CSVs locais
├── requirements.txt
└── pyproject.toml
```

## Como o dashboard funciona

1. **Upload & validação**: o usuário envia um ou mais CSVs pela sidebar; `data_controller.validate_file` garante que sejam CSVs válidos e acusa arquivos vazios.
2. **Carga & normalização**: `csv_loader.load_csv` lê o arquivo (testando múltiplos encodings) e `cost_model.normalize_cost_dataframe` garante que todas as 54 colunas existam, convertendo números e interpretando `Serviço` como data para filtros.
3. **Aplicação de filtros**: o usuário seleciona serviços, período (quando `Serviço` contém datas válidas) e a coluna que alimentará os gráficos. O controller fatia o DataFrame apenas com as colunas relevantes.
4. **Construção do payload**: métricas agregadas, percentuais, rankings, estatísticas e totais mensais são calculados e empacotados em `DashboardPayload`.
5. **Renderização**: `dashboard_view` exibe cards de resumo, tabelas dinâmicas e gráficos Altair (ranking, distribuição percentual e linha temporal) além dos avisos/contextos necessários.

Qualquer mudança na seleção de arquivo ou filtros reexecuta o script Streamlit, reconstruindo todas as seções em tempo real.

## Funcionalidades principais

- Upload múltiplo de CSVs com seleção do dataset ativo.
- Conversão automática das colunas numéricas e interpretação opcional do campo `Serviço` como data.
- Filtros de período, serviços analisados e coluna base dos gráficos.
- Resumo com métricas agregadas, destaques (maiores/menores serviços e meses), estatísticas, ranking e distribuição percentual.
- Gráficos Altair (barras, pizza/donut e linha mensal) e preview tabular dos dados filtrados.
- Mensagens amigáveis para arquivos inválidos, falhas de parsing e filtros sem resultados.
# projeto-finops

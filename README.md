# FinOps Multi-Cloud AI Dashboard

Dashboard interativo em Streamlit para análise e otimização de custos em ambientes multi-cloud, com suporte a insights, previsões, detecção de anomalias e recomendações automatizadas apoiadas por IA.

## 1. Visão Geral da Arquitetura

### Objetivo do Sistema

Uma SPA (Single Page Application) em Streamlit para FinOps que:

- **Lê dados de custos** (ex.: faturas AWS) e/ou base local `finops.db`
- **Normaliza, persiste e analisa** custos de forma automatizada
- **Gera insights, previsões, detecção de anomalias e recomendações**, apoiados por LLM e por lógica estatística própria
- **Exibe tudo numa UI única** com painéis temáticos (anomaly, forecast, insights, recommendations, chat)

## 2. Arquitetura em Camadas

### 2.1. Camada de Apresentação (UI / Front)

**Pasta:** `app/ui`

**Arquivos principais:**

- `layout.py` – define a estrutura da página (layouts, colunas, seções)
- `filters_sidebar.py` – filtros globais (datas, serviço, tags, etc.)
- `kpi_cards.py` – cards de KPIs de custos, totais, médias, etc.
- `charts.py` – componentes gráficos (barras, linhas, pizza, etc.)
- `anomaly_panel.py` – painel de detecção de anomalias
- `forecast_panel.py` – painel de previsões de custos
- `insights_panel.py` – painel de insights gerados por IA
- `recommendation_panel.py` – painel de recomendações de otimização
- `chat_panel.py` – interface de chat FinOps com IA

**Responsabilidade:**

Renderizar a interface Streamlit, reagir aos filtros e chamar os serviços corretos para obter dados e resultados.

### 2.2. Camada de Orquestração / Aplicação

**Pontos de entrada:**

- `main.py` (raiz) – entrypoint chamado pelo `streamlit run main.py`
- `app/main.py` – script principal da app:
  - configura página,
  - integra sidebar, painéis, KPI cards,
  - orquestra chamadas aos serviços

**Configuração:**

- `app/config.py` – parâmetros de app (paths, flags de debug, parâmetros de cache, chaves de serviços, etc.)

**Responsabilidade:**

Coordenar o fluxo: leitura de filtros → chamada de serviços → dados para UI, sem embutir regra de negócio "pesada".

### 2.3. Camada de Serviços (Regras de Negócio & Use Cases)

**Pasta:** `app/services`

**Arquivos:**

- `analytics_service.py` – agregações, métricas, rankings, breakdown por serviço/região/etc.
- `anomaly_service.py` – detecção de anomalias de custo
- `forecast_service.py` – previsões de custo (ex.: séries temporais)
- `insights_service.py` – geração de insights explicativos (ex.: "o custo subiu por causa de X")
- `recommendation_service.py` – recomendações de otimização (reservados, redução de recursos, etc.)
- `chat_service.py` – interface de chat FinOps (via LLM) para responder perguntas sobre custos

**Responsabilidade:**

Implementar os casos de uso da aplicação, combinando:
- dados dos modelos/repos (`app/models`, `app/data`),
- recursos de infraestrutura (`app/infra`),
- e retornando objetos prontos para a camada de UI.

### 2.4. Camada de Domínio & Acesso a Dados

#### 2.4.1. Domínio (Modelos)

**Pasta:** `app/models`

- `cost_model.py` – entidades e lógica de custos (normalização, métricas, etc.)
- `csv_loader.py` – leitura/parse de arquivos CSV com dados brutos (faturas, relatórios)
- `db.py` – abstração de acesso ao banco (ex.: conexão SQLite, queries básicas/ORM leve)

**Responsabilidade:**

Representar o modelo de domínio FinOps e encapsular:
- estrutura dos dados de custo,
- transformação/normalização,
- regras centrais de cálculo.

#### 2.4.2. Data Layer (Repos & Loaders)

**Pasta:** `app/data`

- `loaders.py` – funções de carregamento de dados (de CSV, DB, etc.)
- `schemas.py` – dataclasses/estruturas para Data Layer (ex.: DTOs)
- `repositories.py` – repositórios para consulta/persistência (ex.: CostRepository, AnomalyRepository…)

**Banco local:**

- `data/finops.db` – base SQLite com dados de custos já processados ou consolidados

**Responsabilidade:**

Fornecer uma interface limpa aos dados, escondendo detalhes de:
- onde os dados estão (CSV, DB),
- como são carregados ou persistidos.

### 2.5. Camada de Infraestrutura / Cross-Cutting

**Pasta:** `app/infra`

- `cache.py` – mecanismos de cache (ex.: cache em memória, TTL para queries pesadas)
- `llm_client.py` – cliente central para comunicação com LLM (OpenAI, Groq, etc.)
- `logging_config.py` – configuração de logging estruturado

**Responsabilidade:**

Serviços transversais, usados pela camada de serviços e, eventualmente, pela de domínio:
- Evitar recomputar análises pesadas
- Expor uma interface única de LLM para chat/insights/recomendações
- Padronizar logs (útil para observabilidade e troubleshooting)

### 2.6. Testes e Artefatos de Projeto

- `tests/` – testes unitários e/ou de integração
- `assets/` – logos, ícones, temas visuais
- `projeto.md` – documentação mais detalhada de requisitos/roadmap
- `pyproject.toml`, `requirements.txt`, `uv.lock` – gestão de dependências e ambiente

## 3. Fluxo Lógico (de Ponta a Ponta)

### Usuário acessa o dashboard

`streamlit run main.py` → `main.py` (raiz) delega para `app/main.py`

### Configuração e Layout

`app/main.py`:
- configura tema, página,
- monta sidebar (`filters_sidebar.py`),
- exibe KPI cards (`kpi_cards.py`),
- exibe painéis (`*_panel.py`)

### Usuário define filtros / faz upload / interage com chat

A UI chama funções da camada de serviços, por exemplo:
- `analytics_service.get_summary(...)`
- `anomaly_service.detect_anomalies(...)`
- `chat_service.ask_question(...)`

### Serviços consultam dados e infra

- Repositórios em `app/data/repositories.py` + `app/models/db.py` lêem de `finops.db` ou de CSV via `csv_loader.py`/`loaders.py`
- `cost_model.py` aplica regras de domínio
- `infra/cache.py` guarda resultados reutilizáveis
- `infra/llm_client.py` conversa com o LLM quando necessário (chat, insights, recomendações)

### Resposta volta para UI

Dados são transformados em DataFrames, KPIs, séries para gráficos. `charts.py`, `kpi_cards.py` e os panels renderizam o resultado no Streamlit.

## 4. Mapa Rápido: Pasta → Camada

| Pasta/Arquivo | Papel Arquitetural |
|---------------|-------------------|
| `main.py` (raiz) | Entry point da aplicação Streamlit |
| `app/main.py` | Orquestração da UI e fluxo de página |
| `app/config.py` | Configuração da aplicação |
| `app/ui/*` | Camada de apresentação (front/Streamlit) |
| `app/services/*` | Casos de uso / serviços de negócio |
| `app/models/*` | Domínio (modelos + lógica de custo) |
| `app/data/*` | Acesso a dados (loaders, repos, DTOs) |
| `app/infra/*` | Infraestrutura (cache, LLM, logging) |
| `data/finops.db` | Banco de dados (SQLite) |
| `tests/` | Testes |
| `assets/` | Recursos estáticos (imagens, temas) |

## 5. Stack Tecnológica

- **Python 3.13+** – Linguagem principal
- **Streamlit** – Framework web para UI
- **Pandas** – Manipulação e análise de dados
- **SQLite** – Banco de dados local (via SQLAlchemy)
- **Plotly** – Gráficos interativos
- **OpenAI API** – LLM para insights e chat
- **Prophet** – Previsão de séries temporais
- **Scikit-learn** – Detecção de anomalias
- **Pydantic** – Validação de dados e modelos

## 6. Pré-requisitos

- Python 3.13+
- Dependências listadas em `requirements.txt` ou `pyproject.toml`

## 7. Instalação

```bash
# Criar ambiente virtual (recomendado)
python -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env e adicionar sua OPENAI_API_KEY
```

## 8. Execução

```bash
streamlit run main.py
```

A aplicação estará disponível em `http://localhost:8501`

## 8.1. Execução com Docker Compose

```bash
# 1) (Opcional) Crie o .env na raiz do projeto
cp .env.example .env

# 2) Suba o serviço
docker compose up --build
```

A aplicação estará disponível em `http://localhost:8501` e o SQLite ficará persistido em `./data`.

## 9. Funcionalidades Principais

### 9.1. Upload e Importação
- Upload de arquivos CSV com dados de custos
- Armazenamento automático em SQLite
- Normalização automática de dados

### 9.2. Análise e Visualização
- **KPIs**: Total, média, máximo, mínimo de custos
- **Ranking de Custos**: Serviços ordenados por maior gasto
- **Distribuição Percentual**: Participação relativa dos serviços
- **Evolução Mensal**: Séries temporais de custos
- **Total Gasto por Mês**: Gráfico empilhado com composição detalhada

### 9.3. Inteligência Artificial
- **Insights Automáticos**: Análises explicativas geradas por LLM
- **Previsões**: Forecast de custos futuros usando regressão linear
- **Detecção de Anomalias**: Identificação de custos atípicos
- **Recomendações**: Sugestões de otimização baseadas em IA
- **Chat FinOps**: Interface de linguagem natural para consultas sobre custos

### 9.4. Filtros e Interatividade
- Filtro por período (datas)
- Filtro por serviços
- Seleção de coluna para gráficos
- Visualização focada ou global

## 10. Estrutura de Diretórios

```
projeto-fatura-aws/
├── main.py                 # Entry point
├── app/
│   ├── main.py            # Orquestração principal
│   ├── config.py          # Configurações
│   ├── ui/                # Camada de apresentação
│   │   ├── layout.py
│   │   ├── filters_sidebar.py
│   │   ├── kpi_cards.py
│   │   ├── charts.py
│   │   └── *_panel.py
│   ├── services/          # Casos de uso
│   │   ├── analytics_service.py
│   │   ├── anomaly_service.py
│   │   ├── forecast_service.py
│   │   ├── insights_service.py
│   │   ├── recommendation_service.py
│   │   └── chat_service.py
│   ├── models/            # Domínio
│   │   ├── cost_model.py
│   │   ├── csv_loader.py
│   │   └── db.py
│   ├── data/              # Acesso a dados
│   │   ├── loaders.py
│   │   ├── schemas.py
│   │   └── repositories.py
│   └── infra/             # Infraestrutura
│       ├── cache.py
│       ├── llm_client.py
│       └── logging_config.py
├── data/
│   └── finops.db          # Banco SQLite
├── tests/                 # Testes
├── assets/                # Recursos estáticos
├── requirements.txt
├── pyproject.toml
└── README.md
```

## 11. Configuração

### Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
# OpenAI / LLM Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini

# Cache Configuration
ENABLE_CACHE=true
CACHE_TTL=3600

# Logging
LOG_LEVEL=INFO
```

No Docker Compose, o arquivo `.env` é carregado automaticamente via `env_file` no `docker-compose.yml`.

## 12. Contribuindo

1. Faça fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 13. Licença

Este projeto é de uso interno da organização.

## 14. Contato

Para dúvidas ou sugestões, entre em contato com a equipe de desenvolvimento.

## 15. Deploy com Docker

- Imagem Docker: use o `Dockerfile` na raiz (`docker build -t finops-dashboard:latest .`).
- Manifests para EKS em `deploy/eks/` (`kubectl apply -k deploy/eks`); atualize a imagem no `deployment.yaml` com o endereço do ECR.
- Crie o Secret `finops-secrets` com `OPENAI_API_KEY` e monte um volume em `/app/data` (PVC `finops-data`) para persistir `finops.db` e uploads.

# VetGlobal - Asynchronous Document Processing API

API assincrona para ingestao, processamento e sumarizacao de prontuarios e documentos clinicos veterinarios, construida com FastAPI, SQLAlchemy 2.0, PostgreSQL 16 e Alembic.

---

## 1. Stack Tecnologica

- **Linguagem**: Python 3.11+
- **Framework Web**: FastAPI
- **ORM / Conector de Banco**: SQLAlchemy 2.0 (modo assincrono) + `asyncpg`
- **Banco de Dados**: PostgreSQL 16
- **Gerenciador de Migracoes**: Alembic (suporte assincrono)
- **Validacao e Tipagem**: Pydantic v2 + Pydantic Settings
- **Containers**: Docker e Docker Compose
- **Testes e Cobertura**: pytest, pytest-asyncio, httpx, pytest-cov (74 testes, 96% de cobertura)

---

## 2. Assumptions (Premissas)

- Um pet e identificado atualmente por um ID no banco de dados.
- Autenticacao e isolamento entre tenants estao fora do escopo deste exercicio.
- Apenas documentos `.txt` e `.pdf` sao aceitos.
- O tamanho maximo de um documento e de 20 MB.
- Um documento pode ser processado apenas uma vez no fluxo atual.
- Documentos com o mesmo conteudo para o mesmo pet sao rejeitados.
- A conclusao de um job so e permitida enquanto ele estiver com status `ENQUEUED`.
- O endpoint de polling retorna `204 No Content` quando o tempo limite configurado e atingido sem que o processamento seja concluido.

---

## 3. Design Decisions e Racional Tecnico (Por que tomei essas decisoes)

### 3.1. Hashing SHA-256 em Streaming (64KB) & Memoria Constante O(1)

- **Motivacao**: Evitar esgotamento de memoria RAM (Denial of Service - DoS) quando multiplos clientes realizam upload simultaneo de arquivos grandes (ate 20MB).
- **Decisao**: O arquivo e lido em blocos de 64KB (`aiofiles` / `UploadFile.read(CHUNK_SIZE)`), calculando o hash SHA-256 incrementalmente enquanto grava no storage.
- **Racional Tecnico**: O consumo de memoria do container permanece fixo em poucos kilobytes por requisicao, independentemente do tamanho do arquivo ou do volume de concorrencia.

### 3.2. Ports & Adapters para Storage (Arquitetura Hexagonal)

- **Motivacao**: Isolar operacoes de I/O em disco das regras de negocio e viabilizar testes unitarios rapidos e deterministicos.
- **Decisao**: Criacao do protocolo abstrato `StorageProvider` (`app/core/storage.py`) com duas implementacoes:
  - `LocalStorageProvider`: Persiste arquivos no volume local (`./storage/uploads`), utilizando `uuid.uuid4().hex` no nome temporario para eliminar qualquer colisao de I/O em disco entre uploads concorrentes.
  - `InMemoryStorageProvider`: Persistencia em memoria (`memory://`) para testes unitarios, executando centenas de testes em milissegundos sem tocar no sistema de arquivos do SO.
- **Racional Tecnico**: Permite plugar adaptadores de nuvem (`S3StorageProvider`, `GCSStorageProvider`) alterando apenas a injecao de dependencias no FastAPI, sem modificar o `DocumentService`.

### 3.3. Consistencia Transacional e Prevencao de Concorrencia TOCTOU

- **Motivacao**: Prevenir condicoes de corrida (*Time-of-Check to Time-of-Use*) em que duas requisicoes simultaneas com o mesmo arquivo tentam registrar o mesmo documento para o mesmo pet.
- **Decisao**:
  - Restricao de unicidade composta no PostgreSQL: `UniqueConstraint('pet_id', 'file_hash', name='uq_pet_document_hash')`.
  - Tratamento atomico de `IntegrityError` na camada de servico: Caso ocorra colisao concorrente no `flush/commit`, o sistema executa `rollback()`, deleta o arquivo temporario gravado e lanca `DuplicateDocumentException` (`409 Conflict`).
- **Racional Tecnico**: A garantia de deduplicacao nao depende exclusivamente de checagens na aplicacao, sendo forcada atomicamente pelo proprio banco de dados relacional.

### 3.4. Idempotencia Estrita no Callback do Worker (HTTP 409 Conflict)

- **Motivacao**: Workers distribuidos de IA/OCR operam com semantica *at-least-once*, podendo reenviar mensagens de conclusao em caso de retentativas de rede.
- **Decisao**: O endpoint `POST /internal/jobs/{job_id}/complete` so aceita finalizar jobs que estejam estritamente em `ENQUEUED`. Tentativas de finalizar jobs em `DONE` ou `FAILED` sao rejeitadas imediatamente com `HTTP 409 Conflict`.
- **Racional Tecnico**: Evita sobrescrita de resumos clinicos validos e protege os timestamps originais de auditoria medica (`completed_at`).

### 3.5. Long Polling Assincrono com Reset Transacional e Cancelamento Ativo

- **Motivacao**: Manter clientes atualizados em tempo real com baixo acoplamento e sem prender threads ou conexoes no PostgreSQL.
- **Decisao**:
  - `asyncio.sleep` no loop de polling de ate 25 segundos.
  - Invocacao de `session.rollback()` antes de cada repouso assincrono, liberando a conexao transacional no pool do PostgreSQL para outras requisicoes.
  - Monitoramento de `request.is_disconnected` para abortar o polling imediatamente se o usuario fechar a aba ou cancelar a requisicao.
- **Racional Tecnico**: Garante alta densidade de conexoes simultaneas por processo sem esgotar o pool do PostgreSQL (*idle in transaction*).

### 3.6. Observabilidade com Correlation ID (`X-Request-ID`)

- **Motivacao**: Rastreabilidade distribuida de ponta a ponta entre requisicoes do cliente, processamento da API e callbacks de workers.
- **Decisao**: Adocao do middleware `RequestIDMiddleware` no FastAPI, capturando ou gerando um UUID unico injetado nos headers `X-Request-ID` de todas as respostas HTTP.
- **Racional Tecnico**: Permite correlacionar logs de requisicoes de upload, polling e callbacks de worker em ferramentas de agregacao de logs (Datadog, Loki, CloudWatch).

---

## 4. Analise Aprofundada de Trade-offs e Alternativas Descartadas

### 4.1. Long Polling vs. WebSockets vs. Server-Sent Events (SSE)

| Criterio | Long Polling (Adotado) | Server-Sent Events (SSE) | WebSockets |
| :--- | :--- | :--- | :--- |
| **Complexidade de Infra** | Baixa (Stateless HTTP padrao) | Media (Conexao HTTP unidirecional mantida) | Alta (Conexao TCP persistente bidirecional) |
| **Compatibilidade com Proxies/CDNs** | Total (funciona em qualquer proxy/firewall) | Boa (pode sofrer buffering em proxies corporativos) | Regular (exige suporte explicito a upgrade HTTP/WS) |
| **Resiliencia a Reconexao** | Nativa (novo request HTTP a cada ciclo) | Nativa no EventSource | Exige logica customizada de heartbeat/reconnect |

**Racional da Escolha**: Para o fluxo de prontuarios veterinarios (onde o cliente aguarda um unico resultado por documento), o Long Polling oferece a melhor relacao de simplicidade operacional, escalabilidade horizontal e resiliencia.

### 4.2. DB-Backed Job State & Lifecycle Tracking (PostgreSQL) vs. Message Broker Dedicado (RabbitMQ / SQS)

| Criterio | DB-Backed Job State (Adotado) | Message Broker Dedicado |
| :--- | :--- | :--- |
| **Atomicidade (Dual-Write)** | Garantida via ACID: O documento e o estado inicial do job (`ENQUEUED`) sao persistidos na mesma transacao. | Risco de escrita dupla: O arquivo pode ser salvo e a mensagem falhar ao ir para a fila (ou vice-versa). |
| **Complexidade Operacional** | Zero infraestrutura adicional no estagio inicial; rastreabilidade e auditoria nativas na tabela `jobs`. | Exige deploy, monitoramento, clustering, gerenciamento de DLQs e esquemas de serializacao. |
| **Escalabilidade & Orquestracao** | Adequada para o modelo de callback HTTP (`/internal/jobs/{id}/complete`) sem manter consumidores ociosos. | Necessaria para alto throughput de streaming com centenas de workers em loop continuo. |

**Racional da Escolha**: A tabela `jobs` atua como repositório transacional de ciclo de vida e auditoria de estado (*DB-backed Job State & Audit Tracker*), orquestrado de forma desacoplada via endpoint de callback do worker. Isso elimina falhas de *dual-write* e mantem a arquitetura enxuta e defensavel sem adicionar a sobrecarga operacional de um broker externo nesta fase.

### 4.3. Storage Local em Disco vs. Cloud Object Storage (AWS S3 / Azure Blob)

| Criterio | LocalStorageProvider (Adotado) | S3StorageProvider |
| :--- | :--- | :--- |
| **Dependencia Externa** | Nenhuma (execucao 100% autonoma local e em Docker). | Exige credenciais AWS, buckets e conectividade de rede externa. |
| **Custo e Complexidade de Teste** | Custo zero, testavel via `InMemoryStorageProvider`. | Exige LocalStack ou mocks pesados de SDK (boto3/aioboto3). |
| **Facilidade de Evolucao** | O padrao Ports & Adapters permite plugar `S3StorageProvider` sem tocar na regra de negocio. | Padrao para escala de producao multi-regiao. |

**Racional da Escolha**: Manter o ambiente de avaliacao e desenvolvimento rapido e independente, com a arquitetura pronta para nuvem via injecao de dependencias.

---

## 5. Estrategia de Retentativas e Resiliencia (Retry Strategy)

### 5.1. No Cliente HTTP / Frontend

- **Auto-Reconnect com Backoff Exponencial**: Quando o endpoint de polling atinge o timeout de 25s (`204 No Content`), o cliente abre imediatamente o ciclo seguinte sem interrupcao de UI.
- **Tratamento de Falhas Transitorias de Rede**: Em caso de erro de rede temporario (`5xx` ou perda de pacote), o cliente aguarda com backoff exponencial incremental (1s, 2s, 4s, ate 16s) com jitter aleatorio para prevenir tempestades de requisicoes (*Thundering Herd Problem*).

### 5.2. Nos Workers Assincronos

- **Isolamento de Falhas e Dead Letter Queue (DLQ)**:
  - Jobs que falham durante a extracao de OCR ou sumarizacao transmitem status `FAILED` com a descricao do erro via `POST /internal/jobs/{id}/complete`.
  - O sistema registra `error_message` e encerra o ciclo de vida do job, permitindo analise posterior sem reter o documento em processamento infinito.

---

## 6. Out of Scope (Escopo Intencionalmente Incompleto)

Os seguintes itens foram deliberadamente mantidos fora do escopo inicial para preservar a simplicidade, foco e coesao do desafio:

1. **Pipeline Real de IA/OCR**: O processamento pesado por LLM ou OCR e simulado via endpoint interno de callback, desacoplando a ingestao REST do worker de computacao.
2. **Autenticacao, Autorizacao e Multi-Tenancy**: Ausencia de tokens JWT/OAuth2 e segregacao por clinica (`tenant_id`), simplificando a avaliacao do core do processamento.
3. **Provedor Gerenciado de Object Storage (AWS S3)**: Persistencia padrao mantida localmente, desenhada para receber adaptadores S3/Blob como extensao futura.
4. **Metricas Prometheus e Rastreamento Distribuido (OpenTelemetry)**: Observabilidade coberta por logging estruturado, middleware `X-Request-ID` e endpoint `/health`.

---

## 7. Estrutura de Diretorios

```text
VetGlobal/
├── .github/
│   └── workflows/
│       └── ci.yml                # Pipeline de CI (testes, migracoes e build Docker)
├── app/
│   ├── core/
│   │   ├── config.py             # Configuracoes com pydantic-settings
│   │   ├── database.py           # Engine assincrono, session maker e DeclarativeBase
│   │   ├── exceptions.py         # Excecoes de dominio desacopladas do transporte HTTP
│   │   └── storage.py            # Ports & Adapters: StorageProvider (Local & In-Memory)
│   ├── models/
│   │   ├── __init__.py           # Exportacao centralizada dos modelos e Base
│   │   ├── document.py           # Modelo Document com constraint de hash unico
│   │   ├── job.py                # Modelo Job com timestamps e FK para document
│   │   ├── job_status.py         # Enum com os estados do processamento (JobStatus)
│   │   └── pet.py                # Modelo Pet com relacionamento com documents
│   ├── routers/
│   │   ├── documents.py          # Upload, consulta e long polling de documentos
│   │   ├── health.py             # Endpoint de verificacao de saude e banco
│   │   ├── internal.py           # Callback de conclusao do worker de processamento
│   │   └── pets.py               # CRUD de pets
│   ├── schemas/
│   │   ├── document.py           # Schemas de upload e detalhe de documento
│   │   ├── health.py             # Schema de resposta do healthcheck
│   │   ├── job.py                # Schemas de callback do worker e conclusao
│   │   └── pet.py                # Schemas de entrada e saida de Pet
│   ├── services/
│   │   ├── document_service.py   # Logica de ingestao, hashing e consulta
│   │   ├── job_service.py        # Logica de conclusao e idempotencia de jobs
│   │   └── pet_service.py        # Logica de criacao e consulta de pets
│   └── main.py                   # Ponto de entrada FastAPI com middlewares de CORS e X-Request-ID
├── migrations/
│   ├── versions/
│   │   └── 0001_initial_schema.py # Migracao inicial das tabelas pets, documents e jobs
│   ├── env.py                    # Configuracao assincrona do Alembic
│   └── script.py.mako            # Template de geracao de novas revisoes
├── storage/
│   └── uploads/                  # Diretorio local para persistencia de arquivos
├── tests/
│   ├── __init__.py
│   ├── test_concurrency.py       # Testes de race conditions com asyncio.gather e asyncio.create_task
│   ├── test_documents.py         # Testes de upload, consulta e long polling
│   ├── test_e2e.py               # Testes de integracao End-to-End do fluxo completo
│   ├── test_health.py            # Testes do endpoint de healthcheck
│   ├── test_jobs.py              # Testes do callback do worker (DONE/FAILED/409)
│   ├── test_pets.py              # Testes de CRUD de pets (201, 200, 404, 422)
│   └── test_storage.py           # Testes unitarios de LocalStorageProvider e InMemoryStorageProvider
├── .env.example                  # Variaveis de ambiente de referencia
├── alembic.ini                   # Configuracao principal do Alembic
├── Dockerfile                    # Build da imagem da aplicacao
├── docker-compose.yml            # Orquestracao de servicos (API + PostgreSQL)
├── entrypoint.sh                 # Script de inicializacao e execucao de migracoes
├── pyrightconfig.json            # Vinculacao do Language Server a .venv
├── pytest.ini                    # Configuracao do executor de testes pytest
├── README.md                     # Documentacao consolidada do projeto
└── requirements.txt              # Dependencias do projeto
```

---

## 8. Instrucoes de Execucao

### 8.1. Pre-requisitos

- Docker e Docker Compose instalados, OU
- Python 3.11+ e PostgreSQL 16 configurados localmente.

### 8.2. Execucao via Docker Compose (Recomendado)

1. Clonar o repositorio:

   ```bash
   git clone https://github.com/Ja0Santana/VetGlobal.git
   cd VetGlobal
   ```

2. Configurar o arquivo de ambiente:

   ```bash
   cp .env.example .env
   ```

3. Subir os containers da aplicacao e do banco de dados:

   ```bash
   docker-compose up --build
   ```

4. Acessos:
   - **API**: `http://localhost:8000`
   - **Healthcheck**: `http://localhost:8000/health`
   - **Documentacao Interativa (Swagger/OpenAPI)**: `http://localhost:8000/docs`

### 8.3. Execucao Local (Ambiente de Desenvolvimento)

1. Criar e ativar o ambiente virtual:

   ```bash
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\activate
   # Linux / macOS:
   source .venv/bin/activate
   ```

2. Instalar as dependencias:

   ```bash
   pip install -r requirements.txt
   ```

3. Configurar as variaveis de ambiente no arquivo `.env`:

   ```text
   DATABASE_URL=postgresql+asyncpg://vetglobal:vetglobal@localhost:5432/vetglobal
   STORAGE_PATH=./storage/uploads
   ```

4. Executar as migracoes do banco de dados:

   ```bash
   alembic upgrade head
   ```

5. Iniciar o servidor Uvicorn com hot-reload:

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

---

## 9. Instrucoes de Testes e Cobertura de Codigo

Os testes automatizados cobrem testes unitarios, de integracao, de concorrencia/condicoes de corrida e ponta a ponta (E2E) com `pytest`, `pytest-asyncio`, `httpx` e `pytest-cov`:

```bash
# Executar todos os testes com saida detalhada (74 testes)
pytest -v

# Executar testes gerando relatorio de cobertura de codigo (96%+ de cobertura)
pytest -v --cov=app --cov-report=term-missing
```

---

## 10. Endpoints Implementados

### `GET /health`

Verifica a saude da aplicacao e a conectividade com o PostgreSQL executando `SELECT 1`.

- **Resposta (`200 OK`)**:

  ```json
  {
    "status": "healthy"
  }
  ```

- **Resposta (`503 Service Unavailable`)**: Falha na conexao com o banco de dados.

### `POST /pets`

Cadastra um novo pet no sistema.

- **Request Body**:

  ```json
  {
    "name": "Hank",
    "owner_name": "John Bergeson"
  }
  ```

- **Resposta (`201 Created`)**:

  ```json
  {
    "id": 1,
    "name": "Hank",
    "owner_name": "John Bergeson",
    "created_at": "2026-08-18T20:00:00Z"
  }
  ```

### `GET /pets/{pet_id}`

Consulta os dados de um pet por ID.

- **Resposta (`200 OK`)**: Retorna os dados do pet.
- **Resposta (`404 Not Found`)**: Pet nao encontrado.

### `POST /pets/{pet_id}/documents`

Upload de documento (`.txt` ou `.pdf`) vinculado a um pet. Calcula hash SHA-256 em streaming, persiste o arquivo no disco e enfileira um job assincrono de sumarizacao.

- **Form-Data**: `file` (Multipart file)
- **Resposta (`202 Accepted`)**:

  ```json
  {
    "document_id": 10,
    "job_id": 55,
    "status": "ENQUEUED"
  }
  ```

- **Codigos de Erro**:
  - `400 Bad Request`: Extensao invalida ou arquivo vazio.
  - `404 Not Found`: Pet nao encontrado.
  - `409 Conflict`: Documento identico ja enviado para este pet.
  - `413 Content Too Large`: Tamanho do arquivo excede o limite de 20MB.

### `POST /internal/jobs/{job_id}/complete`

Endpoint interno para simular o callback de conclusao de um worker de sumarizacao.

- **Request Body (Sucesso)**:

  ```json
  {
    "status": "DONE",
    "summary": "Patient has a history of intermittent vomiting."
  }
  ```

- **Request Body (Falha)**:

  ```json
  {
    "status": "FAILED",
    "error": "Could not parse document"
  }
  ```

- **Resposta (`200 OK`)**:

  ```json
  {
    "job_id": 55,
    "document_id": 10,
    "status": "DONE",
    "completed_at": "2026-08-18T20:01:00Z"
  }
  ```

- **Codigos de Erro**:
  - `404 Not Found`: Job nao encontrado.
  - `409 Conflict`: Job ja foi finalizado anteriormente (idempotencia).
  - `422 Unprocessable Entity`: Status invalido, summary ausente para status DONE ou error ausente para status FAILED.

### `GET /documents/{document_id}`

Consulta os metadados do documento e as informacoes do job mais recente associado.

- **Resposta (`200 OK`)**:

  ```json
  {
    "id": 10,
    "pet_id": 1,
    "filename": "prontuario.pdf",
    "created_at": "2026-08-18T20:00:00Z",
    "latest_job": {
      "id": 55,
      "status": "DONE",
      "summary": "Patient has a history of intermittent vomiting.",
      "error_message": null,
      "completed_at": "2026-08-18T20:01:00Z"
    }
  }
  ```

### `GET /documents/{document_id}/poll`

Endpoint de Long Polling que segura a conexao HTTP aberta por ate 25 segundos aguardando o processamento assincrono do documento.

- **Query Parameters (Opcionais)**:
  - `after_job_id` (int, default: `0`, min: `0`): Filtra apenas jobs com ID estritamente maior que o valor informado.
  - `timeout` (float, default: `25.0`, min: `1.0`, max: `25.0`): Tempo maximo de espera em segundos.
- **Resposta quando Concluido (`200 OK`)**:

  ```json
  {
    "id": 10,
    "pet_id": 1,
    "filename": "prontuario.pdf",
    "created_at": "2026-08-18T20:00:00Z",
    "latest_job": {
      "id": 55,
      "status": "DONE",
      "summary": "Patient has a history of intermittent vomiting.",
      "error_message": null,
      "completed_at": "2026-08-18T20:01:00Z"
    }
  }
  ```

- **Resposta em Timeout (`204 No Content`)**:
  - Retornado quando o timeout de 25 segundos expira e o documento ainda se encontra em processamento (`ENQUEUED`), indicando ao cliente para realizar um novo poll sem erro de conexao.
- **Codigos de Erro**:
  - `404 Not Found`: Documento nao encontrado.
  - `422 Unprocessable Entity`: ID invalido ou parametro de timeout fora do intervalo permitido.

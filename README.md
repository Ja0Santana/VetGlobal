# VetGlobal - Asynchronous Document Processing API

API assincrona para ingestao, processamento e sumarizacao de prontuarios e documentos clinicos veterinarios, construida com FastAPI, SQLAlchemy 2.0, PostgreSQL 16 e Alembic.

---

## 1. Stack Tecnologica Atual

- **Linguagem**: Python 3.11+
- **Framework Web**: FastAPI
- **ORM / Conector de Banco**: SQLAlchemy 2.0 (modo assincrono) + `asyncpg`
- **Banco de Dados**: PostgreSQL 16
- **Gerenciador de Migracoes**: Alembic (suporte assincrono)
- **Validacao e Tipagem**: Pydantic v2 + Pydantic Settings
- **Containers**: Docker e Docker Compose

---

## 2. Estrutura de Diretorios Atual

```text
VetGlobal/
├── .github/
│   └── workflows/
│       └── ci.yml                # Pipeline de CI (testes, migracoes e build Docker)
├── app/
│   ├── core/
│   │   ├── config.py             # Configuracoes da aplicacao com pydantic-settings
│   │   ├── database.py           # Engine assincrono, session maker e DeclarativeBase
│   │   └── exceptions.py         # Excecoes de dominio desacopladas do transporte HTTP
│   ├── models/
│   │   ├── __init__.py           # Exportacao centralizada dos modelos e Base
│   │   ├── document.py           # Modelo Document com constraint de hash unico
│   │   ├── job.py                # Modelo Job com timestamps e FK para document
│   │   ├── job_status.py         # Enum com os estados do processamento (JobStatus)
│   │   └── pet.py                # Modelo Pet com relacionamento com documents
│   ├── routers/
│   │   ├── documents.py          # Upload e consulta de documentos
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
│   └── main.py                   # Ponto de entrada da aplicacao FastAPI
├── migrations/
│   ├── versions/
│   │   └── 0001_initial_schema.py # Migracao inicial das tabelas pets, documents e jobs
│   ├── env.py                    # Configuracao assincrona do Alembic
│   └── script.py.mako            # Template de geracao de novas revisoes
├── storage/
│   └── uploads/                  # Diretorio local para persistencia de arquivos
├── tests/
│   ├── __init__.py
│   ├── test_documents.py         # Testes de upload e consulta de documentos
│   ├── test_health.py            # Testes do endpoint de healthcheck
│   ├── test_jobs.py              # Testes do callback do worker (DONE/FAILED/409)
│   └── test_pets.py              # Testes de CRUD de pets (201, 200, 404)
├── .env.example                  # Variaveis de ambiente de referencia
├── alembic.ini                   # Configuracao principal do Alembic
├── Dockerfile                    # Build da imagem da aplicacao
├── docker-compose.yml            # Orquestracao de servicos (API + PostgreSQL)
├── entrypoint.sh                 # Script de inicializacao e execucao de migracoes
├── pyrightconfig.json            # Vinculacao do Language Server a .venv
├── pytest.ini                    # Configuracao do executor de testes pytest
├── README.md                     # Documentacao do projeto
└── requirements.txt              # Dependencias do projeto
```

---

## 3. Instrucoes de Execucao

### 3.1. Pre-requisitos
- Docker e Docker Compose instalados, OU
- Python 3.11+ e PostgreSQL 16 configurados localmente.

### 3.2. Execucao via Docker Compose (Recomendado)

1. Clonar o repositorio:
   ```bash
   git clone https://github.com/Ja0Santana/VetGlobal.git
   cd VetGlobal
   ```

2. Configurar o arquivo de ambiente:
   ```bash
   cp .env.example .env
   ```

3. Subir os containers da aplicacao e do banco:
   ```bash
   docker-compose up --build
   ```

4. Acessos:
   - **API**: `http://localhost:8000`
   - **Healthcheck**: `http://localhost:8000/health`
   - **Documentacao Interativa (Swagger/OpenAPI)**: `http://localhost:8000/docs`

### 3.3. Execucao Local (Ambiente de Desenvolvimento)

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

## 4. Instrucoes de Testes

Os testes automatizados utilizam `pytest`, `pytest-asyncio` e `httpx`:

```bash
# Executar todos os testes
pytest

# Executar com saida detalhada
pytest -v
```

---

## 5. Endpoints Implementados

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
- **Codigos de Erro**:
  - `404 Not Found`: Documento nao encontrado.

---

## 6. Modelagem de Dominio e Decisoes de Banco (Fase 2)

### 6.1. Modelos Implementados
- **`Pet` (`pets`)**: Cadastro basico do animal (`name`, `owner_name`, `created_at`).
- **`Document` (`documents`)**: Metadados do arquivo anexado (`pet_id`, `filename`, `file_path`, `file_hash`, `created_at`).
- **`Job` (`jobs`)**: Rastreabilidade do processamento assincrono (`document_id`, `status`, `summary`, `error_message`, `created_at`, `started_at`, `completed_at`, `updated_at`).

### 6.2. Decisoes Tecnicas Adotadas

1. **SQLAlchemy 2.0 Declarative Mapping**:
   - Uso de `Mapped[...]` e `mapped_column(...)`, garantindo tipagem estatica estrita e validacao pelo Pyright/Mypy.

2. **Consistencia de Timestamps (`server_default=func.now()`)**:
   - A geracao de data/hora e delegada ao PostgreSQL, garantindo precisao cronologica uniforme entre multiplas instancias da aplicacao.

3. **Deteccao de Duplicidade em Nivel de Banco**:
   - Restricao de unicidade composta: `UniqueConstraint('pet_id', 'file_hash', name='uq_pet_document_hash')`.
   - Impede o upload redundante do mesmo arquivo para o mesmo pet de forma atomica no banco.

4. **Integridade Referencial: Cascade Delete**:
   - Relacionamentos configurados com `cascade="all, delete-orphan"` e `ondelete="CASCADE"` entre `Pet -> Documents` e `Document -> Jobs`.
   - **Nota para Producao**: Em ambiente corporativo regulado, a exclusao fisica e substituida por **Soft Delete** (`is_deleted: bool`, `deleted_at: datetime`) para preservar historico e atender normas de auditoria medica.

5. **Ciclo de Vida com Enum Tipado**:
   - `JobStatus` definido como Python Enum (`ENQUEUED`, `DONE`, `FAILED`), persistido como `String(20)` no banco para flexibilidade de evolucao sem necessidade de DDLs pesados de tipos ENUM nativos.

6. **Migracoes Versionadas com Alembic**:
   - Criacao do script `0001_initial_schema.py` com suporte a execucao assincrona via `migrations/env.py`.

### 6.3. Decisoes de Ingestao (Fase 3)

1. **Excecoes de Dominio Desacopladas do HTTP**:
   - Services lancam excecoes semanticas (`PetNotFoundException`, `DuplicateDocumentException`, `InvalidFileExtensionException`, `EmptyFileException`) definidas em `app/core/exceptions.py`. Os routers traduzem para HTTP status codes, mantendo a camada de negocio independente do transporte.

2. **Hashing SHA-256 em Streaming**:
   - O arquivo e lido em chunks de 64KB, calculando o hash simultaneamente a gravacao no disco. Memoria constante independente do tamanho do arquivo.

3. **Limpeza de Arquivos Orfaos**:
   - Se a transacao de banco falhar apos a gravacao do arquivo no disco, o arquivo e removido automaticamente antes de propagar a excecao. Evita acumulo de lixo no storage.

4. **Sanitizacao e Validacao Estrita de Entradas**:
   - Sanitizacao automatica com `.strip()` para campos de texto (`name`, `owner_name`) rejeitando strings vazias ou compostas apenas por espacos (`422 Unprocessable Entity`).
   - Validacao de parametros de rota (`pet_id`, `document_id`) com restricao de inteiros positivos (`ge=1`).
   - Protecao contra Path Traversal no upload de documentos via `os.path.basename` e limite maximo de tamanho de arquivo de 20MB (`413 Content Too Large`).

### 6.4. Decisoes de Callback do Worker e Consulta (Fase 4)

1. **Consistencia Estrita de Payload de Callback**:
   - Validacao no Pydantic exigindo `summary` para status `DONE` (e anulando `error`) e `error` para status `FAILED` (e anulando `summary`), prevenindo estados inconsistentes no banco.

2. **Idempotencia com Bloqueio de Transicao**:
   - O endpoint de callback rejeita tentativas de reprocessar jobs que ja sairam de `ENQUEUED` com `409 Conflict`, preservando timestamps de auditoria e evitando sobrescrita concorrente.

3. **Eager Loading com `selectinload`**:
   - Utilizacao explicita de `selectinload(Document.jobs)` na consulta de documentos para evitar o erro `MissingGreenlet` caracteristico de lazy loading em engines assincronos do SQLAlchemy.

4. **Rastreabilidade e Metricas de Duracao**:
   - Inclusao de `document_id` no payload de resposta do callback e garantia do preenchimento de `started_at`, permitindo calcular metricas de duracao do processamento (`completed_at - started_at`).

5. **Isolamento e Seguranca de Rotas Internas**:
   - Em ambiente produtivo corporativo, rotas sob `/internal/*` nao sao expostas na internet publica, ficando isoladas na VPC/rede interna de workers ou protegidas por tokens de autenticacao de servico (mTLS / Shared Secret).

---

## 7. Proximas Etapas (Roadmap)

- **Fase 5**: Endpoint de Long Polling (`GET /documents/{document_id}/poll`) com timeout de 25s e retorno `204 No Content`.
- **Fase 6**: Testes automatizados e integracao de ponta a ponta.


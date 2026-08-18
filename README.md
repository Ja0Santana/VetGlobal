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
├── app/
│   ├── core/
│   │   ├── config.py             # Configuracoes da aplicacao com pydantic-settings
│   │   └── database.py           # Engine assincrono, session maker e DeclarativeBase
│   ├── models/
│   │   ├── __init__.py           # Exportacao centralizada dos modelos e Base
│   │   ├── document.py           # Modelo Document com constraint de hash unico
│   │   ├── job.py                # Modelo Job com timestamps e FK para document
│   │   ├── job_status.py         # Enum com os estados do processamento (JobStatus)
│   │   └── pet.py                # Modelo Pet com relacionamento com documents
│   ├── routers/
│   │   └── health.py             # Endpoint de verificacao de saude e banco
│   ├── schemas/
│   │   └── health.py             # Schema Pydantic de resposta do healthcheck
│   └── main.py                   # Ponto de entrada da aplicacao FastAPI
├── migrations/
│   ├── versions/
│   │   └── 0001_initial_schema.py # Migracao inicial das tabelas pets, documents e jobs
│   ├── env.py                    # Configuracao assincrona do Alembic
│   └── script.py.mako            # Template de geracao de novas revisoes
├── storage/
│   └── uploads/                  # Diretorio local para persistencia de arquivos
├── .env.example                  # Variaveis de ambiente de referencia
├── alembic.ini                   # Configuracao principal do Alembic
├── Dockerfile                    # Build da imagem da aplicacao
├── docker-compose.yml            # Orquestracao de servicos (API + PostgreSQL)
├── pyrightconfig.json            # Vinculacao do Language Server a .venv
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

## 4. Endpoints Implementados

### `GET /health`
Verifica a saude da aplicacao e a conectividade com o PostgreSQL executando `SELECT 1`.

- **Resposta (`200 OK`)**:
  ```json
  {
    "status": "healthy"
  }
  ```
- **Resposta (`503 Service Unavailable`)**: Falha na conexao com o banco de dados.

---

## 5. Modelagem de Dominio e Decisoes de Banco (Fase 2)

### 5.1. Modelos Implementados
- **`Pet` (`pets`)**: Cadastro basico do animal (`name`, `owner_name`, `created_at`).
- **`Document` (`documents`)**: Metadados do arquivo anexado (`pet_id`, `filename`, `file_path`, `file_hash`, `created_at`).
- **`Job` (`jobs`)**: Rastreabilidade do processamento assincrono (`document_id`, `status`, `summary`, `error_message`, `created_at`, `started_at`, `completed_at`, `updated_at`).

### 5.2. Decisoes Tecnicas Adotadas

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

---

## 6. Proximas Etapas (Roadmap)

- **Fase 3**: Endpoints de CRUD de Pets (`POST /pets`) e Upload de Documentos (`POST /pets/{pet_id}/documents`) com calculo de hash SHA-256 em streaming.
- **Fase 4**: Callback de conclusao do worker (`POST /internal/jobs/{job_id}/complete`) e consulta de documento (`GET /documents/{document_id}`).
- **Fase 5**: Endpoint de Long Polling (`GET /documents/{document_id}/poll`) com timeout de 25s e retorno `204 No Content`.
- **Fase 6**: Testes automatizados e integracao de ponta a ponta.

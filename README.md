# Nanobot Agent Console

Fase 13 da fundacao de um app desktop local-first com Tauri + React + TypeScript no frontend e FastAPI no backend local.

## Estrutura

```text
.
├── .editorconfig
├── .gitignore
├── .python-version
├── README.md
├── package.json
├── prettier.config.cjs
├── apps
│   ├── backend
│   │   ├── alembic
│   │   │   └── versions
│   │   ├── alembic.ini
│   │   ├── package.json
│   │   ├── pyproject.toml
│   │   ├── data
│   │   ├── app
│   │   │   ├── __init__.py
│   │   │   ├── api
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py
│   │   │   │   └── routes
│   │   │   │       ├── agent.py
│   │   │   │       ├── health.py
│   │   │   │       ├── sessions.py
│   │   │   │       └── settings.py
│   │   │   ├── core
│   │   │   ├── db
│   │   │   ├── main.py
│   │   │   ├── models
│   │   │   ├── repositories
│   │   │   ├── schemas
│   │   │   └── services
│   │   └── tests
│   │       ├── conftest.py
│   │       └── test_agent_os_endpoints.py
│   └── desktop
│       ├── .env.example
│       ├── eslint.config.js
│       ├── index.html
│       ├── package.json
│       ├── tsconfig.json
│       ├── tsconfig.node.json
│       ├── vite.config.ts
│       ├── src
│       │   ├── App.test.tsx
│       │   ├── App.tsx
│       │   ├── main.tsx
│       │   ├── styles.css
│       │   ├── vite-env.d.ts
│       │   ├── lib
│       │   │   └── backend.ts
│       │   └── test
│       │       └── setup.ts
│       └── src-tauri
│           ├── Cargo.toml
│           ├── build.rs
│           ├── tauri.conf.json
│           ├── capabilities
│           │   └── default.json
│           └── src
│               ├── lib.rs
│               └── main.rs
└── infra
    └── scripts
```

## Decisoes de arquitetura

- `apps/desktop` concentra a shell desktop com Tauri v2 e a UI React.
- `apps/backend` concentra a API local FastAPI, isolada do desktop por HTTP local e persistida em SQLite.
- SQLite e a fonte de verdade do estado do produto; markdown continua apenas editorial.
- Alembic governa o schema e o seed inicial cria o agente principal default e settings basicos.
- O produto expõe uma boundary interna de kernel; o app fala com contratos proprios e o adapter converte isso para o formato consumido pelo Nanobot.
- O desktop agora expõe a experiencia basica de chat com sessoes persistentes carregadas do SQLite.
- O painel do agente edita `name`, `description`, `identity`, `soul`, `user context`, `policy base` e `default model` diretamente no SQLite.
- O sistema agora inclui um registry de tools locais com permissoes `deny / ask / allow`, restricao de workspace e trilha persistida de `tool_calls`.
- O fluxo de approvals agora pausa execucoes sensiveis em `awaiting_approval`, persiste o estado no SQLite e permite aprovar ou negar depois pelo desktop.
- O backend agora inclui um scheduler local leve com `cron_jobs`, `task_runs` duraveis e heartbeat util para limpeza e resumo operacional.
- A timeline de atividade agrega mensagens, `task_runs`, `tool_calls`, approvals, status final e erros em uma visao de produto voltada para debug operacional.
- O payload agregado de timeline separa duas camadas: `entries` para a narrativa operacional e `audit_log` para o rastro bruto de auditoria.
- Os settings operacionais agora guardam provider/modelo, workspace, budgets e preferencias em SQLite, enquanto segredos ficam fora do banco via keychain do sistema.
- O desktop agora e preparado para distribuicao local com Tauri bundle e backend sidecar empacotado.
- O backend sidecar cria SQLite, logs e artefatos em diretorios nativos do sistema operacional.
- O backend agora adiciona `request_id`, logging minimo de requests e respostas JSON de erro mais uteis para suporte.
- O sistema agora inclui Skills v1 com descoberta em filesystem, precedencia `workspace > user-local > bundled`, gating por contexto e configuracao segura por skill.
- A documentacao tecnica objetiva fica em `docs/architecture.md` e `docs/technical-roadmap.md`.
- O contrato atual inclui `GET /health`, `GET /agent`, `GET /agent/config`, `PUT /agent/config`, `POST /agent/config/reset`, `GET /sessions`, `POST /sessions`, `GET /sessions/{id}`, `GET /sessions/{id}/messages`, `POST /sessions/{id}/messages`, `GET /tools/permissions`, `PUT /tools/permissions/{tool_name}`, `GET /tools/calls`, `GET /skills`, `PUT /skills/{skill_key}`, `GET /approvals`, `GET /approvals/{approval_id}`, `POST /approvals/{approval_id}/approve`, `POST /approvals/{approval_id}/deny`, `GET /cron-jobs`, `POST /cron-jobs`, `PATCH /cron-jobs/{job_id}`, `POST /cron-jobs/{job_id}/pause`, `POST /cron-jobs/{job_id}/activate`, `DELETE /cron-jobs/{job_id}`, `GET /activity/timeline`, `GET /settings`, `GET /settings/operational`, `PUT /settings/operational` e `POST /agent/execute`.
- `apps/backend/package.json` existe apenas para integrar o workspace npm raiz; a implementacao continua Python-first.

## Pre-requisitos

- Node.js 25+ ou uma LTS recente compativel com Vite 7
- Rust toolchain
- `uv`
- Dependencias nativas do Tauri para seu sistema:
  - macOS: Xcode Command Line Tools
  - Windows: Microsoft C++ Build Tools e WebView2

## Setup

```bash
npm install

cd apps/backend
uv python install 3.11
uv sync
npm run migrate
npm run seed
cd ../..
```

Crie o arquivo de ambiente do desktop a partir do exemplo, se quiser sobrescrever o endpoint:

```bash
cp apps/desktop/.env.example apps/desktop/.env
```

## Como rodar

Subir tudo:

```bash
npm run dev
```

Subir apenas o backend:

```bash
npm run dev:backend
```

Subir apenas o desktop:

```bash
npm run dev:desktop
```

Validacoes basicas:

```bash
npm run lint
npm run test
```

## Distribuicao local

Gerar o sidecar do backend e o bundle do desktop para o sistema operacional atual:

```bash
npm run dist
```

Scripts relevantes:

```bash
npm run build:backend:sidecar
npm run build:desktop:bundle
```

Documentacao complementar:

- `docs/architecture.md`
- `docs/memory-v1-operations.md`
- `docs/streaming-terminal-operations.md`
- `docs/distribution.md`
- `docs/release-checklist.md`
- `docs/skills-spec-v1.md`
- `docs/technical-roadmap.md`

## Contrato inicial

`GET /health`

`GET /agent`

`GET /agent/config`

`PUT /agent/config`

`POST /agent/config/reset`

`GET /sessions`

`POST /sessions`

`GET /sessions/{id}`

`GET /sessions/{id}/messages`

`POST /sessions/{id}/messages`

`POST /sessions/{id}/messages/async`

`GET /sessions/{id}/events`

`GET /tools/permissions`

`PUT /tools/permissions/{tool_name}`

`GET /tools/calls`

`GET /skills`

`PUT /skills/{skill_key}`

`GET /approvals`

`GET /approvals/{approval_id}`

`POST /approvals/{approval_id}/approve`

`POST /approvals/{approval_id}/deny`

`GET /cron-jobs`

`POST /cron-jobs`

`PATCH /cron-jobs/{job_id}`

`POST /cron-jobs/{job_id}/pause`

`POST /cron-jobs/{job_id}/activate`

`DELETE /cron-jobs/{job_id}`

`GET /activity/timeline`

`GET /settings`

`GET /settings/operational`

`PUT /settings/operational`

`POST /agent/execute`

Resposta esperada:

```json
{
  "status": "ok",
  "service": "backend",
  "version": "0.1.0"
}
```

## Limites desta fase

- O adapter usa o Nanobot pela camada de provider, mas o loop do produto continua interno e SQLite-first
- Sem gerenciamento do processo Python pelo Tauri empacotado
- A aprovacao retoma apenas o passo pausado de tool call; nao ha paralelismo nem fila de execucao distribuida
- O scheduler usa polling local simples, sem distribuicao nem lock cross-process
- Os jobs do MVP executam tipos internos de manutencao e resumo; nao ha ainda DSL rica nem multi-step workflows
- A timeline e uma projecao agregada sobre `messages`, `task_runs`, `tool_calls`, `approvals` e `audit_events`; ela nao substitui o audit log canonico
- O payload de timeline ainda nao tem filtros avancados, exportacao nem paginação por cursor
- Budget enforcement e aproximado e usa estimativa heuristica quando o provider nao expõe custo real
- Em desenvolvimento e testes, o backend pode usar um secret store em memoria; em uso normal, a meta e keychain do sistema
- O bundle atual ainda usa porta local fixa para o backend sidecar
- Assinatura, notarizacao, updater e cross-compilation ainda nao foram configurados
- O streaming atual e baseado em eventos persistidos por sessao; nao ha token streaming nem multiplexacao dedicada por run
- O runtime de terminal atual expoe `shell_exec` com resultado estruturado; nao ha PTY interativo nem sessao shell persistente

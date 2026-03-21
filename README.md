# Nanobot Agent Console (Forkclaw)

Monorepo local-first para operacao de agentes em desktop.

- Desktop: Tauri v2 + React + TypeScript
- Backend local: FastAPI + SQLite
- Runtime: sessoes principais, subagentes, approvals, tools com politica, scheduler/heartbeat e ACP bridge (v1)

## Estrutura atual

```text
.
├── apps
│   ├── backend
│   │   ├── app
│   │   │   ├── adapters
│   │   │   ├── api
│   │   │   ├── core
│   │   │   ├── db
│   │   │   ├── entrypoints
│   │   │   ├── kernel
│   │   │   ├── models
│   │   │   ├── repositories
│   │   │   ├── schemas
│   │   │   ├── services
│   │   │   ├── tools
│   │   │   └── main.py
│   │   ├── alembic
│   │   └── tests
│   └── desktop
│       ├── src
│       └── src-tauri
├── docs
├── infra
│   └── scripts
└── shared
```

## Arquitetura (estado atual)

### 1) Desktop shell

- App Tauri gerencia UI React e, no bundle, sobe o backend sidecar local.
- Sidecar eh iniciado com diretorios nativos do SO para dados, logs, artefatos e workspace.
- O frontend conversa com backend por HTTP local.

### 2) Backend local

- SQLite como fonte de verdade de estado operacional.
- Alembic como controle de schema/migracoes.
- Camadas principais:
  - `api/routes`: endpoints HTTP
  - `services`: regra de negocio
  - `repositories`: acesso a dados
  - `kernel/adapters`: execucao do agente e integracao com providers

### 3) Execucao de agente

- Fluxo principal em `AgentExecutionService` com persistencia de `tasks`, `task_runs`, `messages`, `audit_events`.
- Loop do kernel suporta encadeamento de multiplos tool-calls no mesmo turno ate `max_iterations`.
- Tool outcomes, approvals e timeline operacional ficam persistidos para replay/debug.

### 4) Tools e politica

- Catalogo de tools com grupos e niveis `deny | ask | allow`.
- `shell_exec` em modo irrestrito por default (`runtime.shell_exec_policy_mode=unrestricted`), com timeout/output limits e auditoria.
- `shell_exec` executa em shell de login (`$SHELL -lc`), com fallback seguro.

### 5) Subagentes

- Runtime nativo de subagente com sessoes filhas, lifecycle e cancelamento.
- `spawn_subagent` suporta `runtime="subagent"` e `runtime="acp"`.

### 6) ACP bridge (v1 pragmatica)

- Bridge stdio em `app/entrypoints/acp_bridge.py`.
- Metodos: `initialize`, `newSession`, `listSessions`, `loadSession`, `prompt`, `cancel`.
- Sessao ACP mapeada/persistida em `acp_sessions`.
- Feature flag: `features.acp_bridge_enabled`.
- Controle administrativo por tools: `acp_enable`, `acp_disable`, `acp_status`.

## Setup rapido

### Pre-requisitos

- Node.js (LTS recomendada)
- Rust toolchain
- `uv`
- Dependencias nativas do Tauri

### Instalar dependencias

```bash
npm install

cd apps/backend
uv python install 3.11
uv sync
npm run migrate
npm run seed
cd ../..
```

### Rodar em desenvolvimento

```bash
npm run dev
```

Atalhos:

```bash
npm run dev:backend
npm run dev:desktop
```

## Build e distribuicao local

Build completo (sidecar + bundle desktop):

```bash
npm run dist
```

Comandos separados:

```bash
npm run build:backend:sidecar
npm run build:desktop:bundle
```

Output esperado (macOS):

- `.app`: `apps/desktop/src-tauri/target/release/bundle/macos/`
- `.dmg`: `apps/desktop/src-tauri/target/release/bundle/dmg/`

## Limitacoes atuais

- ACP bridge esta em v1 pragmatica (foco em fluxo de sessao), sem cobertura total de todos os cantos do protocolo.
- Sem auto-update, code signing e notarizacao prontos para release publica.
- Scheduler e workers sao locais (single-node), sem orquestracao distribuida.
- A timeline operacional eh uma projecao agregada para observabilidade; o canonico continua no audit log e tabelas de execucao.
- O sistema privilegia operacao local-first; nao ha plano de controle remoto multi-tenant nesta fase.

## Documentacao complementar

- `docs/architecture.md`
- `docs/distribution.md`
- `docs/release-checklist.md`
- `docs/technical-roadmap.md`
- `docs/memory-v1-operations.md`
- `docs/streaming-terminal-operations.md`


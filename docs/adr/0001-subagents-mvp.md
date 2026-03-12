# ADR 0001: MVP de Subagentes Persistidos

## Contexto e problema

O ForkClaw ja possui sessoes persistentes, timeline, cron, permissions e skills sobre uma base local-first com FastAPI + SQLite. O problema deste MVP e adicionar subagentes com rastreabilidade operacional sem reestruturar a arquitetura atual nem importar o modelo completo do OpenClaw.

Precisamos suportar delegacao simples parecida com `delegate_task`: a sessao principal cria uma sessao filha persistida, o filho recebe contexto congelado no spawn, executa isoladamente e devolve ao pai apenas um resumo final estruturado com metadados operacionais.

## Decisao arquitetural

- Adotar um modelo semelhante ao Hermes `delegate_task`, nao o modelo completo do OpenClaw.
- Reutilizar `sessions` como fonte canonica para sessoes `main` e `subagent`.
- Persistir lineage diretamente em `sessions` com `kind`, `parent_session_id`, `root_session_id` e `spawn_depth`.
- Persistir lifecycle operacional em `session_subagent_runs`.
- Limitar o MVP a profundidade 1: `main -> subagent`.
- Limitar concorrencia a 3 filhos ativos por sessao pai.
- Manter a boundary `kernel`/`adapter` intacta; esta fatia prepara persistencia e API, nao a execucao real do filho.

## Regras de produto

- Apenas sessoes `kind=main` aparecem na navegacao global e em `GET /sessions`.
- Sessoes `kind=subagent` existem normalmente no SQLite, mas sao acessiveis apenas a partir da sessao pai.
- O filho recebe `goal`, `context`, `toolsets`, `model` e `max_iterations` congelados no spawn.
- O filho nao interage diretamente com o usuario.
- O filho nao pode criar outros subagentes.
- O pai recebe apenas `final_summary`, `final_output_json` e metadados operacionais.
- Nao existe approval especifico para spawn no MVP.
- O agente principal sempre pode spawnar.
- `GET /sessions` pode incluir `subagent_counts` de forma opt-in, embutidos em cada sessao principal.

## Non-goals explicitos

- nested subagents
- cross-session messaging
- `sessions_send` / `sessions_await`
- thread binding
- named durable child sessions
- multichannel routing
- orchestration depth > 1
- arvore de sessoes na sidebar

## Fluxo textual

`main session -> spawn subagent -> child session persisted with frozen goal/context/tool profile -> run row queued/running/completed... -> child produces final_summary + final_output_json -> parent lists/detail subagents and reads only structured result + operational metadata`

## Impactos por camada

- `DB`: `sessions` ganha lineage e payload de delegacao; `session_subagent_runs` registra lifecycle, cancelamento, resumo final, erro e custo estimado.
- `API`: novas rotas de spawn/list/detail/cancel sob `/sessions/{session_id}/subagents`; `GET /sessions` permanece main-only.
- `services`: novo fluxo dedicado de subagentes com validacao de depth, concorrencia e toolsets reais.
- `kernel`: sem mudancas de contrato neste MVP.
- `UI`: sidebar principal continua sem subagentes; drill-down de filhos fica restrito ao contexto da sessao pai.
- `timeline`: sem mudar o payload agregado agora; registrar `subagent.spawned`, `subagent.cancel_requested` e `subagent.cancelled`.
- `tests`: cobrir migration, persistencia, agregacao de contadores, filtro da sidebar, validacoes e cancel idempotente.

## Checklist de rollout

- Migration aplicada em bases novas e existentes com backfill de sessoes legadas para `kind=main`, `spawn_depth=0` e `root_session_id=id`.
- Endpoints principais continuam filtrando `kind=main`.
- Spawn valida pai existente, pai `main`, depth 1, limite de concorrencia e toolsets reais.
- Cancel e idempotente.
- Sessao filha nao aceita interacao direta do usuario.
- Testes de schema, persistencia e API estao verdes antes de liberar a proxima fatia de execucao real.

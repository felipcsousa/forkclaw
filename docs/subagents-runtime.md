# Subagents Runtime MVP

O MVP de subagentes do ForkClaw executa uma sessao filha persistida sem bloquear a requisicao HTTP do spawn.

## Fluxo

`spawn -> session_subagent_runs(queued) -> LocalSubagentWorker claim -> running -> AgentExecutionService.execute_delegated_session(...) -> Task/TaskRun -> completion summary -> mensagem assistant no pai`

Pontos fixos do MVP:

- O filho sempre roda como `sessions.kind=subagent`.
- O worker local faz polling curto da fila e processa um run por vez.
- `session_subagent_runs` continua sendo a fonte canonica do lifecycle.
- `Task` e `TaskRun` sao reaproveitados para observabilidade, timeline e tool calls.
- O filho nao conversa diretamente com o usuario e nao pode criar outros filhos.

## Contexto do Filho

O contexto do subagente e explicito e congelado no spawn:

- `delegated_goal`
- `context` explicito opcional do request
- snapshot pequeno da sessao pai
- identidade/configuracao atual do agente principal
- skills elegiveis recalculadas para o subset final de tools

O filho nao herda automaticamente a conversa inteira do pai. Nao existe memoria compartilhada implicita no MVP.

## Toolsets Publicos

Mapeamento atual de grupos publicos para tools reais:

- `file` -> `list_files`, `read_file`, `write_file`, `edit_file`
- `web` -> `web_search`, `web_fetch`
- `terminal` -> sem tools concretas no catalogo atual
- `local_product_tools` -> sem tools concretas no catalogo atual

Aliases legados aceitos no request:

- `group:fs` -> `file`
- `group:web` -> `web`
- `group:runtime` -> `terminal`

## Resolucao Final de Policy

A policy efetiva do filho segue estas regras:

- expandir apenas os grupos pedidos no spawn
- intersectar com o catalogo real existente
- respeitar o estado atual de cada tool (`allow`, `ask`, `deny`)
- `deny` sempre vence
- nenhuma tool fora do subset pedido entra no request do kernel
- nenhuma primitive de nesting, spawn de subagentes ou interacao direta com usuario e adicionada

O audit log registra:

- grupos pedidos
- grupos vazios
- tools elegiveis finais
- tools negadas por policy

## Conclusao

Quando a sessao filha termina, o sistema persiste em `session_subagent_runs`:

- status terminal
- timestamps
- `final_summary`
- `final_output_json`
- `estimated_cost_usd` quando disponivel
- erro resumido para UI quando houver falha

Tambem e criada uma mensagem `assistant` na sessao pai com um resumo curto e acionavel da conclusao do filho.

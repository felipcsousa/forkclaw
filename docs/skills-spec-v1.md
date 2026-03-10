# Forkclaw Skills Spec v1

## Objetivo

Skills v1 adiciona uma camada formal, local e deterministica para instruir o agente com workflows especializados sem executar codigo de terceiros. A resolucao parte do filesystem, o runtime aplica configuracao por skill no backend, e o prompt recebe apenas skills elegiveis para o contexto atual.

## Fontes e precedencia

- `apps/backend/app/skills/bundled`
- `~/.forkclaw/skills`
- `<workspace>/skills`

Precedencia por `skill_key`:

1. `workspace`
2. `user-local`
3. `bundled`

`skill_key` e o slug derivado de `frontmatter.name`.

## Descoberta

- Cada skill vive em um diretorio filho direto que contem `SKILL.md`.
- O loader resolve `realpath` do root e do `SKILL.md`.
- Qualquer arquivo fora do root resolvido e ignorado.
- Arquivos invalidos tambem sao ignorados.
- Nenhum arquivo da skill e executado durante parse, load ou gating.

## Formato de `SKILL.md`

Formato v1: frontmatter estrito e simples, nao YAML completo.

```md
---
name: List Files Coach
description: Guide filesystem listing for the current workspace.
metadata: {"forkclaw":{"os":["darwin","linux"],"requires":{"tools":["list_files"],"env":["BRAVE_API_KEY"]},"primaryEnv":"BRAVE_API_KEY"}}
enabled: true
---
Use `list_files` before `read_file` when you need directory shape first.
Prefer narrow paths and summarize before reading large trees.
```

Campos:

- `name`: obrigatorio, string em uma linha
- `description`: obrigatorio, string em uma linha
- `metadata`: obrigatorio, JSON valido em uma linha
- `enabled`: opcional, booleano; default `true`

Corpo:

- tudo depois do frontmatter
- preservado como texto puro
- sem includes, sem import, sem execucao

## Metadata v1

Namespace reservado: `metadata.forkclaw`

Campos suportados no gating inicial:

- `metadata.forkclaw.os`
- `metadata.forkclaw.requires.tools`
- `metadata.forkclaw.requires.env`
- `metadata.forkclaw.primaryEnv` opcional, para mapear `apiKey` na env principal da skill

Exemplo minimo:

```json
{
  "forkclaw": {
    "requires": {
      "tools": ["list_files"],
      "env": ["BRAVE_API_KEY"]
    }
  }
}
```

## Configuracao por skill

Configuracao persistida:

- `skills.entries.<skill_key>.enabled`
- `skills.entries.<skill_key>.config`
- `skills.entries.<skill_key>.env`
- `skills.entries.<skill_key>.apiKey` via secret store, opcional

Modelo pratico:

- `enabled` e `config` ficam em `settings`
- `env` e `apiKey` ficam no secret store
- `env_keys` fica em `settings` como indice nao secreto
- `apiKey` so e aceito quando a skill declara `metadata.forkclaw.primaryEnv`

## Gating

Uma skill so entra no prompt quando passa por todas as verificacoes:

1. `enabled`
2. `metadata.forkclaw.os`
3. `metadata.forkclaw.requires.tools`
4. `metadata.forkclaw.requires.env`

Regras:

- `enabled` efetivo respeita override de config e, na falta dele, usa o `enabled` do arquivo
- tools com permissao `deny` nao contam como disponiveis
- env e resolvida pela combinacao de ambiente atual do processo e env configurada para a skill
- skill bloqueada permanece observavel no catalogo com `blocked_reasons`, mas nao e selecionada

Razoes de bloqueio v1:

- `disabled`
- `unsupported_os`
- `missing_tools`
- `missing_env`

## Estrategia de selecao

Estrategia v1 explicita: `all_eligible`

Comportamento:

- toda skill elegivel entra no prompt
- ordenacao deterministica por `skill_key`
- cada item resolvido registra `matched_tools` para permitir ranking futuro sem mudar o shape da resolucao

## Injecao no prompt

Fluxo no runtime:

1. descobrir skills nas tres fontes
2. aplicar precedencia por `skill_key`
3. aplicar gating
4. construir o bloco `# Skills`
5. anexar o bloco ao system prompt antes da execucao

Formato de prompt v1:

```text
# Skills
Strategy: all_eligible

## list-files-coach
Name: List Files Coach
Description: Guide filesystem listing for the current workspace.
Config: {"mode":"narrow-first"}
Source: workspace
Path: /workspace/skills/list-files-coach/SKILL.md

Use `list_files` before `read_file` when you need directory shape first.
Prefer narrow paths and summarize before reading large trees.
```

Se nenhuma skill for elegivel:

```text
# Skills
Strategy: all_eligible

No eligible skills were resolved for this run.
```

## Runtime e seguranca

- Env de skill e injetada apenas durante a execucao do agente.
- O ambiente original e restaurado ao fim do run.
- Secrets nao entram no prompt.
- Secrets nao entram em logs, `task_runs.output_json`, activity ou tool calls.
- O loader nunca executa scripts da skill.
- O loader rejeita escapes de path apos `realpath`.
- O frontend recebe apenas metadados redigidos e a lista de `configured_env_keys`.

## Observabilidade

Cada run persiste um resumo redigido de skills resolvidas:

- `strategy`
- `key`
- `name`
- `origin`
- `source_path`
- `selected`
- `eligible`
- `blocked_reasons`

Eventos de auditoria:

- `skills.resolved`
- `skills.config.updated`

Tool calls e timeline tambem expoem:

- `guided_by_skills`
- `resolved_skills`
- `skill_strategy`

## API v1

- `GET /skills`
- `PUT /skills/{skill_key}`

`GET /skills` retorna:

- `strategy`
- `items[]` com `key`, `name`, `description`, `origin`, `enabled`, `eligible`, `selected`, `blocked_reasons`, `config`, `configured_env_keys`, `primary_env`

`PUT /skills/{skill_key}` aceita:

- `enabled`
- `config`
- `env`
- `api_key`
- `clear_env`
- `clear_api_key`

Respostas sempre retornam valores redigidos; segredos nao voltam para a UI.

## Estados de UI v1

Painel de tools:

- aba `Catalog`: nome, grupo, risco e permissao atual
- aba `Skills`: nome, origem, elegibilidade, razao de bloqueio e enable/disable
- aba `Recent calls`: destaque `Guided by ...` quando houve skill guidance

Timeline de atividade:

- mostra `Guided by: ...`
- mostra `Strategy: all_eligible` quando houver skills resolvidas

Estados visuais esperados:

- vazio: nenhum skill resolvido
- elegivel: skill selecionada para prompt
- bloqueada: skill visivel com razao de bloqueio
- misto: algumas skills elegiveis e outras bloqueadas

## Compatibilidade

- Sessoes existentes continuam validas.
- A mudanca e aditiva no metadata de run e no prompt builder.
- O shape de resolucao ja deixa espaco para ranking futuro por relevancia.

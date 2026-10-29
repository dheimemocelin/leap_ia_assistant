# Engineering Harness smoke test — 2026-10-29

Resultado: **PARCIAL**. Harness Lite v1.1 funciona para inspeção, persistência, recuperação e gate unittest. Ruff/Pytest não são gates nativos suportados; nenhum deles foi executado nem aprovado neste teste.

Origem imutável: `/tmp/tmp.fCmo3OfNSF/skill`, SHA `708706abe5add6a5bea1d51087ef343675843da4`. Versão funcional identificada pelo README/CHANGELOG: Harness Lite v1.1 (schema de estado v1; não há opção CLI --version). Comandos disponíveis: create, status, history, evidence, cancel, restore, run, resume, note.

## Execuções reais

Comandos base, executados no diretório da origem: `python3 -B -m harness --workspace <workspace> <command>`.

- LEAP: `create 'LEAP read-only inspection' --plan /tmp/leap-harness-smoke-pg8r8zx3/inspection.json`; depois `run`, `status`, `history`, `evidence` para a tarefa `41b6f834dd9646b69cf27b6f9e459aee`.
- Estados confirmados pelo histórico: pending → planning → running → validating → completed. Leitura real do README e gate SHA-256 passaram. Checkpoint `.harness/41b6f834dd9646b69cf27b6f9e459aee.json` e backup `.bak` persistidos no LEAP; .harness possui ignore próprio.
- Workspace isolado `/tmp/leap-harness-smoke-pg8r8zx3/recovery`: plano oficial examples/harness/recovery.json, tarefa `f0ea138a553f40ef8f2e0a979dced34c`. `run` bloqueou após tentativa 1; `resume` sem confirmação continuou bloqueado e não repetiu a operação; `resume --confirm-retry simulated-operation` concluiu na tentativa 2.
- A recuperação acima usa **fixture sintética**, executada de verdade em processo local; não comprova recuperação de integrações LEAP/CRM ou de modelos.
- Teste de corrupção: primário isolado substituído por JSON inválido; `status` retornou exit 1, “Invalid/missing checkpoint; no execution or automatic rollback performed”. `restore` recuperou backup e preservou primário em `.corrupt`; estado restaurado blocked, validado em novo processo `status`. Não foi retomado após restauração, pois o backup exige inspeção conservadora. Não houve corrupção de checkpoint do LEAP.
- Cópia isolada do repositório em `/tmp/leap-harness-smoke-pg8r8zx3/upstream-copy`: tarefa `f6817ceee58a4fe69d00562b915b1327`, gate tests/unittest. `run` bloqueou sem --allow-tests; `resume --allow-tests` concluiu. Gate real passou: exit 0, sem timeout, duração 12.184s, término confirmado. Executou unittest do Harness, não Pytest do LEAP.
- Planos com suites ruff/pytest foram rejeitados pelo normalizador: “Supported test suites: skills, unittest”. Sem extensão do Harness, não há gate Python arbitrário. Gate review também é indisponível na implementação; não executado neste smoke.
- `CodexExecutor.preflight(Path(workspace))` passou tanto no checkout original quanto no LEAP: retorno None, CLI 0.165.0. Executou somente --version e exec --help. Não houve --allow-codex, inferência paga, agente remoto ou chamada a Evolution/Syonet.

## Evidências e limites

Comandos completos, saídas e exit codes: `/tmp/leap-harness-smoke-pg8r8zx3/results.json`. Plano: inspection.json. Gate unittest: unit.json e unit-evidence.json no mesmo diretório. Checkpoints temporários: recovery/.harness e upstream-copy/.harness. Artefatos em /tmp são locais e não têm garantia de retenção permanente.

Somente a inspeção/hash e o gate unittest constituem evidência de operações reais sobre arquivos/testes. A sequência de falha/retry é propositalmente sintética. Preflight comprova compatibilidade do executável, não autenticação/inferência ou integração automática com T3. Harness CLI e sessão T3 têm ciclos de vida independentes.

Aplicação, catálogo, mídia, política comercial e alterações preexistentes não foram modificados. Esta execução adicionou somente este relatório e checkpoints de inspeção; sem commit, push, merge ou deploy.

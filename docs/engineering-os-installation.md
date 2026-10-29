# Engineering OS — instalação e evidências

Verificado em 2026-10-29. Origem: https://github.com/dheimemocelin/skill, SHA `708706abe5add6a5bea1d51087ef343675843da4` (HEAD remoto confirmado). Codex CLI `0.165.0`; Python `3.12.3`.

Antes: não existiam `.agents/skills`, `.codex/agents` ou `AGENTS.md` no projeto. Não encontrada instalação global das sete skills em `~/.agents/skills` ou `~/.codex/skills`; existem skills de sistema/plugins do executor. Configuração e credenciais globais não foram alteradas.

Instaladas em `.agents/skills/<nome>/SKILL.md`: engineering-os, software-engineering, ai-engineering, data-engineering, ui-ux-design, fde-delivery, git-quality. Instalador skill-installer executado com SHA fixado e destino local. Adapters gerados pelo script oficial em staging temporário e copiados sem sobrescrever configurações existentes.

Agentes em `.codex/agents/`: ai_engineer.toml, software_engineer.toml, quality_reviewer.toml. Adicionado `AGENTS.md` com orientação do projeto e preservada licença MIT em `.agents/ENGINEERING_OS_LICENSE`.

Validações: 7 SKILL.md idênticos à origem; validator oficial passou (7 skills e links locais). Os 3 TOMLs foram parseados com tomllib, têm name/description/developer_instructions e correspondem ao output oficial.

Descoberta real: processo local `codex app-server`, initialize seguido de `skills/list` com cwd do projeto e forceReload=true: retornou as 7 skills em paths locais, enabled=true e errors=[]. Nenhuma chamada de inferência foi necessária. O teste não executou agentes nem comprova seleção de custom roles pelo executor T3. A sessão T3 já aberta pode manter catálogo de skills em cache; novas instruções devem ser carregadas em nova sessão/turno. Os agentes dependem de suporte do executor e confiança no projeto. O contrato read-only do reviewer não endurece o sandbox herdado.

Não foram modificados aplicação, catálogo, imagens ou CommercialPolicyEngine. Nenhum commit, push, merge ou deploy realizado nesta instalação.

# Engineering baseline review — 2026-10-29

**Resultado: REPROVADO para integração/atendimento real.** Há componentes locais úteis, mas quatro testes falham e as barreiras comerciais têm bypasses comprovados. Esta auditoria não implementou correções.

## Escopo, baseline e método

Workspace LEAP, branch `feat/leap-mvp-foundation`, HEAD `21fe8b7`, dois commits à frente do remote conhecido. Revisão do estado de trabalho, não apenas do HEAD. Skills aplicadas: software-engineering, ai-engineering, git-quality e fde-delivery. Inspecionados arquitetura/ADRs, contratos, módulos app, testes, schema SQL, Compose, dependências, manifesto e arquivos das 12 fotografias.

Estado preexistente preservado: models.py modificado; media_library.py, teste de busca, imagens/manifesto, instalação Engineering OS, AGENTS.md e relatórios anteriores não rastreados. Não foram feitos commit, stash, reset, merge, push, deploy ou chamadas a serviços de atendimento. Documento novo desta execução: este relatório. Harness adicionou checkpoints ignorados em .harness.

## Descoberta e ativação dos agentes

Teste real nesta execução: initialize + skills/list(forceReload=true, cwd do projeto) via `codex app-server`: sete skills locais enabled=true, errors=[]. Descobertas engineering-os, software-engineering, ai-engineering, data-engineering, ui-ux-design, fde-delivery, git-quality. TOMLs ai_engineer, software_engineer e quality_reviewer parseados com tomllib.

T3 orchestrator_capabilities confirmou delegação Codex disponível (canRunChildTask=true); Claude indisponível. **quality_reviewer não foi acionado**: a restrição de não consumir inferência adicional prevaleceu sobre a solicitação condicional de delegação. Nenhuma revisão independente é declarada concluída. Os contratos de especialistas foram disponibilizados, não ativados como subagentes. O contrato read-only não reduz o sandbox herdado.

## Componentes aprovados no escopo testado

- Importador do estado local carrega 12 registros com id normalizado, todos pending_review; teste específico passou. SHA-256 de cada um dos 12 arquivos corresponde ao manifesto. Não implica direitos de uso, classificação visual ou aprovação editorial.
- get_commercial_offer não está na classe SalesTools. Bloqueios de CRM para dados mínimos, consentimento/adapter ausente ou inválido e falta de chave são cobertos por testes que passaram.
- Validação de aprovação Pydantic existe para catálogo/mídia. Consulta padrão bloqueia mídias pendentes; não há publicação ou envio real.
- Health live passou. Ruff passou no estado completo de app/tests. Isso não aprova a aplicação ou a segurança global.

## Achados comprovados

### P0-01 — política não é obrigatória na construção da resposta (alto)

app/domain/response.py:21-31: somente a fábrica opcional validated aplica CommercialPolicyEngine. Reproduzido `AssistantResponse(text='Preço R$ 180.000', confidence='insufficient_evidence')`: aceita e serializa texto proibido. Tornar a validação inevitável na fronteira de saída; testar construtor, model_validate e serialização usada pela API.

### P0-02 — projeção financeira é apenas superficial (alto)

app/policy/commercial.py:50-57 inclui specifications, features e sources sem validar conteúdo interno. Reproduzido model_safe_vehicle com specifications.price=180000 e features=['R$ 180.000']: ambos permanecem no retorno. Preço pode entrar no contexto mesmo com ferramenta financeira removida. Definir schema positivo de specs técnicas e tratar todos os textos/metadados como dados não confiáveis; testar conteúdo financeiro em todos os níveis.

### P0-03 — política regex aceita pedidos/respostas proibidos (alto)

app/policy/commercial.py:14-41. Probes determinísticos retornaram ALLOW e validate_output=True para: “Custa cento e oitenta mil.”, “Aceitamos PIX.”, “Está reservado para você.”, “1,2%” e “Quais condições de pagamento?”. Regex de plural está incorreta e limite de palavra após % não detecta a forma isolada. Os testes atuais de taxa também contêm a palavra taxa, mascarando essa lacuna. Ampliar corpus/paráfrases e validar a fronteira final, sem alegar que regex elimina prompt injection.

### P1-01 — busca de mídia incompleta e fixtures incompatíveis

app/catalog/media_library.py:98-132; tests/unit/test_media_library.py:12-56. Três testes falham: B10 REEV ausente dos veículos canônicos de fixtures; busca frente encontra front_seats_roof além de exterior frontal. Ângulo desconhecido vira ausência de filtro (linhas 78-80), podendo retornar tudo do veículo. Corrigir classificação sem substring ambígua, rejeitar filtros desconhecidos e criar fixtures sintéticas aprovadas válidas.

### P1-02 — catálogo real não contém veículos canônicos

`load_catalog(Path('data/catalog'))`: 12 mídias, **zero veículos**. O loader trata arquivo ausente como lista vazia (loader.py:36-43), não valida associação mídia→veículo, e o repositório não valida IDs duplicados ou motorização. Fixtures têm c10-bev, c10-reev e b10-bev; não b10-reev. Consequência atual: biblioteca carregada do catálogo real bloqueia todas as buscas por falta de veículo. Criar/validar registros canônicos pendentes com fontes e testes de associação, sem aprovar veículos por inferência do nome do arquivo.

### P1-03 — alteração local do schema quebra teste existente e persistência diverge

models.py:66-91 adiciona campos de arquivo/direitos e exige usage_rights_status=approved; tests/unit/test_sales_tools.py:38 cria mídia aprovada sem esse campo, resultando em ValidationError. Testes de media_library usam model_copy(update=...), que não revalida e cria objetos que o construtor rejeitaria. SQL vehicle_media não possui os novos campos e source_url é NOT NULL, enquanto o estado Python aceita None e as 12 fotos não têm URL de origem. Precisa de decisão de schema/migração compatível e fixtures construídas por validação normal.

### P1-04 — readiness falha antes do tratamento de erro

app/config.py:7 usa postgresql+psycopg; pyproject declara asyncpg e não psycopg; routes.py cria engine antes do try. GET real local de /health/ready via TestClient lançou ModuleNotFoundError: No module named 'psycopg', em vez de 503. Teste existente substitui engine por mock e mascara a falha. Não há timeout explícito do probe SQL. Alinhar driver assíncrono, ciclo de vida, timeout e teste com configuração efetiva.

### P1-05 — dois caminhos de consulta de mídia divergem e expõem localização

SalesTools.search_vehicle_media (sales.py:84-103) ignora a biblioteca nova e retorna model_dump completo, incluindo asset_path, storage_uri e proveniência. Biblioteca retorna entidades completas e apenas verifica existência/confinamento, sem MIME/hash em runtime. IDs são rótulos legíveis. Não há entrega autenticada implementada. Centralizar busca e projetar metadados públicos; manter resolução/entrega fora do modelo.

### P1-06 — contratos arquiteturais se contradizem

architecture.md:5 e ADR-005 ainda permitem ofertas aprovadas; ADR-008 proíbe qualquer valor financeiro. contracts.md seção de resposta ainda permite preço com fonte, contradizendo política obrigatória. Estados, audit logs, contrato Syonet validado em startup e outbox descritos como garantias não existem no runtime. Documentar planejado versus implementado e remover permissão financeira conflitante.

### P1-07 — baseline commitado não é reproduzível sozinho

O commit 21fe8b7 inclui teste que depende de data/catalog não rastreado e loader que passa source_url=None; no HEAD o modelo exige HttpUrl. Novos campos e fixtures/imagens ainda estão fora do histórico. O sucesso da importação observado vale para o workspace local; clone limpo não contém seus insumos. Preparar commits coerentes com fixtures pequenas e ativos/controlador de dados definidos, após corrigir suíte.

## Segurança e funcionalidades ausentes

Confirmado por inspeção: runtime HTTP expõe somente probes; autenticação, sessão/tenant scoping, rate limiting, webhook, memória persistente, grafo LangGraph, LLM/RAG, worker/outbox, envio Evolution, adapter Syonet concreto, UI e painel não estão implementados. APP_API_KEY não é usado. Não há proteção efetiva de PII/retention em runtime; body_ciphertext no SQL é só nome de coluna, não implementação de criptografia.

Riscos de desenho comprovados: FKs customer/conversation/message não incluem tenant e não há RLS no SQL; integridade entre tenants não é garantida pelo banco. UNIQUE(channel, provider_message_id) não inclui tenant/instância. Compose publica Postgres/Redis e usa senha local conhecida, sem autenticação Redis; inadequado para exposição compartilhada. Essas configurações existem, mas **não se comprovou exposição real nem vazamento**.

CRM usa protocolos injetáveis, chave repassada ao adapter e booleano de consentimento/ID verificado por protocolo. Não há dedupe persistente, escopo de operador/tenant, retry/timeout ou envio concreto; teste usa fake com dict e não prova idempotência Syonet. Campos mínimos aceitam strings sem formato/identidade de veículo aprovado; crm_authorized da qualificação não equivale à autorização real de escrita.

Hipóteses não comprovadas: exploração entre tenants, SSRF, comprometimento por prompt injection e vazamento em LLM/CRM. Não há integração externa ativa para confirmar essas hipóteses. Não foram usados dados reais de clientes.

## Evidências dos gates

- `python3 -B -m pytest -q -p no:cacheprovider`: **16 passed, 4 failed** (0.86s), exit 1. Falhas: test_exact_vehicle_isolation_across_all_three_vehicle_ids; test_powertrain_synonyms_and_explicit_mismatch_do_not_mix_records; test_category_angle_and_color_filters_are_deterministic; test_media_search_filters_and_requires_approved_stored_asset.
- `ruff check app tests --no-cache`: passou. `git diff --check`: passou. Não aplicado --fix.
- Probes Python reproduziram P0-01/02/03 e P1-04; não persistidos como testes novos, em respeito à restrição de não alterar código.
- Hash dos 12 JPEGs verificado com hashlib. Descoberta real de skills confirmada novamente.
- Integração Postgres/Redis, Docker e chamadas externas não executadas. Docker indisponível no PATH. Não há aprovação de evals de modelo, isolamento multiusuário ou integração real.

## Harness e checkpoints desta auditoria

Harness Lite v1.1, origem SHA 708706abe5add6a5bea1d51087ef343675843da4. Comandos `python3 -B -m harness --workspace <LEAP> create ... --plan <plan.json>`, run, status, evidence. Tarefa `3bc9c1c331234b4db3725fe906be4a96`: inspeção real e gate SHA-256 da política passaram; gate independent-review bloqueado com review_executor_unavailable, agent_dispatched=false. Estado global blocked, exit 2; checkpoint primário/backup em .harness.

Evidências JSON e plano em `/tmp/leap-baseline-yrrw2z5m` (retenção temporária). Skills/list salvo em discovery.json; status e gates em status.json/evidence.json. Harness suporta gates de arquivo/hash, unittest/skills e perfis Node; não Ruff/Pytest arbitrários. Por isso esses dois comandos foram executados diretamente, sem fingir aprovação pelo Harness. A tarefa bloqueada não significa que o hash falhou nem que houve revisão independente. Sem --allow-codex, subagentes ou inferência adicional.

## Plano incremental de correção

**P0:** tornar política obrigatória em todas as respostas; fechar vazamento financeiro em payloads aninhados; ampliar testes adversariais determinísticos e revisar independentemente antes de qualquer canal real.

**P1:** corrigir os quatro testes com fixtures validadas; definir canonical IDs/associações e classificação de ângulos; unificar busca/projeção; reconciliar schema Python/SQL e publicação de ativos; corrigir readiness/driver; atualizar contratos; fazer baseline reproduzível em clone limpo. Depois implementar auth, isolamento, consentimento e outbox com testes de integração em serviços locais.

**P2:** integrar adapter LLM/grafo restrito e canais/sandbox; métricas e observabilidade sem PII, retenção/LGPD, backup/restore, testes de carga e piloto acompanhado. Avaliações adversariais reais e revisão independente seguem pendentes. Nenhuma funcionalidade futura deve ser declarada pronta por passar testes unitários com mocks.

# Tool calling e grounding real — 2026-10-29

**Resultado: APROVADO no escopo estreito exercitado.** Groq solicitou duas chamadas reais de get_vehicle_details; o agente executou a consulta local, produziu uma resposta factual exata vinculada a uma fonte verificada, absteve-se para dado ausente e bloqueou preço/negociação. Isso não aprova grounding genérico, todo o catálogo ou atendimento em produção.

Baseline 491f597. Skills ai-engineering, software-engineering e git-quality lidas/aplicadas. Preservados grafo LangGraph, adapter Groq, orçamento de duas chamadas por turno, CommercialPolicyEngine e barreira HTTP. Nenhuma aprovação/alteração das 12 fotos; sem WhatsApp/Syonet, merge, push ou deploy. Nenhum subagente foi acionado.

## Fonte e aprovação interna

Catálogo separado em data/validation/grounding; não é o catálogo de atendimento. Fatos conferidos nesta execução na fonte oficial https://www.leapmotor.com.br/tecnologias-eletrificadas.html : C10 BEV, autonomia até 338 km no ciclo PBEV. A mesma página confirma identidade BEV do B10, mas a especificação de capacidade de bateria não foi registrada porque não há evidência selecionada para ela. O carregamento da página b10.html falhou por timeout; nenhuma especificação foi inferida dessa falha.

vehicles.json contém apenas essas identidades e a autonomia. facts.json guarda fato, valor, frase revisada, assunto e source_id. review.json registra data, fonte e escopo. approved_by=internal-source-verification identifica revisão feita pelo assistente nesta execução para ensaio interno; **não significa aprovação da fabricante ou de revisor humano independente**. Não há dado sintético apresentado como fato oficial, preços ou estoque nesse catálogo. Valores permanecem sujeitos a mudanças na fonte; captura pontual, sem rotina de atualização automática ou snapshot integral de HTML.

## Comportamento implementado

- Mesmo grafo; opção prefer_tool_calling=True apenas no ensaio força o caminho de planejamento em vez do atalho determinístico. Groq recebe tools e um hint do veículo canônico já resolvido, pede a função e argumentos; o dispatcher valida allowlist e associação modelo/motorização, executa SalesTools e grava tool_events. A escolha da ferramenta nesta prova foi assistida pelo hint, não planejamento autônomo irrestrito.
- GroundingPolicy valida fato técnico numérico contra valor do catálogo aprovado e source_id calculado de URL+data. Reconfere valor/fonte/aprovação em cada consulta para impedir uso de dado alterado ou revogado.
- Para detalhes, o modelo retorna apenas JSON fact_ids entre os fatos oferecidos. Texto final é renderizado pelo servidor com as frases revisadas exatas. IDs desconhecidos, campos adicionais, texto livre e fato de outro assunto são recusados. Somente fontes dos fatos selecionados constam na resposta. Dados financeiros aninhados continuam removidos pela projeção técnica existente.
- Sem fatos revisados pertinentes, não há chamada de composição: saída insufficient_evidence, sem fonte, com oferta de consultor. O padrão do agente sem registro de fatos passa a abster-se em detalhes, mesmo se houver identidade de veículo aprovada. O teste anterior que aceitava fonte para specs vazias foi corrigido para exigir abstenção; teste de timeout foi movido para consulta de fotos, que efetivamente atinge o LLM.
- Eventos de ferramenta ficam na sessão em memória: nome, argumento canônico, projeção técnica do resultado, sources e origem llm/deterministic. Sem chave, prompts completos, PII, caminhos internos ou bytes de imagem. Não é uma trilha persistente de produção.

## Execução real controlada

Script original executado uma vez: python3 -B /tmp/leap-grounding-real.py. Reprodutor versionado scripts/validate_groq_grounding.py exige --allow-real-groq, credencial/modelo configurados e workspace como cwd. Reexecutá-lo poderá consumir nova cota; não foi reexecutado para polir resultados. Três interações, máximo seis chamadas, sem retry; foram feitas apenas três chamadas reais. Cenários passaram pelo endpoint FastAPI e pela barreira HTTP via TestClient; Groq foi real, catálogo interno e consultas locais também reais, sem fotos aprovadas artificialmente.

1. “Qual a autonomia do C10 BEV no ciclo PBEV?” Groq devolveu tool_call get_vehicle_details(vehicle_id=c10-bev); resultado real specifications.range_km=338. Segunda chamada selecionou o fato revisado. Resposta final: O C10 BEV tem autonomia de até 338 km no ciclo PBEV. source_ids=[src-ddb8b165ff27670a154b], resolvido ao registro oficial consultado e efetivamente usado. HTTP 200, grounded, sem handoff, sem mídia. Latência 1986.63 ms.
2. “Qual a capacidade da bateria do B10 BEV?” Groq pediu get_vehicle_details(vehicle_id=b10-bev); resultado real specifications={}. Agente absteve-se, sem chamada de composição, sem fontes/mídias e com handoff. HTTP 200. Latência 489.07 ms. Não inventou capacidade de bateria.
3. Preço/negociação: bloqueado no guard, sem ferramenta/LLM, sem valores financeiros na saída, handoff true. HTTP 200. Latência 7.70 ms.

Modelo efetivo em todas as chamadas: openai/gpt-oss-20b. Todas HTTP 200. Primeira interação: 528+423=951 tokens de entrada, 88+103=191 de saída; segunda: 525 de entrada e 83 de saída; terceira: zero. Total **1476 tokens de entrada, 274 de saída, três chamadas Groq**, duas solicitações de ferramenta. Nenhuma falha real de provedor observada. Valor monetário cobrado não disponível: não foi estimado nem inferido de plano gratuito. Métricas observacionais, não benchmark.

Evidência pública sanitizada: docs/grounding-real-evidence.json contém perguntas estáticas sem dados pessoais, chamadas/argumentos/resultados, resposta final, política, fontes, tokens e latências. Não contém credencial ou resposta bruta do provedor. As fontes da resposta factual correspondem exatamente ao fato; fontes vazias nas abstenções são intencionais.

## Gates e regressões

- python3 -B -m pytest -q -p no:cacheprovider: **84 passed, 1 warning** (1.86s). Aviso transitivo de depreciação LangGraph já existente.
- ruff check app tests scripts/validate_groq_grounding.py --no-cache: passou.
- python3 -m compileall -q app tests scripts: passou.
- git diff --check: passou.

Novos testes: despacho e origem do tool call, frase exata e fontes, ausência de evidência, rejeição de alegação adicional/fact_id desconhecido, fonte/valor divergentes, campos financeiros aninhados, alteração/revogação e tentativa do modelo de trocar o veículo solicitado. Testes automatizados não fazem chamadas pagas. O ensaio real foi separado e opt-in.

## Riscos residuais e próximos passos

Cobertura factual comprovada para **um fato técnico**, uma ausência de evidência e uma solicitação comercial bloqueada. Associação por assunto usa termos revisados e pode exigir expansão; não é compreensão semântica universal. A correção factual da frase revisada depende da revisão de fonte; igualdade com o catálogo não prova, sozinha, verdade externa. Fontes não são atualizadas automaticamente e não existe aprovação humana independente neste ensaio.

Listagem de identidades e respostas de fotos conservam seu contrato anterior e não foram avaliadas como respostas factuais livres neste teste real; fotos continuam pendentes. Limitações lexicais P0-03 continuam; o renderizador impede texto financeiro novo no caminho estrito de detalhes, mas não é certificado de segurança de todos os textos livres da aplicação. Registro de fatos interno não foi ativado automaticamente no catálogo de atendimento. Persistência multiworker, TTL de memória, revisão humana/editorial ampliada, atualização de fontes e avaliações com mais fatos/perguntas seguem pendentes.

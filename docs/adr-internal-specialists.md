# ADR — Especialistas internos, identidade e memória únicas

Data: 2026-11-03. Estado: implementado para avaliação; ativação no piloto pendente.

## Contexto

O responsável solicitou acolhimento e interpretação de intenção, com atendimento especializado em vendas ou dúvidas, sem menus de departamentos nem anunciar FAQ. O piloto mostrou interpretações equivocadas e apresentações repetitivas. A simples troca de modelo ou adição de documentos não demonstrou resolver isso.

## Decisão

Adicionar um roteador e três executores internos ao LangGraph existente, reutilizando SalesAgent, Groq configurável, memória, ferramentas e validações. O backend deriva o executor de um ato tipado e limita suas ferramentas. O cliente vê somente a Lia. O estado não é copiado para agentes independentes, e não há delegação recursiva, execução paralela de modelos ou escrita externa.

Manter limite total de duas chamadas por turno. Reutilizar a normalização/observação existente e o mesmo limite de saída. Especializar evidências de apresentação e resposta técnica. Ativar por flag de servidor inicialmente false para permitir comparação e reversão sem alterar produção.

## Consequências

Há separação de responsabilidades, rastreabilidade de roteamento e controle de capacidade por executor. Não há garantia automática de naturalidade. O classificador e a validação de prosa ainda têm limitações; a renderização factual conservadora permanece. A divisão é incremental, não uma arquitetura de agentes autônomos de propósito geral.

A liberação exige conversas reais controladas, revisão humana de tom/continuidade e aprovação explícita de ativação. Testes com simulador são necessários, mas insuficientes para essa decisão. Não se muda provedor ou modelo por essa refatoração.

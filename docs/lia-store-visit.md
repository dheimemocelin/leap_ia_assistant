# Lia: qualificação para visita à loja

## Problema observado e diagnóstico

As capturas do piloto mostram uma abertura funcional (nome, B10, escolha BEV e fotos), mas pouca continuidade após uma reação positiva. A pergunta sobre compra foi tratada como falta de conhecimento técnico. O diagnóstico em `SalesAgent.consult`, `observe`, `purchase_plan` e `compose_conversation` mostrou ausência de um ato de decisão de compra e overrides fixos para intenção de compra/visita.

## Mudança no mesmo grafo

O novo plano `purchase` separa decisão do comprador de consulta técnica. O roteador contextual também pode sugerir esse ato, sem obter autoridade para contato, transação ou consentimento. O LLM redige a resposta a partir do contexto e de uma pergunta opcional autorizada. Não há outro agente, grafo, ferramenta de venda ou integração.

Quando existe veículo identificado e interesse em compra, a próxima ação prioriza conhecer o carro na loja. Após aceite, coleta uma preferência de dia/período; depois pode perguntar sobre carro na troca. Uma pergunta por turno, sem repetir perguntas já feitas nem pressionar após recusa. Reações positivas podem explorar o uso do carro quando essa informação ainda falta; não exigem pergunta sempre. A redação continua livre dentro das verificações existentes.

Apenas perguntar sobre compra não é intenção firme nem autorização para vendedor. Interesse em visita não autoriza compartilhamento. As proibições financeiras e as regras de handoff permanecem. Uma lacuna identificada pelo teste `Quanto vale meu usado na troca?` foi bloqueada no guard existente, sem modificar CommercialPolicyEngine. Confirmações fictícias de agenda/aceitação do usado são rejeitadas na composição.

## Dados locais

`LeadProfile`, estado persistido e oportunidade local guardam `visit_preference` e `trade_in_interest`, além dos campos existentes (nome preferido vinculado ao contato, veículo canônico, uso, necessidades, intenção, prazo, consentimento). São campos JSON aditivos; não exigem recriar tabelas.

- `visit_interest`: sim, não ou ainda desconhecido.
- `visit_preference`: preferência declarada, como `sabado / manha`; não é compromisso, data convertida ou horário confirmado.
- `trade_in_interest`: sim, não ou desconhecido; não guarda avaliação financeira, placa, documentos ou promessa de aceitação.
- Oportunidades continuam `local_only`; dados de handoff somente com pedido explícito e consentimento.
- Retenção existente de 30 dias permanece. Não foi criada retenção indefinida.

## Evidências e limites

Os quatro primeiros testes de comportamento falharam antes da correção. A suíte nova cobre 14 casos: sequência das capturas, compra explícita, não repetição, recusa de contato/visita, elogio com erro de digitação, persistência e reabertura do banco, troca positiva/negativa, bloqueio de avaliação e proibição de confirmar agenda. O teste da avaliação de usado revelou uma lacuna adicional antes do ajuste do guard.

A comparação executada com o mesmo simulador e catálogo está em [purchase-visit-before-after.json](evaluations/purchase-visit-before-after.json). Antes (`dfa162b`), a pergunta era `other` e os detalhes de visita/troca não eram registrados. Depois, ela é `purchase` e a sequência sintética registra visita, preferência e troca. Isso comprova diferenças de fluxo/persistência, não melhoria de conversão ou naturalidade do Groq.

Não houve inferência paga ou envio real de WhatsApp nesta avaliação. Permanecem pendentes: avaliação humana/modelo real, mais paráfrases/negações, conteúdo técnico aprovado mais amplo e dados oficiais da loja (endereço, horários, processo de visita). Não há agenda integrada: a Lia não pode confirmar visita, atendimento, carro disponível ou test-drive. Os filtros de afirmações continuam heurísticos, não prova geral de grounding. Não existe garantia de comparecimento ou venda.

Gates finais: 321 testes Pytest passaram, Ruff passou, compilação Python passou e `git diff --check` passou. Um aviso de depreciação upstream do LangChain permanece. Nenhuma dependência nova foi instalada.

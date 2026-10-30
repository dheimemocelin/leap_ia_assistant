> Histórico da etapa anterior. A regra de handoff foi substituída pela solicitação explícita do cliente; veja [SDR v2](sdr-v2-evaluation.md).

# Lia — correção SDR P1 e acolhimento

Data: 2026-10-30. Baseline: `bd94068`. Branch: `fix/sdr-context-continuity`.
Skills: ai-engineering, software-engineering, fde-delivery e git-quality, conforme roteamento Engineering OS. Alterações iniciais locais: nenhuma. Sem alterações no CommercialPolicyEngine, barreira HTTP, Groq adapter, biblioteca de mídia ou aprovações.

## Diagnóstico comprovado

A jornada “Qual a autonomia do C10 BEV?” → “Manda fotos.” → “Pensei em utilizar para Uber.” foi executada antes da correção com adapter simulado e ferramentas reais locais. O terceiro turno caiu em `get_vehicle_details`, sem fatos pertinentes, e respondeu que precisava de confirmação técnica. O erro era de roteamento: declaração de uso não reconhecida. A sequência fixa uso → prioridade → visita também produzia perguntas descoladas do contexto.

Antes/depois completos: [antes](evaluations/sdr-before.json), [depois](evaluations/sdr-after.json). Esses arquivos registram **execuções locais reais de diálogos sintéticos com LLM simulado**, não inferências Groq nem conversas de clientes.

## Arquitetura preservada

O mesmo LangGraph permanece `consult → guard → select → tools → compose → output`. Groq e as três ferramentas de leitura permanecem. Não existe outro agente ou grafo.

- Determinísticos: extração conservadora de uso, necessidades, objeções, distância informada, primeira experiência elétrica, intenção de compra, consentimento, identidade, contatos e política de próxima ação. Preço/negociação continuam bloqueados antes de qualquer inferência.
- LLM: grounding técnico existente seleciona IDs de fatos revisados; nas respostas consultivas, uma chamada escolhe uma formulação entre alternativas autorizadas do plano. O modelo não recebe autoridade para criar fatos, benefícios, fontes, ações ou perguntas. Respostas livres, JSON inválido, índices inválidos e falhas usam formulação determinística segura. Esta etapa melhora variedade limitada; não implementa geração livre irrestrita.
- Saída: fatos vêm literalmente do GroundingPolicy; todas as respostas, incluindo apresentação e fallback, são validadas por AssistantResponse e permanecem sujeitas à barreira HTTP existente. Valores financeiros não entram nas opções consultivas.

A política seleciona exploração da rotina ou esclarecimento de objeção; consultas/fotos mantêm as ações explicar/apresentar do grafo; intenção explícita de compra/visita oferece encaminhamento com autorização. A antiga sequência obrigatória de perguntas foi removida. Perguntas têm chaves persistidas e não são repetidas automaticamente. A distância diária pode gerar apenas reconhecimento, sem pergunta final.

O estado existente agora inclui contextos de uso simultâneos, primeira experiência elétrica, distância diária, motivo categórico do contato e estágio comercial. Não se armazena texto bruto como motivo. Nome preferido, apresentação realizada, perguntas anteriores, seleção canônica e consentimento reutilizam campos existentes. Dados privados continuam separados do resultado público e da projeção enviada ao modelo.

## Identidade e abertura

Lia se identifica como assistente virtual de IA de pré-vendas Leapmotor uma vez por conversa. Saudação simples pergunta como a pessoa prefere ser chamada. Pergunta técnica inicial é respondida antes da pergunta opcional de nome; a apresentação não exige dados. Modelos e motorizações são reconhecidos desde o primeiro turno. Nome voluntário, inclusive junto de pergunta técnica, não é solicitado novamente; nome e recusa não provocam repetição da seleção já conhecida.

O nome não é repetido em todos os turnos e não constitui consentimento de CRM. Entradas e histórico com nome são omitidos do contexto do modelo; coleta de telefone e preparação de contato continuam dependentes de autorização. Fotos continuam filtradas por aprovação e veículo, com prevenção de repetição das buscas gerais. Nenhum registro foi aprovado ou publicado.

## Avaliação qualitativa das transcrições

- **Reconhecimento de contexto:** Uber é uso profissional; família é contexto adicional; primeira experiência elétrica e recarga são esclarecimentos, não afirmações técnicas inventadas.
- **Relevância comercial:** pergunta de distância diária substitui encaminhamento sem propósito; família explora passageiros/bagagem; recarga explora possibilidade de carregar em casa/trabalho.
- **Naturalidade e perguntas:** não há formulário sequencial; perguntas respondem a sinais concretos. A qualidade subjetiva ainda precisa de avaliação humana independente.
- **Fundamentação:** autonomia revisada mantém sua fonte. Sem detalhes de recarga, o agente explicita a lacuna e ainda pode explorar a rotina. Não promete economia, rentabilidade ou categoria de aplicativo.
- **Continuidade:** relato de uso não dispara ausência de especificação; mudança de modelo atualiza fotos; recusa de vendedor é respeitada.
- **Qualificação:** uso, distância, prioridades e intenção espontânea passam a compor o estado; visita/compra levam à oferta de encaminhamento, sem envio externo.

O caso Uber foi reproduzido literalmente. A jornada adicional de família/primeiro elétrico/recarga/troca/visita/recusa e as aberturas foram sintetizadas dos cenários solicitados. O pedido anterior mencionava dois atendimentos, mas apenas um veio transcrito integralmente nessa solicitação; não se afirma ter reconstruído uma segunda conversa real ausente.

## Gates e evidências

```bash
PYTHONPATH=. python3 -B scripts/evaluate_conversation.py --scenario sdr --output docs/evaluations/sdr-after.json
python3 -B -m pytest -q -p no:cacheprovider --tb=short
ruff check app tests scripts/evaluate_conversation.py --no-cache
python3 -m compileall -q app tests scripts/evaluate_conversation.py
git diff --check
```

Resultado: **135 testes passaram**, Ruff, compilação e diff check passaram. Permanece um aviso upstream LangChainPendingDeprecationWarning. Regressões existentes de mídia, importador, grounding, isolamento, política comercial e HTTP continuam executadas. Os testes de expectativas textuais foram ajustados somente para a identidade e a nova pergunta contextual, mantendo fontes, fatos e proteção comercial.

Novas regressões cobrem: caso Uber completo, família, primeiro elétrico, recarga, mudança de veículo, visita, recusa, compra com prazo espontâneo, nome voluntário, recusa do nome, retorno à conversa, nome junto de pergunta técnica, uma pergunta por turno e fallback para saída financeira maliciosa ou timeout do modelo. A contagem das chamadas consultivas é persistida mesmo em fallback.

Nenhuma inferência paga foi realizada. Tokens retornados como zero pelo simulador não medem custo real; latência, qualidade Groq e conversão comercial não foram avaliadas. Não houve envio externo, reinício do chat em execução, merge, push ou deploy.

## Limitações e próximos passos

As formulações consultivas são deliberadamente limitadas e o reconhecimento é lexical: paráfrases, negações complexas, correções de intenção e distâncias implícitas precisam de avaliações adicionais. Histórico e contatos continuam na memória local do processo, com as limitações de retenção já documentadas. Aprovação e completude do catálogo continuam condicionando afirmações técnicas.

Recomenda-se avaliação humana do atendimento e, somente com autorização, piloto limitado com Groq real. A cobertura determinística não constitui aprovação de segurança adversarial ampla nem comprovação de encantamento ou conversão.

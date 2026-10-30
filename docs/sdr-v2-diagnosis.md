# SDR v2 — diagnóstico antes da ampliação

Baseline: `8b833c2`, 2026-10-30. O workspace já contém a correção em andamento para viagem/economia e sua regressão; ela será preservada.

Fluxo: rotas autenticadas web/API → SalesAgent.turn (memória por owner/conversa e lock) → LangGraph consult/guard/select/tools/compose/output → AssistantResponse → barreira HTTP. Não há segundo agente.

Causas comprovadas:
- `observe` reconhecia “viagens” e “viajar”, mas não “viagem”. O teste reproduzindo o print falhou antes da correção: `handoff_required=True`, texto de confirmação por consultor. A correção local já faz essa regressão passar.
- Respostas curtas sobre distância e acesso à recarga não eram incorporadas em todos os contextos; podiam voltar à busca técnica sem fatos.
- O compositor usa fallback rígido quando faltam fatos técnicos, mesmo quando o cliente estava informando uso. A frase citada pelo usuário estava nesse caminho.
- Intenção de visita ou compra e pedidos financeiros iniciavam oferta de contato automaticamente. Isso conflita com a nova regra explícita: encaminhamento somente por pedido do cliente.
- Apresentação visual ainda chama `next_question` automaticamente. A galeria objetiva pode ser mais útil sem pergunta.
- A composição consultiva permite ao LLM escolher somente entre formulações autorizadas. Isso protege fatos, mas limita variedade e compreensão semântica. Esse limite continuará explícito; snapshots não comprovam fluência.
- Identidade, fontes, aprovação de mídia e isolamento já têm mecanismos existentes. CommercialPolicyEngine e barreira HTTP serão preservados.

Escopo: ações SDR contextuais, não sequenciais; memória de viagem/recarga; saídas sem encaminhamento automático; handoff com solicitação explícita e consentimento; testes completos com modelo simulado. Sem chamadas Groq reais, reinício, deploy, merge ou push nesta execução.

# Próxima iteração — qualidade de atendimento

Checkpoint: 2026-11-02. WhatsApp funcional confirmado pelo usuário; transporte não equivale a aprovação da experiência comercial.

## Ordem proposta

1. **Medir o atendimento atual.** Criar transcrições sintéticas completas e avaliação por reconhecimento contextual, continuidade, repetição, iniciativa, grounding, consentimento e segurança. Incluir nome lembrado após reinício, B10 ambíguo → REEV/BEV, fotos, reações sociais, Uber, família, recarga, mudança de modelo, preço e recusa de contato. Não usar conversas reais como fixtures sem autorização.
2. **Melhorar o perfil de atendimento no mesmo LangGraph.** Revisar roteamento intenção social/técnica/necessidade, contexto compacto e composição pelo modelo. Entregar valor antes de perguntas secundárias, no máximo uma pergunta útil, sem nome ou fotos repetidos. Consultor somente sob pedido explícito; consentimento antes de encaminhamento com dados pessoais. Não trocar a política independente por prompt.
3. **Comparar modelos Groq.** Manter adapter configurável, registrar modelo, chamadas, tokens, latência, timeouts e custo quando disponível. Selecionar candidatos do catálogo vigente na execução; nenhum modelo novo foi escolhido aqui. Rodar mocks primeiro e comparar com orçamento explícito de chamadas reais autorizado pelo usuário. Melhorar fluidez não justifica inventar benefícios técnicos ou financeiros.
4. **Decidir sobre orquestração.** Já existe LangGraph: aperfeiçoar a seleção de próxima ação e ferramentas dentro dele. Só adicionar componente orquestrador se avaliações demonstrarem falha que a estrutura atual não resolve; não criar outro agente/grafo por padrão.
5. **RAG somente se necessário.** Primeiro ampliar e aprovar catálogo estruturado. Recuperação documental versionada pode complementar lacunas técnicas, com fontes, aprovação, abstinência e proteção contra prompt injection. Catálogo continua prioritário; não enviar manuais completos ao modelo. Valores financeiros em documentos devem permanecer inacessíveis ao contexto/saída.

## Critérios para concluir a próxima entrega

- Transcrições antes/depois e avaliação comportamental, não apenas snapshots de frases.
- Nenhum valor financeiro, afirmação sem evidência ou handoff não solicitado.
- Nome e contexto isolados por remetente; exclusão local e reinício testados.
- Ferramentas restritas, fontes rastreáveis e mídia aprovada sem repetição indevida.
- Pytest, Ruff, compilação e diff check reais; smoke de WhatsApp separado de testes determinísticos.
- Relatório de falhas e métricas; não prometer ausência total de erros.

## Operação a endurecer

- Investigar causa raiz de `conflict: replaced`; monitorar reconexão, saúde de sessão e falhas de envio com códigos sanitizados.
- Painel/ferramenta de revisão de outbox incerta, sem reenvio automático.
- Modo aberto exige limites globais de consumo/concorrência além dos 40 eventos por pessoa/dia existentes. Atualmente não há orçamento global de inferência.
- Ampliar avaliação adversarial e validar retenção, backup/restore e acesso a dados antes de expansão.

Sem envio ao Syonet, mudança de modelo, nova recuperação documental ou integração adicional implementados neste checkpoint.

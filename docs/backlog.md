# Backlog priorizado — pré-vendas Leapmotor

## P0 — validar catálogo e ferramentas (escopo atual)

1. Pipeline de extração para rascunhos comerciais e inventário de mídias; guardar URL, captura, hash, data e proveniência. Valores não aprovados não aparecem nas ferramentas.
2. Confirmar ficha oficial atual de C10/B10, versões/ano-modelo, autonomia/ciclo, cores e equipamentos; executar revisão humana com trilha de aprovação.
3. Resolver direitos de uso e localização/storage para cada mídia antes de permitir envio. Não converter imagens para payload base64.
4. Validar schemas e ferramentas determinísticas com fixtures: catálogo, filtros de mídia, ofertas vigentes, autorização e idempotência.
5. Obter contrato de qualificação, campos mínimos/base legal/consentimento e sandbox Syonet. CRM permanece bloqueado enquanto pendente.

## P1 — experiência de pré-venda

6. Implementar estado de conversa comercial que aproveita dados já fornecidos e faz no máximo uma pergunta útil por turno.
7. Orquestrar ferramentas com LangGraph; consulta ao catálogo antes de RAG técnico e sem chamar RAG quando catálogo basta.
8. Integrar Evolution API com envio de texto e media por URL/arquivo permitido, webhooks autenticados e dedupe.
9. Adaptador Syonet com outbox, confirmação de consentimento, chave idempotente e retries seguros.
10. Handoff humano com resumo de intenção, veículo e pendências já coletadas.

## P2 — canais e operação

11. Widget React incorporável e painel operacional/revisão do catálogo e mídias com RBAC/auditoria.
12. Observabilidade sem PII, métricas de conversão/qualidade, evals e testes de regressão adversarial.
13. Política LGPD de retenção/exclusão, segurança de sessão/tenant, load tests, backup/restore e runbooks.
14. Piloto por loja com fontes locais de preço/estoque, critérios go/no-go, rollback e monitoramento.

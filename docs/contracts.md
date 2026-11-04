# Contratos de API e ferramentas

## Convenções

JSON UTF-8; IDs UUID; timestamps ISO-8601 UTC. Erros usam `{ "code": "...", "message": "...", "request_id": "..." }`; payloads não ecoam tokens nem dados sensíveis. Requisições mutáveis aceitam `Idempotency-Key`. Versão pública inicial: `/v1`.

## API proposta

- `POST /v1/conversations`: cria sessão vinculada a canal; widget recebe token de sessão aleatório, escopado e expirável.
- `POST /v1/conversations/{id}/messages`: recebe texto e ID único do cliente; resposta pode indicar `grounded`, `insufficient_evidence` ou `handoff`.
- `POST /hooks/evolution/{instance}`: webhook máquina-a-máquina autenticado por `X-Webhook-Secret`; persiste inbox e deduplica IDs, retornando apenas `queued`, `duplicate` ou `ignored`.
- `GET /v1/conversations/{id}`: histórico autorizado, redigido segundo política de PII.
- `POST /v1/conversations/{id}/handoff`: abre/atualiza pedido de atendimento humano.
- `POST /v1/leads/{id}/authorize-crm`: grava consentimento explícito, escopo e timestamp; não envia conteúdo oculto.
- `GET /health/live`, `GET /health/ready`: probes operacionais.

## Resposta conversacional

```json
{
  "message_id": "uuid",
  "status": "answered",
  "answer": {
    "text": "Podemos explorar as informações verificadas do veículo.",
    "confidence": "insufficient_evidence",
    "source_ids": [],
    "handoff_required": true
  }
}
```

Valores de status: `answered`, `abstained`, `handoff`. Respostas sobre preço, estoque, prazo ou garantia exigem fonte autorizada atualizada; sem ela o agente deve se abster. Citações referem IDs/versionamento visíveis para o operador.

## Ferramentas do agente comercial (allowlist)

1. `list_vehicles(model?, powertrain?)` — somente registros de catálogo aprovados.
2. `get_vehicle_details(vehicle_id)` — especificações, diferenciais, itens de série, cores e fontes da versão aprovada.
3. `search_vehicle_media(vehicle_id, version?, model_year?, color?, category?)` — somente assets aprovados, direitos documentados e local de armazenamento presente; devolve metadados/URI, nunca bytes/base64.
4. `compare_vehicles(vehicle_ids[2..4])` — comparação determinística de campos aprovados; ausências ficam explicitamente ausentes.
5. `qualify_lead(fields)` — retorna campos mínimos ausentes e autorização derivada de consentimento registrado.
6. `create_syonet_lead(lead_id, consent_id, idempotency_key)` — efeito externo bloqueado sem dados mínimos, consentimento verificado no servidor e adapter configurado; serve somente para encaminhar oportunidade autorizada.
7. `handoff_to_human(conversation_id, reason, summary)` — abre encaminhamento interno e preserva contexto já coletado.

Recuperação de manuais técnicos é uma ferramenta separada, chamada apenas se o catálogo comercial não contiver a resposta. Mensagens e dados não confiáveis não alteram instruções do sistema. O agente deve manter slots preenchidos na memória e não repetir perguntas respondidas.

### Política comercial obrigatória

Não existe `get_commercial_offer` na superfície de ferramentas do agente. Nenhum preço, parcela, taxa, desconto, promoção, condição de pagamento ou valor de avaliação de usado pode ser informado. O agente não negocia, reserva nem conclui vendas. Dados financeiros eventualmente mantidos em estruturas internas não podem ser serializados ao contexto do modelo. Solicitações diretas/indiretas ou instruções injetadas recebem resposta segura oferecendo apresentação de características e encaminhamento a consultor. A saída final passa por validação determinística independente do LLM.

O modelo não recebe ferramentas genéricas HTTP/SQL, não escolhe endpoint/headers e não pode fabricar `consent_id`. Todas as chamadas são auditadas sem registrar prompt/PII bruto em logs comuns.

## Configuração do payload Syonet

Contrato JSON configurável validado em startup, com campos mapeados a allowlist, required, tipos e transformação. Rejeita propriedades desconhecidas e dados além do consentimento. Falha fechada se ausente/inválido. Upsert usa chave estável/idempotency key; timeout finito, retry apenas para falhas transitórias e sem duplicar oportunidades.


## Lia v3 — contrato interno em avaliação

`ConversationPlan` separa intenção, perguntas opcionais e fatos revisados de `ConversationDraft` (`text`, `fact_ids`, `question`). Fontes e mídias permanecem server-owned. `InterpretedIntent` é uma dica semântica com categoria `other`, sem autoridade de consentimento ou ações. Texto e transcrição usam o mesmo `SalesAgent.turn`; voz é opt-in e responde somente texto. [Contratos, limites e ativação](lia-v3.md).

### Oportunidade e visita local

O plano `purchase` trata decisão de compra/visita sem conceder ações externas. `LeadProfile` e a oportunidade `local_only` acrescentam `trade_in_interest: bool | null` e `visit_preference: str | null`. A preferência é informação declarada, nunca reserva ou agendamento confirmado. Nome e veículo canônico continuam vinculados à identidade persistida do contato. Convite para conhecer o carro não implica consentimento para contato humano; handoff mantém pedido explícito e autorização. [Comportamento e evidências](lia-store-visit.md).

### Conhecimento técnico e referências de opção

`ReviewedTextFact` e a introdução institucional possuem revisão explícita, fonte e digest. Somente a projeção pública de fatos aprovados chega à composição; o modelo não aprova documentos. `offered_vehicle_ids` guarda IDs ordenados no estado da mesma conversa; referências ordinais não podem selecionar itens fora dessa oferta. A linguagem de apresentação pode usar elétrico/ultra-híbrido, preservando as chaves BEV/REEV internamente. [Fontes, evidências e limites](knowledge-expansion.md).

### Especialistas internos da Lia (opt-in)

`RouteHint` contém ato, tópico e evidência opcional de rotina, sem ferramentas, consentimento ou destinatário. O backend deriva `reception`, `sales` ou `knowledge` e verifica o conjunto de ferramentas antes da execução. Todos compartilham o estado e a validação de saída; o formato público AssistantResponse permanece inalterado. `active_specialist` e resumo de roteamento são privados. `LIA_ORCHESTRATION_ENABLED=false` preserva o modo atual até avaliação. [Responsabilidades, grafo e limitações](lia-internal-specialists.md).

## Lia V2 — transferência local autorizada

`app/handoff/service.py` define `HandoffContract`, `HandoffDispatcher` e `DeliveryReceipt`. Consentimento persistido e dados mínimos são obrigatórios; destinos não são argumentos de ferramenta do LLM. Os estados `prepared`, `queued`, `delivered`, `failed` e `acknowledged` são independentes do estado conversacional. O adapter local só retorna `queued`. Recibo de entrega exige identificador externo; testes de entrega usam adapter sintético. Não existe novo endpoint público para despacho/confirmação. Veja o [contrato e ciclo completos](lia-v2/README.md).

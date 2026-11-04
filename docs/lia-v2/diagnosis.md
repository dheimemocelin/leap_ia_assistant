# Lia V2 — diagnóstico antes da implementação

## Versão inspecionada

Serviço `leap-pilot.service` ativo, WorkingDirectory `/home/ubuntu/.t3/projects/leap-ia-assistant`, branch `deploy/lia-typing-8416720`, commit `8416720`. Desenvolvimento em worktree separado, branch `feat/lia-v2-lifecycle`, baseada na entrega de apresentação `1495ef3`. Nenhuma alteração no serviço ou banco operacional.

## Defeitos reproduzidos

`python3 -m pytest tests/unit/test_lia_v2.py -q`: **4 falhas**, antes da implementação. Fixtures sintéticas e LLM simulado.

1. `SalesAgent.tools()` remove `shown_media_ids` quando não há ângulo/cor. Não diferencia pedido de repetição; `compose()` mantém somente o conjunto acumulado, sem última galeria associada ao veículo. “Manda novamente” não repete a galeria anterior.
2. `PilotStore` guarda nome no cadastro e perfil no thread, mas não distingue sessão encerrada/nova sessão. `reset_thread()` elimina todo o contexto, preservando apenas nome. Não há motivo/data do encerramento.
3. `route()`/`ReceptionSpecialist.handle()`/`consult()` não possuem tratamento de pausa/despedida. “Depois eu vejo” não resulta em estado PAUSED verificável.
4. “Quero continuar” retorna “Estou acompanhando o que você está contando. Pode seguir no seu ritmo.”, sem retomar B10 selecionado. Não consulta dados técnicos nesse caso, mas perde pertinência conversacional.

## Pontos diretamente relacionados

- `service.py`: `turn()` persiste uma lista fechada de campos; `output()` reapresenta somente via `greeted`, não via ciclo de sessões, e elimina referências a consultor quando não existe solicitação explícita.
- `consultative.py`: nome e consentimento progressivos já implementados. `collect_contact()` informa corretamente `prepared_not_sent`; não há dispatcher, entrega, confirmação nem idempotência de transferência.
- `composition.py`: redação pelo LLM com evidências/validação; não substituir esse mecanismo por um novo agente. Lifecycle, consentimento e recibos são decisões determinísticas.
- `specialists.py`: saudação no modo comercial ignora nome do contato recorrente; referências abertas dependem de interpretação sem uma retomada explícita.
- `CommercialPolicyEngine` e barreira `AssistantResponse` são preservados; não há necessidade de modificar regras financeiras.
- `EvolutionWorker`: identifica pessoa por instância/contato já normalizados no webhook, reusa memória e inbox/outbox. Marca foto como apresentada antes da entrega, mas não registra mídia efetivamente entregue na memória. Envio parcial vai para revisão; não existe envio exatamente uma vez garantido pelo provedor.

## Escopo mínimo

Adicionar ciclo de sessões e estados comerciais ao mesmo grafo, memória persistente do cliente separada dos registros de sessão, reenvio explícito aprovado e dispatcher de transferência local com estados verificáveis. Ativação opt-in de V2; nenhuma integração externa ou migração em produção. Avaliações com simulador não comprovam naturalidade geral do Groq.

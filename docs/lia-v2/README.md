# Lia V2 — continuidade, sessões e transferência controlada

**Entrega de desenvolvimento, opt-in. Não ativada no serviço de WhatsApp.** Mesmo LangGraph, Groq, catálogo, ferramentas e banco SQLite. Sem novo agente, serviço externo ou dependência adicionada.

Veja o [diagnóstico com quatro falhas reproduzidas](diagnosis.md), as [conversas comparativas](conversations.md), as [transcrições executadas](transcripts.json) e o [relatório de gates](validation.md).

## Separação de estados

| Dimensão | Campo / armazenamento | Significado |
| --- | --- | --- |
| Cliente persistente | `pilot_people.display_name`, `profile_json`, `updated_at` | Nome confirmado, veículo, preferências, contexto resumido e última interação. A chave opaca do webhook já considera instância e contato. |
| Thread / canal | `pilot_threads` | Owner isolado e conversa por pessoa/canal. O identificador HTTP não precisa mudar a cada sessão. |
| Sessão | `conversation_session`, `pilot_sessions` | Identificador próprio, abertura, última interação, término, motivo e sessão anterior. |
| Estado comercial | `commercial_state` | DISCOVERY, EXPLORING, INTERESTED, AWAITING_CONSENT, HANDOFF_PENDING, HANDOFF_CONFIRMED, PAUSED, CLOSED. |
| Temperatura | `lead_profile.temperature` | Frio/morno/quente, pelos critérios observáveis anteriores; não exibida ao cliente. |
| Transferência | `pilot_handoffs` | Contrato autorizado, entrega e idempotência. Não representa a sessão nem a temperatura. |

O campo legado `commercial_stage` permanece para compatibilidade. A dimensão explícita V2 é `commercial_state`.

## Ciclo de sessões

| Situação | Transição | Efeito |
| --- | --- | --- |
| Primeiro contato | → ACTIVE | Apresenta Lia uma vez; nome opcional, sem bloquear pedido direto. |
| “Vou pensar” / “Depois eu vejo” | ACTIVE → PAUSED | Registra motivo e data, despedida sem insistência nem nova pergunta. |
| Despedida / desinteresse | ACTIVE → CLOSED | Preserva memória permitida, sem follow-up automático. |
| Inatividade configurada | ACTIVE → PAUSED → ACTIVE na próxima entrada | Arquiva a sessão anterior; não envia mensagem por timer. |
| Retorno após pausa/encerramento | PAUSED/CLOSED → nova ACTIVE | Novo ID de sessão, mesmo cliente, veículo e preferências. Saudação conhecida usa nome confirmado e pergunta o motivo atual, sem sugerir automaticamente o carro anterior; pedido direto segue para sua resposta. |
| Resumo autorizado preparado ou em fila | → HANDOFF_PENDING | Não afirma recebimento humano. Cliente pode continuar conversando. |
| Recibo de entrega válido | → TRANSFERRED | HANDOFF_CONFIRMED no estado comercial; worker deixa de responder automaticamente. |
| “Voltar para Lia” | TRANSFERRED → ACTIVE | Retoma somente mediante pedido explícito; não reenvia automaticamente a transferência anterior. |

Um “obrigado” com pergunta seguinte não encerra o atendimento. Agradecimento isolado com pergunta pendente não força encerramento. Recusa de vendedor/visita é tratada no seu contexto, sem equivaler automaticamente a desinteresse no veículo.

A apresentação personalizada usa o nome guardado pelo servidor, nunca um nome inventado pelo modelo. O LLM continua responsável pela redação conversacional e pode redigir despedidas; a aplicação rejeita perguntas/pressão no encerramento e mantém fallback breve. Interpretação de paráfrases de despedida ainda tem cobertura limitada e exige avaliação humana.

## Memória e privacidade

Migração aditiva e idempotente: `profile_json` em `pilot_people`, tabelas `pilot_sessions` e `pilot_handoffs`. Nenhuma migração foi executada em produção. Dados CRM e consentimento não são copiados para a memória compacta do cliente; as informações da transferência ficam no contrato autorizado.

A política existente de retenção de **30 dias** permanece. Encerrar sessão não apaga a memória; exclusão solicitada ou expiração de retenção apaga o cadastro e seus dependentes. Reconhecimento não é prometido após expiração. O teste de retorno com relógio avançado avalia a lógica da sessão, não prorroga a retenção.

Exclusão pelo WhatsApp reutiliza o comando existente `Apagar meus dados`: remove também sessões e contratos locais, limpa conteúdo da inbox/outbox e conserva apenas tombstones de deduplicação. Não apaga mensagens do aparelho, backups anteriores ou dados já enviados a um eventual sistema externo. Esse último fluxo depende de integração futura.

## Fotos: proposta, seleção e entrega

- `shown_media_ids`: conjunto utilizado para evitar galeria repetitiva espontânea.
- `last_shown_media_ids` + `last_media_vehicle_id`: última seleção proposta, vinculada ao veículo canônico.
- `last_delivered_media_ids` + `media_delivery_status`: aceites de envio efetivamente observados pelo worker; não equivalem a leitura no aparelho.
- “Manda novamente”, “Mostra de novo”, “Cadê?” e “Cadê aquela foto?” podem repetir a galeria anterior, revalidando aprovação e associação.
- “Tem outra foto?” procura material ainda não mostrado. Se não houver, não inventa outra imagem.
- Categoria/ângulo continuam usando a biblioteca determinística existente. Aprovação de mídia e veículo é verificada novamente; o worker preserva verificação de arquivo, tamanho, MIME e SHA-256.
- O texto diz que separou fotos para mostrar, sem afirmar entrega concluída. Falha/timeout gera estado de revisão; não há reenvio automático de partes incertas. Novo pedido explícito é uma nova intenção de envio.

## Transferência: contrato e autoridade

`app/handoff/service.py` define `HandoffContract`, `HandoffDispatcher`, `DeliveryReceipt` e `LocalHandoffDispatcher`.

O contrato contém ID da oportunidade, modelo/motorização, necessidades, uso, motivo, resumo, nome e telefone autorizados, consentimento com data/escopo, status, identificador externo e chave de idempotência. A chave deriva de owner + conversa + data do consentimento, nunca de argumentos do LLM. Mudança de veículo revoga o escopo em uso e impede novo despacho do registro antigo; fila externa futura também deverá respeitar revogação.

A intenção clara pode gerar **oferta**, uma vez, sem transferência: aceitar falar com consultor ainda leva a uma solicitação explícita de consentimento para compartilhar nome, telefone e interesse. Recusa é respeitada. Pedido direto de consultor usa a mesma autorização anterior. Conversar sobre compra ou pedir preço não representa consentimento.

O serviço confere o perfil persistido, os dados mínimos e a mesma autorização no snapshot antes de preparar/despachar. Não há URLs, destinos, callback de confirmação ou ferramenta de escrita controlados pelo modelo. Nenhuma API pública de confirmação foi criada.

| Status | Evidência necessária | Resposta da Lia |
| --- | --- | --- |
| prepared | Registro persistido com autorização | Preparado, ainda não enviado. |
| queued | Adapter local devolveu fila; ou tentativa reclamada em curso/incerta | Fila local, recebimento humano não confirmado. |
| delivered | Adapter autorizado retorna recibo com ID externo | Confirma recebimento pelo canal e pausa o bot. |
| failed | Falha/timeout ou recibo inválido | Não confirma entrega; conversa pode continuar. |
| acknowledged | Confirmação operacional após delivered, via método interno | Continuidade humana confirmada. |

Registro e claim SQLite são transacionais. A mesma chave não é despachada duas vezes, inclusive em submissões concorrentes. Exceção/timeout não causa retry automático; requer investigação. Um crash após claim fica queued e incerto, sem supor sucesso nem reenviar cegamente. Não há garantia de entrega exatamente uma vez em provedor futuro.

O modo local **somente coloca em fila**. `delivered`/`acknowledged` foram exercitados com adapter sintético, não com vendedor real. A configuração distribuída não contém adapter de CRM, fila externa ou entrega por WhatsApp a consultores. Um adapter futuro exige configuração/autorização de destino, recibos confiáveis e autenticação do operador antes de habilitar confirmações externas.

Revogar consentimento remove os dados pessoais do contrato local e bloqueia novo claim. Não significa retirar uma mensagem já entregue a um serviço externo.

## Configuração de desenvolvimento

```dotenv
LIA_CONVERSATION_V2_ENABLED=true
LIA_SESSION_INACTIVITY_SECONDS=3600
LIA_HANDOFF_MODE=local
```

Padrões: V2 desativada, inatividade 1h e handoff `disabled`. `disabled` prepara somente; `local` registra fila. Não há opção de envio externo nesta entrega. A flag independe da ativação do RAG e não substitui o fluxo comercial existente.

Validação realizada com fixtures sintéticas em bancos temporários. Não alterar `.env` do piloto nem reiniciar o serviço para experimentar sem aprovação. Instalar a versão não basta para ativar V2: a flag também precisa ser configurada.

## Métricas e limites

Por turno: estado de sessão/comercial, reabertura, origem de composição, fallback, perguntas consecutivas, ferramentas, tokens e latência já existentes. Sem nome/telefone/texto em logs operacionais. Métodos internos `handoff_metrics()` e `conversion_metrics()` retornam contagens agregadas de status, oportunidades e interesse em visita, sem alegar conversão em vendas.

As transcrições usam o grafo completo com LLM simulado, antes/depois da flag, e incluem métricas mecânicas. Não medem naturalidade humana, eficácia comercial, conversão real ou qualidade do Groq. Atendimento vivo, recibos reais e observação de mídia no aparelho permanecem pendentes. Sem deploy, merge, push, WhatsApp/Syonet real, inferência paga ou mudança na política comercial.

## Ajuste de abertura após inatividade

Após 1h sem mensagens, a próxima entrada pode abrir nova sessão também quando o encaminhamento estiver apenas preparado/em fila, sem recebimento humano confirmado. Nome e interesse ficam preservados, mas um “Oi” recebe uma abertura sobre a necessidade de hoje, sem convite automático para continuar o carro anterior. Retomadas explícitas continuam recuperando o interesse. Transferência confirmada não expira para liberar o bot. Nenhuma despedida é enviada por timer.

Validação do ajuste: dois testes de intervalo de 2h falharam antes da correção (ACTIVE e HANDOFF_PENDING); após o ajuste, a suíte completa passou em **558 testes**, com Ruff, compilação e diff aprovados. A expectativa antiga de mencionar o B10 na saudação de retorno foi substituída por verificação de abertura neutra, mantendo a verificação do interesse persistido. Saudações também não forçam assunto anterior dentro de sessão ativa. Não houve inferência paga.

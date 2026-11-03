# Indicador de digitação e continuidade comercial

Base: `b138269`, branch `fix/lia-typing-and-context`.

## Indicador nativo

Inspecionamos a implementação da imagem instalada `evoapicloud/evolution-api:v2.3.7`.
`textMessage` encaminha o campo `delay` ao método `sendMessageWithTyping` com presença
`composing`. Usamos o próprio POST autenticado `/message/sendText/{instance}`;
não há outro agente, endpoint de envio, tarefa de presença contínua ou chamada LLM.
O contrato do SDK oficial também documenta delay em milissegundos e presença:
https://github.com/evolution-foundation/evolution-client-python

`EVOLUTION_TYPING_DELAY_MS` aceita 0..2000, padrão 0. O piloto usa **1200ms**. A
configuração é exclusivamente do servidor; destinatário continua vindo da entrada
validada, e a resposta passa pela validação comercial antes do envio. Não há espera
artificial longa. Não introduzimos retries adicionais nem reenvio de entregas
incertas. Mensagens com envio desativado não geram chamadas de digitação.

É uma indicação curta **antes de entregar o texto**, não uma presença contínua durante
toda a inferência. A renderização visual depende do cliente WhatsApp e deve ser
confirmada pelo usuário. Não enviamos mensagens reais para validar a aparência.
A Lia continua identificada como assistente virtual.

## Erros de conversa reproduzidos

Dois testes inicialmente falharam:

- “Então quero trabalhar e economizar”: uso e necessidade já eram reconhecidos no
  estado, mas a resposta virava uma solicitação genérica. O fallback do acolhimento
  descartava a ação consultiva determinística quando o classificador falhava.
- “Ele faz quanto com litro?” após B10 BEV: não explicava a diferença entre consumo
  de combustível e autonomia elétrica.

A correção reconhece a intenção de uso e preserva a ação já identificada quando
há falha de classificação, sem provocar outro timeout apenas para redação. A
explicação de unidades exige seleção canônica aprovada e usa a autonomia publicada
com fonte. Não converte autonomia em km/l e não promete economia ou rentabilidade.
Litros do porta-malas continuam sendo volume de bagagem, não combustível.

“Quero saber mais sobre os veículos” passa a listar o catálogo aprovado sem exigir
modelo/motorização de quem ainda não conhece os carros. Contexto, nome, mídia,
loja, consentimento e proibições comerciais anteriores são preservados.

## Evidências

Testes determinísticos cobrem contrato autenticado do delay, limites, contexto de
trabalho/economia, necessidade familiar com classificador indisponível, autonomia
BEV por carga, porta-malas em litros e apresentação geral de veículos. Não há nova
dependência nem avaliação paga. Os testes não comprovam naturalidade geral do Groq.

Ativação no mesmo piloto: backup privado de configuração/SQLite, checkout do commit
validado, `EVOLUTION_TYPING_DELAY_MS=1200`, reinício curto e health/connection checks.
RAG permanece desligado e o foco comercial continua ativo. Sem merge/push ou
mensagem manual de teste.

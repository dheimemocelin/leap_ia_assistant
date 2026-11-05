# Finalização da qualificação de visita

Base `2677791`. O print mostrou preferência por quinta às 10h e resposta “Pode agendar, não tenho carro”, seguida de retorno genérico à descoberta.

## Reprodução e correção

Dois testes inicialmente falharam: o parser descartava `10h` e a ausência de veículo na troca levava a uma nova pergunta de prioridade. Não era falha de envio: eram perda de informação e decisão conversacional inadequada.

O parser agora preserva horários válidos como `10h` e `14:30` → `14h30`, associados à preferência de dia/período. Não infere uma data de calendário a partir de “quinta” e não presume funcionamento da loja naquele horário.

O plano `visit_wrapup` no mesmo grafo reconhece a conclusão da descoberta necessária para a visita. Dados da troca são opcionais: pedido explícito para agendar pode concluir essa etapa sem forçar resposta sobre veículo atual. Não se inventa ausência ou presença de um usado.

O LLM pode formular um acolhimento breve, sem nova pergunta. Afirmações de agendamento e retorno genérico à descoberta são rejeitados; preferência, condição da troca e status real são renderizados pelo backend. O horário não depende da redação livre do modelo. A validação comercial permanece intacta.

`visit_booking_status` distingue `not_requested`, `preference_recorded` e `confirmation_required`. **Não existe estado confirmado nem integração de agenda nessa entrega.** Oportunidades guardam o campo; novos contratos autorizados de handoff podem carregar preferência e status. Nada é compartilhado sem autorização.

Depois do registro, `pending_question` é limpo e a próxima ação é aguardar confirmação de visita. A sessão não é encerrada à força: o cliente pode perguntar mais; “obrigado” isolado permite fechamento natural, sem insistência. Nenhuma mensagem adicional é enviada automaticamente.

## Evidências

- **575 testes passaram** na suíte completa com dependências opcionais já existentes localmente.
- Cinco casos novos: reprodução integral, fim da qualificação, tentativa de confirmação falsa pelo modelo, preferência com minutos e avaliação presencial de usado, e pedido de agendamento sem resposta à pergunta opcional de troca.
- Ruff, compilação Python e `git diff --check`: aprovados.
- [Conversa executada com simulador](visit-wrapup-evidence.json). Os fallbacks são registrados como tal, não como redação bem-sucedida do LLM.
- Nenhuma API paga, reserva, contato com vendedor ou agenda externa foi chamada.

## Limites

Registrar uma preferência não confirma uma visita. A confirmação real depende da equipe/agenda autorizada da loja, ainda não integrada. O cliente recebe essa limitação explicitamente. Naturalidade do Groq não foi reavaliada com chamadas pagas; permanece necessária validação no piloto.

# Piloto comercial — entrega focada em vendas

Branch `fix/lia-sales-delivery`, base `2acd07d`. Mesmo LangGraph, Groq, memória,
catálogo, mídia e política comercial. A flag `LIA_SALES_FOCUS_ENABLED` preserva o
comportamento anterior quando desativada. O piloto comercial desativa temporariamente
`LIA_KNOWLEDGE_ENABLED`; a infraestrutura RAG permanece versionada para retomada.

## Problemas reproduzidos e correção

Antes da alteração, cinco dos seis cenários iniciais falharam: relato de defeito
recebia reconhecimento genérico; abertura não tinha um objetivo comercial único;
valor/nome/uso não avançavam corretamente; troca podia perder a orientação presencial;
pergunta financeira não mantinha a direção para visita. O erro específico de busca
visto no WhatsApp não teve sua exceção original recuperada; não afirmamos ter
comprovado a causa daquele evento. Acrescentamos registro do tipo da exceção sem
mensagem de cliente, argumentos ou credenciais.

- Abertura curta, identificada como virtual, com uma pergunta. Sem LLM nesse passo.
- Modelos canônicos informados diretamente não dependem de classificação ambígua.
- Fotos aprovadas são apresentadas antes de solicitar nome, sem empilhar uma ficha
  técnica na primeira galeria. Nome é opcional, perguntado uma vez e persistido.
- Uso e reação positiva permitem convite contextual à loja, sem funil obrigatório.
- Interesse em visita e preferência de período são anotados; não confirmam agenda.
- Troca recebe orientação de avaliação presencial, sem promessa de aceitação,
  valorização ou valores. Recusas não se transformam em novas ofertas insistentes.
- Pedidos financeiros continuam sem valores e sem handoff automático; visita é uma
  próxima ação possível, distinta de autorização para contato humano.
- Relato de defeito recebe limite de escopo claro. Não consultamos catálogo ou RAG
  para simular diagnóstico. Novo interesse em compra sai desse contexto normalmente.

## Loja: informação fornecida pelo responsável pelo projeto

Leapmotor / Autovema Mobility, Grupo Rovema: **primeiro piso do Porto Velho Shopping**,
com acesso próximo pela **Entrada F**, perto da **CVC**. Sem endereço de rua, telefone,
horários, oficina no local, disponibilidade ou test-drive confirmados nesta entrega.

A apresentação usa “acesso F”, expressão geográfica equivalente: a política existente
classifica a palavra “entrada” como financeira. Não alteramos CommercialPolicyEngine
nem a barreira HTTP. O dado operacional é montado fora do texto livre do modelo e
validado antes da saída. Fonte operacional possui ID derivado da configuração
fornecida pelo responsável. Endereço tem resposta determinística sem LLM ou RAG.

A referência à loja aparece no convite uma vez por conversa. Pergunta de endereço
não se confunde com recusa de visita ou pedido de assistência técnica. Horário não
informado é declarado desconhecido; preferência do cliente não vira agendamento.

## Evidências e limites

`tests/unit/test_sales_delivery.py` cobre 12 cenários, incluindo conversa completa,
persistência em SQLite de nome/veículo/uso/troca/visita e ausência de consentimento
CRM implícito. `docs/evaluations/sales-delivery-before-after.json` contém execuções
sintéticas do grafo com as mesmas mensagens, com a flag desligada/ligada. Não são
transcrições reais do Groq nem prova independente de naturalidade.

Não houve avaliação paga. A experiência real ainda deve ser verificada no piloto.
Timeouts e limites do provedor continuam possíveis; não prometemos ausência de
falhas. A loja foi informada pelo usuário, sem inventar horários ou estoque.

Ativação prevista: backup privado de configurações/SQLite, checkout do commit
validado em branch de piloto, flags de foco comercial/orquestração ativas e
knowledge desativado, dados operacionais configurados. Nenhuma perda de contatos,
merge, push ou mensagem manual de teste. O serviço será verificado por health e
estado da Evolution após reinício.

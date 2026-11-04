# Humor, risadas e modelos fora do catálogo

Base `02e3fa3`. O print apresentou Fusca como intenção de compra, seguido de risada e repetição da pergunta sobre modelo/motorização. Três testes falharam antes do ajuste por ausência de redirecionamento contextual e redação apropriada. Os casos adversariais iniciais não exercitavam o novo plano e só se tornam evidência pertinente após a implementação.

## Implementação no mesmo grafo

`RouteHint` e `ConversationPlan` distinguem `banter` e `outside_catalog`. Os exemplos inequívocos (risada isolada, Lua com carro e algumas referências automotivas comuns) têm fast path; demais variações são interpretadas pelo roteador LLM existente. Não é um classificador universal de sarcasmo.

Antes da qualificação, a camada consultiva reconhece o ato e prepara composição social: sem ferramentas técnicas, fotos inventadas, transferência ou intenção de compra Leapmotor derivada de um Fusca. Menção ao carro na troca mantém o fluxo de qualificação anterior. Dados e instruções recebidos continuam não confiáveis.

O compositor escreve a resposta. Pode citar culturalmente o carro mencionado e oferecer os nomes aprovados B10/C10 em linguagem natural. Não existem novas ferramentas ou outro agente. A permissão transitória de mencionar a marca/modelos não é persistida no perfil e não libera atributos técnicos: números, fatos, fontes e ações continuam sob validação. A exceção de entidade externa exige citação literal na mensagem atual; não dá autoridade ao texto citado.

Especificações, afirmações de capacidade, comparações e valores não são fornecidos por esse plano. Afirmações técnicas em texto social e promessas de ir à Lua são rejeitadas nos cenários testados. Ataques ao cliente também são rejeitados. As referências culturais são apreciações de tom, não ficha técnica nem evidência comercial.

A resposta pode não ter pergunta; risada não exige nova escolha de motorização. O compositor recebe histórico recente e orientação para não repetir catálogo ou criar menu. O fallback é usado quando o provedor falha ou a redação não passa na validação, e continua identificado nas métricas.

## Evidências

- **570 testes passaram** na suíte completa, incluindo doze casos de humor/escopo: conversa Fusca → risada → Fusca, fantasia, redação livre, referência externa literal, veículo na troca e tentativas de atributos inventados, preço, ataque e encaminhamento não autorizado.
- Ruff, compilação e diff aprovados.
- [Execuções sintéticas](banter-evidence.json): mesmo grafo e LLM simulado; sem inferência paga ou envio externo no teste.
- Nenhuma alteração no CommercialPolicyEngine, consentimento, aprovação de mídia ou interface de envio.

## Limites

Não há garantia de lidar bem com qualquer situação. Ironia, referências desconhecidas, ambiguidade e novas paráfrases ainda precisam de avaliação real e humana. Os filtros de afirmações são conservadores e não são prova semântica geral. Uma expressão válida pode cair em fallback; os registros não ocultam isso como resposta bem-sucedida do LLM. Não foi realizada nova avaliação paga do Groq nesta entrega.

A regressão adicional de consentimento falhou antes da correção: uma mudança para brincadeira não cancelava a pergunta pendente. Agora, ela invalida a autorização ainda não concedida; um “sim” posterior não compartilha dados. Consentimento já concedido ou recusado não é reclassificado automaticamente.

A detecção de risada pura evita repetição ambígua de quantificadores; o teste com uma sequência longa de “k” seguida de texto passa sem classificar a mensagem inteira como risada.

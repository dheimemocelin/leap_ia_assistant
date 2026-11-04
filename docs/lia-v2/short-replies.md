# Respostas curtas e comunicação de encaminhamento

Base `8995a5d`. Ajuste motivado pelos prints com “Na estrada mesmo”, “Como?” e exposição de “fila local”.

## Reprodução

Três testes inicialmente falharam: resposta de rotina enviada à ferramenta técnica por interpretação simulada inadequada; manutenção inventada ao reparar uma resposta; jargão interno na mensagem de encaminhamento. O quarto teste diferencia explicitamente uma continuação de pergunta sobre autonomia.

Não foi possível reconstruir pelo print a pergunta imediatamente anterior a “Na estrada mesmo”. Por isso, testamos duas interpretações legítimas, em vez de presumir uma só.

## Comportamento

- Depois de uma pergunta sobre uso, a resposta curta pode registrar viagens e seguir a descoberta, sem consulta técnica obrigatória.
- Depois de pergunta sobre autonomia, recupera referências aprovadas do mesmo veículo e explicita a ausência de medição rodoviária específica, sem transformar a fala em contexto de manutenção ou prometer autonomia real. Não classifica automaticamente essa pergunta como rotina do cliente.
- “Como?” pede esclarecimento da última resposta. O compositor recebe o plano de reparo existente, com o veículo/uso conhecido. Uma afirmação de manutenção/reparo sem suporte nas falas recentes do cliente é rejeitada; não se inventa um defeito ou posse de veículo. Isso é um controle direcionado, não uma prova geral de consistência semântica.
- Status privado permanece `queued`, mas a resposta diz: “Registrei seu pedido de contato. Ele ainda não foi enviado a um consultor; podemos continuar por aqui.” O destino humano continua não configurado; nenhum recebimento é inventado.

A correção usa o mesmo grafo, catálogo, memória e orçamento de chamadas. Política comercial, consentimento, imagens e integração externa permanecem preservados.

## Validação

- Rodada completa final: **554 testes passaram**, com dependências opcionais locais já existentes no PYTHONPATH.
- Ruff, compilação e `git diff --check`: aprovados.
- Zero chamadas pagas ou mensagens reais enviadas pelo executor.
- [Execuções sintéticas](short-replies-evidence.json): resposta sobre uso em estrada, rejeição de manutenção inventada e mensagem de encaminhamento local.

A redação do simulador não comprova naturalidade do Groq. O teste real deve verificar continuidade no aparelho. A transferência real continua pendente de destino autorizado e integração; registrar o pedido não representa contato com vendedor.

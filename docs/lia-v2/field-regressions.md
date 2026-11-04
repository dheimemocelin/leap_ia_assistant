# Correções do teste de WhatsApp — receio, detalhes e fotos antigas

Base `a6c6fbe`. Os prints mostraram que a validação anterior, com conversas novas, não cobria adequadamente o histórico anterior à V2.

## Reprodução

`python3 -m pytest tests/unit/test_lia_v2_field_regressions.py -q`: quatro falhas antes da correção, com LLM simulado e estado sintético.

- Receio sobre “esse tipo de carro”, sem repetir a palavra “elétrico”, podia chegar a `get_vehicle_details` por interpretação técnica inadequada.
- Threads anteriores à V2 têm `shown_media_ids`, mas não a última galeria. Pedidos de reenvio caíam no filtro de novidade, que podia retornar outra imagem ou nenhuma.
- “Só rever as fotos” não era interpretado como reenvio.
- Se todos os fatos já estivessem marcados como apresentados, pedir mais detalhes podia produzir só um convite genérico, sem conteúdo.

## Correção

A expressão clara de receio com veículo conhecido recebe plano conversacional de objeção, sem ferramenta técnica obrigatória. Perguntas técnicas explícitas continuam no caminho factual. A redação permanece com o compositor existente; abstenção técnica indevida nesse plano é rejeitada, com fallback que reconhece o receio e pode explorar a preocupação, sem garantia ou pressão.

Para estado legado, recuperamos até três IDs previamente apresentados, aprovados e vinculados exclusivamente ao veículo atual. Não afirmamos reconstruir a última galeria histórica exata quando essa informação nunca foi persistida. A seleção recuperada permite rever material conhecido sem misturar motorizações. Pedidos novos continuam usando a última galeria V2. “Rever” também é reenvio explícito.

Pedir mais detalhes pode revisitar fatos aprovados quando não existem fatos novos. Não há criação de conteúdo nem consulta a documentos não aprovados.

## Evidências e limites

- Rodada completa: **549 testes passaram** com dependências opcionais locais já existentes no `PYTHONPATH`.
- Após acrescentar a proteção contra abstenção indevida do compositor: **49 testes V2 passaram** (44 anteriores e cinco regressões de campo).
- Ruff, compilação e `git diff --check` aprovados.
- Nenhum teste pago, mensagem real enviada pelo executor ou alteração em política comercial, consentimento, biblioteca ou aprovação das imagens.
- Não foi realizada nova avaliação de naturalidade com Groq. As conversas reais do usuário demonstraram limitações que as fixtures anteriores não cobriam; o teste externo deve ser repetido no piloto após ativação.

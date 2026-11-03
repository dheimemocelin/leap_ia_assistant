# Knowledge no piloto WhatsApp

Ativação solicitada pelo usuário após limpar o próprio contato de teste.

O mesmo LangGraph e a mesma Lia recebem `search_knowledge`, read-only. O primeiro
runtime consulta somente fatos do catálogo já aprovados pelo GroundingPolicy,
isolados por identificador canônico do veículo. Consultas lexicais determinísticas
vêm primeiro; embeddings locais E5 recuperam paráfrases quando necessário, com
limiar conservador. Resultados são revalidados após composição e antes de renderizar
as afirmações, usando o contrato existente de IDs de fatos/fontes e a barreira de
saída comercial. Não há acesso a ofertas financeiras, CRM ou comandos externos.

Os cinco trechos de manuais do preview não foram promovidos automaticamente: sua
fidelidade textual foi revisada, mas a aplicabilidade ainda está pendente. O piloto
não deve afirmar que todos os PDFs estão liberados. Perguntas sobre recurso opcional
não comprovado não podem usar uma informação relacionada como prova da presença.

A flag `LIA_KNOWLEDGE_ENABLED` fica false por padrão. O serviço do piloto precisa
receber o diretório de dependências via PYTHONPATH e um diretório local do modelo
verificado. Cache de embeddings é separado do banco de contatos e não persiste
texto de consultas de clientes. Modelo/provedor de conversação Groq preservado.

Validação antes da ativação: 477 testes passaram, incluindo sete novos de integração
com o grafo e isolamento/revogação de evidências; Ruff, compilação e diff-check
aprovados. Testes usam LLM simulado e embeddings locais/simulados; nenhuma chamada
paga foi feita como avaliação. Inicialização com modelo local real também foi
verificada sem LLM gerador. Naturalidade com Groq ainda depende do teste do usuário.

Plano operacional: preservar SQLite e configurações em backup privado, parar
brevemente o serviço, apontar o checkout para o commit validado, copiar somente
dependências/modelo locais necessários, ativar flags e reiniciar. Verificar health,
configuração efetiva e conexão Evolution sem enviar mensagens de teste. Não há
merge/push automático. Falha de inicialização exige retorno ao commit/configuração
anteriores; não fazer reenvio de mensagens incertas.

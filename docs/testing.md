# Plano de testes e avaliações

## Pirâmide

- Unitários: transições de estado, validação de respostas/citações, classificação, consentimento, allowlist e dedupe.
- Integração: Postgres/pgvector e Redis via Compose; persistência de histórico, filtros de ACL/versão, outbox, retries e concorrência.
- Contrato: fixtures sanitizadas Evolution webhook e schema Syonet configurável; testes de compatibilidade com sandbox quando disponível.
- Regressão/evals offline: conjunto sintético versionado de perguntas FAQ, veículo, revisões e pós-venda; adversariais para prompt injection em mensagens/documentos, PII, pedidos de preço/estoque sem fonte, baixa confiança e tentativa de ferramenta proibida.
- Segurança: autenticação/autorização, isolamento entre tenants/sessões, replay, rate limiting, redaction, retenção/deleção, dependências e segredos.

## Critérios de aceitação iniciais

1. Nenhuma resposta factual sem fonte aprovada vigente; preço/estoque/garantia ausente deve abster-se.
2. Conteúdo com instruções hostis não altera políticas nem habilita ferramentas.
3. CRM não recebe dados sem consentimento válido; envio repetido da mesma oportunidade produz uma gravação lógica.
4. Evento repetido não duplica mensagem nem lead; timeout não gera retry inseguro.
5. Falha de recuperação/modelo/integrador resulta em mensagem segura e estado recuperável/handoff.
6. Sessão de um cliente/tenant não pode ler conversa de outro.

Datasets devem ser sintéticos ou autorizados, com versão e critérios anotados. Métricas: recall de fonte, precisão de citações, taxa de abstenção correta, tool-call correctness, sucesso de handoff, duplicatas CRM, latência p50/p95 e custo por conversa. Estabelecer limites numéricos após baseline com conteúdo oficial e sandbox; não declarar qualidade de agente antes disso.

# Piloto privado — nome e oportunidades no banco

Data de preparação: 2026-11-02. Branch: `feat/local-pilot-memory`.

## O que está pronto

- Nome preferido sobrevive a logout/login, reinício do backend e “Nova conversa”.
- Contexto compacto da conversa atual é recuperado após reinício. Nova conversa limpa o contexto, preservando somente o nome.
- Oportunidade local é criada após seleção canônica; novos turnos atualizam a mesma linha por owner/conversa. Nova conversa representa outra oportunidade.
- Nome fica associado ao visitante no banco; o payload de oportunidade evita duplicá-lo. Resumo com contato exige pedido de humano e consentimento. Não há CRM ou envio externo.
- “Apagar meus dados” remove identidade, threads e oportunidades e encerra os acessos desse visitante. Dois navegadores usando a mesma senha permanecem isolados.
- Falha de gravação retorna erro visível, sem afirmar ao cliente que os dados foram salvos.

## Iniciar o teste

O arquivo `.local/pilot.sqlite3` foi criado vazio. O caminho foi configurado localmente no `.env`, sem alterar as credenciais. `.env` e arquivos SQLite são ignorados pelo Git. Em outro checkout, configure `PILOT_DB_PATH=.local/pilot.sqlite3` no ambiente ou `.env`.

```bash
cd /home/ubuntu/.t3/projects/leap-ia-assistant
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1 --no-access-log
```

Verificação sem chamar LLM:

```bash
curl --fail http://127.0.0.1:8000/health/ready
python3 -m app.pilot_admin --db .local/pilot.sqlite3
```

O comando de administração mostra apenas contagens, sem nomes, contatos ou mensagens. O servidor fica restrito ao localhost; abrir link externo exige uma ativação explícita do túnel de teste. Um túnel temporário pode mudar de URL e não garante disponibilidade. Processos iniciados no executor T3 podem ser cancelados com reinício do executor; o banco permanece em disco, mas não se promete uptime.

## Roteiro do piloto

1. Entrar no chat, fornecer um nome sintético, escolher modelo e motorização e informar uso.
2. Sair e entrar no mesmo navegador: a Lia não deve pedir o nome novamente.
3. Reiniciar o backend e entrar novamente: nome e contexto continuam.
4. Usar “Nova conversa”: novo assunto, mesmo nome.
5. Abrir outro navegador/perfil: nome não deve ser compartilhado.
6. Demonstrar interesse em visita: registrar oportunidade, sem oferta automática de vendedor.
7. Pedir explicitamente vendedor, autorizar e fornecer contato sintético: resumo local `prepared_not_sent`, sem envio.
8. Revogar autorização: o payload atual perde o contato autorizado.
9. Usar “Apagar meus dados”: removidos os registros e encerrada a sessão; depois de entrar novamente, nome é desconhecido.

No mesmo navegador compartilhado, use “Apagar meus dados” ao encerrar. Limpar cookies ou mudar de dispositivo perde a identificação. Não use dados reais de clientes nos testes. A tela ainda não restaura todo o histórico visual de galerias; o contexto compacto é recuperado no backend. Pedidos explícitos de ângulo permitem rever fotos; “Nova conversa” reinicia a apresentação do veículo preservando o nome.

## Evidências e limites

**175 testes passaram**, além de Ruff, compilação Python, `node --check app/web/chat.js` e `git diff --check`. Os oito novos testes usam SQLite real em diretório temporário e LLM simulado: reinício/reset, isolamento de navegador, upsert/consentimento/revogação, exclusão, readiness/conversa desconhecida, erro de escrita/recuperação, cookie forjado e separação dos modos revisado/pendente.

Os testes comuns desativam a configuração persistente por fixture para não tocar no banco local configurado; os testes de persistência ativam apenas seus arquivos temporários. Nenhuma inferência paga, dado real, mensagem WhatsApp, Syonet, deploy, merge ou push foi usado nesta validação. Mantém-se um aviso upstream LangChainPendingDeprecationWarning.

Limitações: piloto de um processo, banco local sem alta disponibilidade/criptografia, autenticação por senha compartilhada somente no chat web, histórico visual parcial e sem avaliação Groq real nesta execução. Readiness é operacional do modo configurado, não comprovação de qualidade do agente. Consulte [ADR](adr-local-pilot-memory.md).

## Próxima etapa: Evolution API

O cliente do WhatsApp não terá login nem senha. A configuração de autenticação da Evolution será somente do servidor. A identidade do remetente deverá ser vinculada com isolamento por instância/canal, deduplicação pelo ID da mensagem e tratamento seguro de retries. O mesmo agente e a memória serão reutilizados; números compartilhados precisam de cuidado com identificação.

A integração Evolution ainda não foi ativada nem validada. Serão necessários URL, instância e chave de API fornecida por mecanismo seguro, além do contrato/versionamento da instância. Não se deve remover autenticação de webhook/API para eliminar senha do cliente. WhatsApp não substitui consentimento para encaminhamento comercial. Primeiro validar o piloto web; depois executar a integração com limite e autorização de mensagens reais.

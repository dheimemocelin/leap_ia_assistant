# Piloto WhatsApp — Evolution compartilhada

Preparado em 2026-11-02. Evolution instalada: **2.3.7**. Instância LEAP: `leap-pilot`.

## Separação da infraestrutura

Infraestrutura compartilhada: `/home/ubuntu/apps/evolution` (Compose, configuração administrativa privada, PostgreSQL e Redis próprios). O LEAP mantém somente adapter, webhook, worker e configuração de sua instância. Novas aplicações usam instâncias/tokens/webhooks próprios e bancos de atendimento separados.

API Evolution: `127.0.0.1:8081`, sem administração pública. PostgreSQL/Redis não publicam portas. Credenciais globais ficam fora do projeto; o LEAP recebe token exclusivo da instância. Prova real de isolamento: token LEAP retorna 200 na própria instância e 401 em outra instância temporária, removida após o teste. Aplicações não confiáveis exigem também separação de usuário/container no sistema operacional.

`leap-pilot.service` executa o backend com restart supervisionado, sem terminal T3 aberto. Usa a interface Docker interna `172.17.0.1:8000`, sem abrir porta no IP público. Seu namespace bloqueia leitura da pasta administrativa Evolution e dos diretórios de credenciais T3/Codex. O template em `ops/leap-pilot.service` é específico deste servidor.

## Fluxo e controles

1. WhatsApp → Evolution → `POST /hooks/evolution/{instance}`, autenticado por `X-Webhook-Secret`.
2. Confere instância, evento, remetente e lista de participantes. Somente texto de conversa direta; ignora `fromMe`, grupos, status, eventos históricos e formatos não suportados.
3. Inbox SQLite durável antes do ACK. Identidade e ID da mensagem são HMACs privados estáveis, separados por instância. Não usa nome ou telefone enviado ao LLM como identificador.
4. O mesmo LangGraph/Groq consulta catálogo/mídia e mantém memória e oportunidades locais.
5. Resposta validada por AssistantResponse e política comercial independente. Outbox envia texto e fotos aprovadas, com integridade, MIME e path conferidos antes do envio.
6. Fotos são transmitidas como arquivo binário multipart: sem URL pública, conversão para base64 ou upload ao LLM.

Webhook é máquina-a-máquina: retorna apenas ACK tipado (`queued`, `duplicate`, `ignored`), sem texto do agente. Fica fora de `/v1/` para não misturar ACK com o contrato conversacional da barreira HTTP. A barreira das rotas de cliente não foi alterada; o adapter revalida o mesmo AssistantResponse antes de enviar texto. Não há endpoint público para escolher destinatário ou disparar mensagens.

Cliente não faz login nem informa senha. Autenticação de Evolution/webhook fica no servidor. O número do canal só é reutilizado como contato após pedido explícito de humano e consentimento, evitando repetir uma pergunta já respondida pelo canal. Nenhum dado é enviado ao Syonet. Nome é lembrado por remetente/instância e não é compartilhado automaticamente com navegador ou outro projeto.

`Apagar meus dados` remove memória, nome e oportunidades locais e limpa conteúdos antigos da fila. O pedido de exclusão tem prioridade e cancela mensagens pendentes desse participante, mesmo após o limite diário. Preserva tombstones opacos contra replay; não apaga histórico do WhatsApp/servidor Evolution nem constitui eliminação forense de backups.

## Entrega e recuperação

Deduplica ID da mensagem e controla partes separadas para texto/fotos. Retry automático limitado a conexão não estabelecida e HTTP 429. Timeout de leitura/escrita ou erro ambíguo não é reenviado: fica em `review`, evitando duplicar mensagem possivelmente entregue. Reinício marca processamento/entrega interrompidos para revisão; mensagens ainda em fila ou respostas prontas permanecem duráveis. Não se promete exactly-once externo.

Estados: `queued`, `processing`, `ready`, `delivering`, `sent`, `dry_run`, `review`, `cancelled`. `sent` significa aceite da API com ID, não leitura no telefone. Limites: 40 mensagens por participante/dia, um worker/processo e até três fotos por resposta. Áudio, visão, grupos e LID sem alias telefônico não estão implementados. Participantes ficam em configuração privada; não é um bot público irrestrito.

## Operação

```bash
cd /home/ubuntu/apps/evolution
sudo docker compose --env-file .env ps

cd /home/ubuntu/.t3/projects/leap-ia-assistant
sudo systemctl status leap-pilot --no-pager
python3 -m app.channels.evolution_admin status
python3 -m app.channels.evolution_admin qr
```

`qr` grava imagem privada em `.local/evolution-qr.png`, sem imprimir seu conteúdo ou chave. No número exclusivo: WhatsApp → Aparelhos conectados → Conectar aparelho → escanear. QR expira; gerar outro quando necessário. Não publicar QR ou chaves em Git. `connection` precisa ser `open` antes de declarar WhatsApp operacional.

Um participante autorizado usa outro WhatsApp para enviar `oi` ao número conectado. Testar nome, retorno após reinício, B10 BEV/REEV e C10 BEV, fotos, Uber/viagem, reações sociais, preço sem valores/oferta de vendedor, contato somente sob pedido/consentimento e exclusão. Mensagens do próprio número conectado são ignoradas para evitar loop.

Readiness verifica o banco do backend; não comprova pareamento ou qualidade Groq. Consultar `evolution_admin status` para conexão/fila. Não reenviar `review` cegamente: verificar a conversa primeiro. Para parar só LEAP: `sudo systemctl stop leap-pilot`. Parar infraestrutura compartilhada afeta seus outros projetos. Não usar `docker compose down -v`.

## Evidências

- Instalação real: Docker/Compose, Evolution 2.3.7 respondendo 200 e volumes persistentes; PostgreSQL/Redis saudáveis.
- Configuração real do webhook: 201; cabeçalho conferido por leitura posterior.
- Smoke autenticado de evento não conversacional: `ignored`, sem LLM ou mensagem.
- Container → backend: HTTP 200 pela rede interna, sem túnel público.
- Teste cruzado de credencial negado (401), sem WhatsApp conectado.
- Catálogo de modelos Groq consultado por GET: HTTP 200 e modelo configurado disponível, sem inferência/tokens.
- QR real gerado pelo servidor instalado; pareamento ainda depende do usuário.
- **192 testes automatizados passaram**: parser, auth, tamanho, allowlist, dedup, isolamento, memória após reinício, texto revalidado, multipart, entrega parcial incerta, dry-run, recuperação, exclusão, contato pós-consentimento, retries limitados e gates anteriores.
- Ruff, compilação Python, JavaScript syntax check e diff check aprovados; um aviso upstream LangChainPendingDeprecationWarning permanece.

Nenhum teste automatizado chama Groq/WhatsApp real. O primeiro atendimento real depende de pareamento e mensagem do participante autorizado. Não se declara entrega no telefone ou qualidade Groq aprovadas antes disso. A lista recebida em campo privado foi instalada sem expor números.

## Contratos consultados

[Release oficial](https://github.com/evolution-foundation/evolution-api/releases/tag/2.3.7), [router de envio](https://github.com/evolution-foundation/evolution-api/blob/main/src/api/routes/sendMessage.router.ts), [DTOs](https://github.com/evolution-foundation/evolution-api/blob/main/src/api/dto/sendMessage.dto.ts), [webhook e cabeçalhos](https://github.com/evolution-foundation/evolution-api/blob/main/src/api/integrations/event/webhook/webhook.controller.ts).

A schema da imagem instalada foi inspecionada: multipart exige `number` e `mediatype`, permite arquivo `file`. Compatibilidade foi testada localmente; recebimento no telefone e estabilidade da sessão exigem piloto pareado. Versão fixa, sem atualização silenciosa para `latest`.

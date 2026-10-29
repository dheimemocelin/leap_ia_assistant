# Chat web privado para teste

GET / serve a tela responsiva; nenhum framework, CDN ou dependência frontend adicional. HTML/CSS/JS locais, com política CSP, texto do assistente renderizado por textContent e sem chave Groq/API embutida.

Configurar WEB_CHAT_PASSWORD (mínimo 12 caracteres) no .env privado. Login via /web/login gera cookie aleatório HttpOnly, SameSite=Strict, Secure quando o acesso é HTTPS. Somente o hash do cookie fica no store local. Sessões duram duas horas, até 32 simultâneas; login limitado a 20 tentativas/minuto no processo e mensagens a 30/sessão. Nova conversa troca o conversation_id e não reinicia o orçamento de mensagens. Senha e tokens não aparecem em HTML, armazenamento JS ou logs de aplicação. Logout revoga o cookie no store. Reiniciar o servidor encerra sessões. Sem recuperação de senha ou SSO.

Browser chama /v1/web/messages: origem validada, sessão obrigatória, grafo existente e CommercialOutputBoundary obrigatória. A rota de API com Bearer permanece disponível para integrações autorizadas e não expõe APP_API_KEY ao navegador. Teste de origem cross-site falha fechado. Não usar a chave Groq como senha do chat.

O login permite escolher catálogo interno de fatos verificados (identidades C10 BEV/B10 BEV e autonomia C10 BEV) ou catálogo de atendimento pendente. O catálogo interno é somente ensaio; GroundingPolicy carrega facts.json revisado. Nenhuma foto foi aprovada ou publicada. Respostas não suportadas seguem abstenção/handoff; fotos não são exibidas porque a aprovação real ainda está pendente.

Execução local: python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1 --no-access-log . Quick Tunnel: cloudflared tunnel --url http://127.0.0.1:8000 . O processo cloudflared acessa somente o listener de loopback. O domínio temporário deixa de funcionar quando o processo para; não é deploy de produção. Senha é necessária mesmo para quem conhece o link. As conversas do usuário podem consumir cota Groq; não foram executadas inferências reais nos testes desta UI.

Gates: 90 testes Pytest passaram; Ruff, node --check do JavaScript e git diff --check passaram. Novos testes cobrem páginas/arquivos, login correto/incorreto, cookie Secure/HttpOnly, sessão expirada, CSRF, isolamento/reset/logout, limite e saída financeira bloqueada. Layout mobile via CSS; não foi realizada validação visual automatizada no navegador. Aviso transitivo LangGraph permanece. Limites locais: um processo, memória volátil, limite de sessões do agente e sem proteção distribuída contra abuso. Não compartilhar como canal de atendimento real.

Cloudflared 2026.10.6 foi obtido do release oficial cloudflare/cloudflared; SHA-256 do binário comparado ao digest do asset. Binário fica em /tmp, fora do Git; processos de teste permanecem ativos enquanto o operador usa o link. Referência: https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/ .

Verificação real do túnel temporário: página HTTPS retornou 200; tentativa de conversar sem autenticação retornou 401; /.env retornou 404. Senha solicitada por cartão privado; sem configuração de senha válida, o login falha fechado.

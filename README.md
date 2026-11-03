# Página de apresentação da Lia

Site estático independente da aplicação: HTML/CSS, sem dependências, formulários, rastreamento ou credenciais. Não conecta ao WhatsApp, banco ou LLM.

## Conteúdo e fontes

- Proposta, mais de oito empresas e faixa indicativa de R$ 1.500–3.000 por implementação: informações fornecidas pelo responsável, não pesquisa de mercado. Não representam economia comprovada.
- Foto: https://avatars.githubusercontent.com/u/113947697?v=4
- Logo fornecido: https://gruporovema.com.br/wp-content/uploads/2024/09/GRUPO-ROVEMA-NEGATIVO_Prancheta-1-1.png
- Nome público: perfil GitHub `dheimemocelin`. A breve apresentação é texto proposto, sem cargo ou resultados atribuídos.
- Conversa: ilustração editorial, sem dados reais de clientes ou alegação de execução.

As imagens foram copiadas para `assets/` para evitar requisições a terceiros na abertura da página. Logo e retrato não passam a estar sob licença MIT.

## Publicação no GitHub Pages

Publicar **somente o conteúdo desta pasta**. Não servir a raiz do repositório, `.local`, arquivos de ambiente ou artefatos internos. O workflow `.github/workflows/presentation-pages.yml` prepara o artefato estático e permite publicação manual. A aplicação e o serviço de WhatsApp não precisam ser reiniciados.

O GitHub Pages precisa estar configurado com a origem **GitHub Actions**. O workflow manual precisa estar na branch padrão para aparecer na interface do GitHub. A publicação deve ser aprovada separadamente; nenhum envio ao GitHub é necessário para visualizar os arquivos localmente.

## Validação

Verificar links locais e âncoras, estrutura HTML, ausência de scripts/rastreadores e `git diff --check`. Revisar em larguras desktop e móvel antes da publicação. Não há dados de clientes no site.

Workflow baseado na documentação oficial: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages

Validação nesta execução: estrutura HTML, IDs, âncoras, assets locais e diff verificados. O preview automatizado não pôde executar porque o navegador do executor T3 está sem bibliotecas de sistema (ATK/GBM/ALSA e outras). Não foi instalada infraestrutura de navegador nem afirmada validação visual desktop/móvel. Nenhuma publicação foi executada.

# Segurança e publicação

Não inclua credenciais, dados de clientes, conversas reais, bancos, backups,
sessões WhatsApp ou QR Codes em commits, issues ou pull requests.
Use `.env.example` somente com campos vazios ou exemplos identificáveis.

Suspeitas de vulnerabilidade ou vazamento devem ser comunicadas privadamente
ao mantenedor pelo mecanismo privado disponível no GitHub. Se indisponível,
combine um canal privado antes de compartilhar detalhes; não abra uma issue
com material sensível. Nunca envie o valor completo de uma credencial.

Antes da publicação, atualize as refs e execute:

```bash
git fetch origin --prune --tags
python3 scripts/audit_publication.py
```

O script examina blobs alcançáveis pelas refs locais e imprime somente caminho
e regra. Compara também segredos do `.env` local, quando presente. Não detecta
todo tipo de segredo, dados pessoais ou arquivo inacessível via refs. Não
consulta automaticamente issues, PRs, releases, Actions, caches ou forks.

Se uma credencial tiver sido commitada, revogue/rotacione primeiro. Remover o
arquivo atual não elimina versões anteriores. Reescrita de histórico e force
push exigem planejamento, autorização e coordenação com colaboradores.

Fotos e marcas possuem condições próprias: consulte [aviso de mídia](assets/MEDIA-NOTICE.md).

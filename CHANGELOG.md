# Changelog

## [Unreleased]

## [0.1.3] - 2026-11-15

### Corrigido
- `PATCH /cob/{txid}` aceita apenas `status: REMOVIDA_PELO_USUARIO_RECEBEDOR`, conforme `CobRevisada` do BCB; os demais valores retornam 400 (`invalid-state`) sem alterar a cobranca.
- `revisao` passa a ser persistida: comeca em 0 e sobe 1 por requisicao que altere status, valor ou calendario (`loc` e PATCH sem mudanca real nao contam). `PUT` sobre `txid` existente tambem incrementa. Migracao SQLite idempotente adiciona a coluna em bancos antigos.
- `PATCH` no formato plano legado (`{"valor":"12.00"}`) nao reseta mais a expiracao para 86400 s.
- `cob` (PUT/POST) exige `valor`, `calendario` e `valor.original`; o PATCH regenera o `pixCopiaECola` ao alterar o valor (PR #15, que ficou fora da v0.1.2).
- Testes de regressao para o PR #15 e para os itens acima.

### Alterado
- Quem usava `PATCH {"status":"CONCLUIDA"}` ou `{"status":"ATIVA"}` para simular pagamento deve usar `POST /_bancada/banco/pagar`.

## [0.1.2] - 2026-11-15

### Corrigido
- `cob` (PUT/POST/PATCH) aceita o payload oficial do BCB (`calendario.expiracao`, `valor.original`, `valor.modalidadeAlteracao`, `devedor`, `solicitacaoPagador`, `infoAdicionais`).
- `calendario.expiracao` passa a ser respeitado na criacao.
- Teste de contrato valida requisicao e resposta de PUT/POST/PATCH de `cob`.

### Obsoleto
- Formato plano legado (`{"valor":"10.50","expiracao":N}`) aceito com `Deprecation: true`; removido na v0.2.0.

## [0.1.1] - 2026-11-15

### Corrigido
- Retry de webhook com backoff exponencial e persistencia do ultimo status HTTP (`ultimo_status_http`).
- Reordenacao deterministica de entregas webhook (cenario `fora_de_ordem` com semente).
- `txid` incluido no payload do webhook.
- Filtros de periodo (`inicio`/`fim`) em `GET /cob`.
- Validacao de contrato contra OpenAPI oficial do BCB com `openapi-core`.
- Testes de expiracao e caos para webhooks.
- Ajustes de release: `release.yml` anexa `CHANGELOG.md` e gera notas; status do README atualizado.

## [0.1.0] - 2026-11-15

### Adicionado
- Emulador local da API Pix do BCB.
- Cobranca imediata (cob), location (loc), OAuth ficticio.
- Banco ficticio para pagar cobrancas de teste.
- Pix recebido e devolucao.
- Webhooks por chave com cenarios de caos.
- Relogio virtual e controle de cenarios.
- Painel Vue 3.
- Teste de contrato contra OpenAPI oficial pinado.
- Docker multi-stage e CI.

[Unreleased]: https://github.com/YVTOMAZ/pix-bancada/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/YVTOMAZ/pix-bancada/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/YVTOMAZ/pix-bancada/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/YVTOMAZ/pix-bancada/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/YVTOMAZ/pix-bancada/releases/tag/v0.1.0
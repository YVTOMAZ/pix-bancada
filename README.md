# pix-bancada

Emulador local da API Pix do BCB: banco ficticio para pagar cobrancas de teste, webhooks realistas, caos controlavel e relogio virtual.

> Status: v0.1.0 publicada.

## Aviso importante

Este projeto e **independente**. **Nao e afiliado ao Banco Central do Brasil (BCB) nem a nenhum Provedor de Servicos de Pagamento (PSP)**, nao e certificado e serve **apenas para desenvolvimento e testes**. O comportamento pode variar entre PSPs; este emulador segue o contrato publico da API Pix.

## Problema

No sandbox dos PSPs, o QR Code gerado nao e pagavel, entao o desenvolvedor so testa pagamento, webhook, devolucao e expiracao em producao. O pix-bancada resolve isso com um banco ficticio local.

## Quick start (3 comandos)

```bash
git clone https://github.com/YVTOMAZ/pix-bancada.git
cd pix-bancada
docker compose up
```

Acesse http://127.0.0.1:8080. Crie uma cobranca por curl e pague no navegador.

```bash
curl -X PUT http://127.0.0.1:8080/cob/tx1 \
  -H 'Content-Type: application/json' \
  -d '{"chave":"12345678901","valor":"10.50"}'
```

## Rotas suportadas (v0.1.0)

| Rota | Descricao |
|---|---|
| POST /oauth/token | Token ficticio |
| PUT/POST/GET/PATCH /cob/{txid}, GET /cob | Cobranca imediata |
| GET /loc/{id} | Location |
| POST /_bancada/banco/pagar | Pagar cobranca (banco ficticio) |
| GET /pix, GET /pix/{e2eid} | Pix recebidos |
| PUT/GET /pix/{e2eid}/devolucao/{id} | Devolucao |
| PUT/GET/DELETE /webhook/{chave} | Webhook por chave |
| POST /_bancada/relogio/avancar | Avancar relogio virtual |
| POST/GET /_bancada/cenarios | Cenarios de caos |
| GET /saude | Saude |

## Rotas planejadas (v0.2+)

cobv/lotecobv, Pix Automatico (rec, solicrec, cobr, retentativa), mTLS, locrec, DICT/MED, split, saque/troco.

## Limitacoes e o que nao e

- Nao e certificado, nao e afiliado ao BCB nem a PSP.
- Nao substitui testes em producao/sandbox real.
- Algumas regras variam por PSP; documentado como comportamento configuravel.

## Licenca

MIT. Veja LICENSE.

# pix-bancada

Emulador local da API Pix do BCB: banco ficticio para pagar cobrancas de teste, webhooks realistas, caos controlavel e relogio virtual.

> Status: em desenvolvimento (v0.1.0 em andamento).

## Aviso importante

Este projeto e **independente**. **Nao e afiliado ao Banco Central do Brasil (BCB) nem a nenhum Provedor de Servicos de Pagamento (PSP)**, nao e certificado e serve **apenas para desenvolvimento e testes**. O comportamento pode variar entre PSPs; o que este emulador faz e seguir o contrato publico da API Pix.

## Problema

No sandbox dos PSPs, o QR Code gerado nao e pagavel, entao o desenvolvedor so testa pagamento, webhook, devolucao e expiracao em producao. O pix-bancada resolve isso com um banco ficticio local.

## Quick start (em breve)

```bash
docker compose up
```

## Licenca

MIT. Veja `LICENSE`.

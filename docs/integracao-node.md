# Integracao Node

```js
const r = await fetch("http://127.0.0.1:8080/cob/tx1", {
  method: "PUT",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ chave: "12345678901", valor: "10.50" }),
});
```

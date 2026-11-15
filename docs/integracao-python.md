# Integracao Python

```python
import httpx
httpx.put("http://127.0.0.1:8080/cob/tx1", json={"chave": "12345678901", "valor": {"original": "10.50"}, "calendario": {"expiracao": 3600}})
```

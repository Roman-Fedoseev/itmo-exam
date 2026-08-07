# Support ticket routing PoC

Прототип маршрутизации тикетов: `auto_reply` / `suggest` / `escalate`.

Сейчас без обучения моделей: правила по словам + поиск в локальной KB + заглушка текста ответа.
Sync-путь (тема/риск/маршрут) отдельно от draft; ориентир sync &lt; 500 ms.

## Запуск

```powershell
pip install -r requirements.txt
python scripts/smoke_demo.py
uvicorn app.main:app --reload --port 8000
```

Демо: `/demo/happy`, `/demo/risky`, `/demo/llm-down`, `/demo/outage`, список `/demo/fixtures`.

## Сценарии

| Кейс | Ожидание |
|------|----------|
| `happy` | пароль → auto/suggest + draft |
| `risky` | оплата + PII → escalate |
| `happy` + LLM down | draft=degraded, auto→suggest |
| `faq` / `outage` | suggest (или escalate), не слепой auto на деньгах |
| `account_delete` / `unknown` / `injection` | escalate |
| `paraphrase_access` | **LIMIT**: похоже на доступ/пароль, но без ключевых слов — rules часто не дают auto |

## Real vs target

| Сейчас | В проде |
|--------|---------|
| Rules classify | Обученный классификатор |
| Keyword KB | Embeddings / BM25+vector |
| Mock draft / template | LLM + очередь + circuit breaker |
| Мало mock-тикетов | Разметка + мониторинг + shadow→suggest→auto |

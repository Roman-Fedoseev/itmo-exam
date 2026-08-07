# Автоматизация обработки тикетов поддержки (PoC)

Минимальный прототип + system design: быстро понять тему/риск тикета, безопасно выбрать маршрут `auto_reply` / `suggest` / `escalate`, при необходимости набросать черновик ответа.

**Важно:** в PoC нет обученной ML-модели и нет внешнего LLM. Classify и поиск KB — правила/слова; текст ответа — заглушка или шаблон из KB. Доказываем архитектуру и safety-policy, не качество нейросети.

## Запуск

```powershell
pip install -r requirements.txt
python scripts/smoke_demo.py
uvicorn app.main:app --reload --port 8000
```

API: `http://localhost:8000/docs`  
Демо: `/demo/happy`, `/demo/risky`, `/demo/llm-down`, `/demo/outage`, список `/demo/fixtures`.

## Какой сценарий демонстрируется

1. **Happy:** сброс пароля → low risk → `auto_reply` / `suggest` + draft + статья KB.  
2. **Risky / fallback:** оплата + карта/паспорт → `escalate`, без авто-ответа.  
3. **Degrade:** LLM «недоступен» → шаблон KB, `auto` понижается до `suggest`.  
4. **Edges:** outage, delete, unknown, injection; `paraphrase_access` — LIMIT правил (перефраз без ключевых слов).

Sync-путь (тема + риск + политика) измеряется отдельно (`latency_ms_sync`, ориентир &lt; 500 ms); генерация текста — отдельно (`latency_ms_draft`; в проде — async).

## Real vs design

| Реализовано в PoC | Целевая архитектура (docs) |
|-------------------|----------------------------|
| Rules-классификатор | Lightweight ML-классификатор |
| Keyword retrieval по KB | BM25 / embeddings |
| Mock draft + template fallback | LLM API + очередь + circuit breaker |
| FastAPI + jsonl audit | Встройка в ticket platform + HITL UI |
| Малый набор mock-тикетов | Разметка, мониторинг, shadow→suggest→auto |

Документы: `docs/product.md`, `architecture.md`, `ml.md`, `monitoring.md`, `risks-and-ops.md`, плюс `AI_USAGE.md`, `WORKLOG.md`, `SELF_REVIEW.md`.

## Допущения и ограничения

- 4 часа → компактный PoC, не production.  
- Демо в основном на русском; мультиязычность — отдельный шаг (не в текущем baseline).  
- Пороги confidence эвристические.  
- Нет нагрузочного теста пика 10–20k/10 мин.

## Зачем бизнесу (3–5 предложений)

Типовые обращения можно закрывать или готовить черновиком дешевле ~150 ₽/тикет руками, не раздувая штат на пиках. Ценность не в «LLM на всё», а в разделении: быстрый sync-маршрут без LLM, авто только на safe-темах, человек на деньгах и PII. Это снижает очередь и защищает CSAT/reopen/SLA. Пилот считаем на узком % объёма, с kill-switch и shadow→suggest→auto. Если guardrails ломаются — откатываем авто, а не гоним automation %.

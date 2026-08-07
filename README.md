# Автоматизация обработки тикетов поддержки (PoC)

Минимальный прототип + system design: быстро понять тему/риск тикета, безопасно выбрать маршрут `auto_reply` / `suggest` / `escalate` / `reject_rewrite`, при необходимости набросать черновик ответа.

**Важно:** в PoC нет обученной ML-модели и нет внешнего LLM. Classify и поиск KB — правила/слова; текст ответа — заглушка или шаблон из KB. Доказываем архитектуру и safety-policy, не качество нейросети.

## Как запустить PoC (главное)

```powershell
pip install -r requirements.txt
python scripts/smoke_demo.py
```

Smoke — основной способ проверки: happy path, risky/escalate, degrade при «падении LLM», edge-кейсы. В конце должно быть `OK: smoke passed`.

Опционально (если хотите потыкать HTTP API вручную) можно поднять сервер:

```powershell
uvicorn app.main:app --reload --port 8000
```

Тогда в браузере откроется Swagger UI: `http://localhost:8000/docs` — удобные кнопки для `/demo/happy`, `/demo/risky` и т.д. **Для сдачи достаточно smoke-скрипта**, сервер не обязателен.

## Какой сценарий демонстрируется (Proof of Concept)

1. **Happy:** сброс пароля → low risk → `auto_reply` / `suggest` + draft + статья KB.  
2. **Risky / fallback:** оплата + карта/паспорт → `escalate`, без авто-ответа (сценарий №6 из ТЗ).  
3. **Degrade:** LLM «недоступен» (`force_llm_down`) → шаблон KB, `auto` → `suggest` (корректная деградация).  
4. **Edges:** outage, delete, unknown, injection; `paraphrase_access` — LIMIT правил.  
5. **Multilingual:** `en_password` — LIMIT RU-rules на EN; `en_billing_pii` — escalate по карте (язык не важен) + `locale=en`.  
6. **Toxicity:** `toxic_ru` — мат/оскорбления → `reject_rewrite` + шаблон «переформулируйте» (не очередь оператора; topic для аудита всё равно считается).  
7. **Complex:** `multi_intent` → escalate (max risk); `sarcasm_billing` — LIMIT правил; `mixed_locale` → `locale=unknown`, не auto.  
8. **Burst:** `outage_burst` с `incident_id=INC-42` → status template, `llm_used=false` (dedup на пике, не LLM на каждый тикет).

Sync (тема + риск + политика) измеряется отдельно (`latency_ms_sync`, ориентир &lt; 500 ms); текст — отдельно (`latency_ms_draft`; в проде async). Стоимость LLM контролируем тем, что LLM **не** на classify; на пике — шаблоны/throttle (см. `docs/`).

## Real vs design

| Реализовано в PoC | Целевая архитектура |
|-------------------|---------------------|
| Rules-классификатор (RU) | Lightweight multilingual / per-locale ML |
| Keyword retrieval по KB | BM25 / embeddings + locale |
| Эвристика `locale` | Явный locale канала + lang-detect |
| Toxicity hard list → `reject_rewrite` | List + tiny toxicity model в sync-бюджете |
| Burst по `incident_id` + status template | Spike detector → dedup → incident templates |
| KB `owner` / `updated_at` (контракт) | Freshness gate + review process |
| Mock draft + template fallback | LLM API + очередь + circuit breaker |
| FastAPI + jsonl audit | Встройка в ticket platform + HITL UI |
| Малый набор mock-тикетов | Разметка, мониторинг, shadow→suggest→auto |

## Документация

- [`docs/product.md`](docs/product.md) — ценность, гипотезы, North Star / guardrails, ROI, rollout  
- [`docs/architecture.md`](docs/architecture.md) — поток, sync/async, **Mermaid-диаграмма**, встройка  
- [`docs/ml.md`](docs/ml.md) — rules / ML / embeddings / LLM  
- [`docs/monitoring.md`](docs/monitoring.md) — метрики, алерты, cost LLM  
- [`docs/risks-and-ops.md`](docs/risks-and-ops.md) — пики, PII, degrade  
- [`AI_USAGE.md`](AI_USAGE.md) · [`WORKLOG.md`](WORKLOG.md) · [`SELF_REVIEW.md`](SELF_REVIEW.md)

## Допущения и ограничения

- 4 часа → компактный PoC, не production.  
- Демо в основном на русском; EN gap показан в smoke (`en_password` = LIMIT); полный multilingual classify/KB — target.  
- Пороги confidence эвристические.  
- Нет нагрузочного теста пика 10–20k/10 мин.

## Зачем бизнесу (3–5 предложений)

Типовые обращения можно закрывать или готовить черновиком дешевле ~150 ₽/тикет руками, не раздувая штат на пиках. Ценность не в «LLM на всё», а в разделении: быстрый sync-маршрут без LLM, авто только на safe-темах, человек на деньгах и PII. Это снижает очередь и защищает CSAT/reopen/SLA. Пилот считаем на узком % объёма, с kill-switch и shadow→suggest→auto. Если guardrails ломаются — откатываем авто, а не гоним automation %.

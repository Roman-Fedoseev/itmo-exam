# AI_USAGE

Честное описание работы с AI (Cursor) на экзаменационном кейсе.

## Инструменты

- Cursor Agent — декомпозиция ТЗ, черновики кода PoC, черновики `docs/*` и review-файлов.
- Локальная проверка: `python scripts/smoke_demo.py` (без AI).

## По этапам

### 1. Понимание задачи и декомпозиция
- **AI помог:** разложить обязательные артефакты (README, docs, PoC, AI_USAGE, WORKLOG, SELF_REVIEW) и отделить «system design + PoC» от обучения модели на большом датасете.
- **Сам:** приоритет на 4 часа — working happy/risky + safety policy важнее UI/K8s/обучения; история коммитов как рассказ (MVP → edges → docs).

### 2. Проектирование архитектуры
- **AI помог:** набросать sync (&lt;500 ms) vs async draft, матрицу типов тикетов, встройку Decision Service рядом с ticket platform.
- **Сам / отклонил:** «LLM classify на каждый тикет» — отклонено из‑за пиков, cost и требования &lt;500 ms.
- **Изменилось после AI:** явное раздедение `latency_ms_sync` и `latency_ms_draft` в PoC (сначала AI смешивал generation в sync-бюджет — исправили).

### 3. Выбор ML/LLM подходов
- **AI предлагал:** сразу embeddings/vector DB и «живой» LLM API.
- **Отклонено:** вне скоупа 4ч и не нужно для доказательства policy; оставили rules + keyword KB + mock draft как baseline.
- **Сам:** зафиксировал, что LLM только на draft; auto запрещён на billing/PII/injection.

### 4. Разработка PoC
- **AI помог:** структура FastAPI-модулей (`classifier`, `retrieval`, `pipeline`, `llm`), fixtures, smoke.
- **Сам:** пороги policy, сценарий `force_llm_down`, кейс `paraphrase_access` как LIMIT правил, убрали Docker из сдачи (достаточно local run).

### 5. Тесты и документация
- **AI:** черновики product/architecture/ml/monitoring/risks.
- **Сам:** сверка с цифрами ТЗ (150 ₽, 40%, CSAT, reopen, SLA), ROI на узком пилоте (не «весь объём»), ревью формулировок под защиту.

### 6. Риски и edge cases
- **AI напомнил:** PII во внешний LLM, prompt injection, пики.
- **Сам:** escalate на injection/PII; degrade auto→suggest; в smoke явный LIMIT на перефразе.

### 7. Stress-test после doc-pack
- **AI помог:** разложить multilingual / toxicity funnel / multi-intent / burst-dedup и куда писать в docs vs код.
- **Сам:** toxicity = reject_rewrite (не escalate); EN topic-слова убрали для честного LIMIT; burst через `incident_id`, не через «магический» флаг; smoke с LIMIT/ok.

### 8. Процесс и ложный успех метрик
- **AI:** черновики про HITL discipline, training bias, DPA, anti-pattern automation↑/CSAT↓.
- **Сам:** оставил это в docs (без фейкового кода UI); stop-условия пилота дополнил явным «ложным успехом».

## Примеры ошибок AI и как чинили

| Ошибка / совет AI | Как заметили | Что сделали |
|-------------------|--------------|-------------|
| Классифицировать всё через LLM | Конфликт с &lt;500 ms и пиками из ТЗ | LLM убрали с hot path; rules/ML на classify |
| Считать draft в sync latency | Нельзя честно защищать SLA sync | Разделили `latency_ms_sync` / `latency_ms_draft` |
| Сразу vector DB / большой код «под прод» | Чеклист «чего не делать» в ТЗ | Оставили компактный PoC + docs |
| Завышенный ROI «40% × 200k сразу» | Нереалистично для MVP | ROI на 1% пилота + явные assumptions |
| Auto-логика для денежных тикетов в черновиках | Safety/product risk | Policy: escalate always на billing/PII |

## Что решил кандидат самостоятельно (итог)

- Каркас: policy + HITL важнее «умного текста».  
- Коммиты: мало, по смыслу защиты (MVP → edges → architecture → doc-pack).  
- Честный scope: rules baseline, без обучения большой модели.

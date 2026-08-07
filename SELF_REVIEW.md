# SELF_REVIEW

## Самая слабая часть

Rules-классификатор и keyword retrieval: хорошо работают на «прямых» RU-формулировках (пароль/списание), ломаются на перефразах (`paraphrase_access`), EN (`en_password`) и сарказме/косвенном billing (`sarcasm_billing`) — LIMIT в smoke. Multi-intent и mixed locale закрываем conservative policy (escalate), не «умным» NLU. KB/draft пока по сути RU. Confidence эвристический. Draft — mock.

## Предположения

- Цифры ТЗ (200k/день, 40% типовых, 150 ₽, CSAT 4.2, reopen 9%, SLA 15 мин) принимаем как данность.
- Пилот ROI считаем на ~1% потока safe-тем, не на всём потенциале 40%.
- Основной язык демо — RU; `locale` в PoC — эвристика; полноценный multilingual classify/KB не внедряли (EN LIMIT в smoke).
- Существующая ticket-платформа есть — мы проектируем Decision Service рядом, не заменяем CRM.

## Нерешённые риски

- Ложный low-risk / пропуск billing при новых формулировках.
- Prompt injection обходит простые эвристики.
- Поведение p95 sync под реальным пиком 10–20k/10 мин не нагрузочно измерено.
- Стоимость LLM при расширении suggest на большой % потока может вырасти скачком без throttle.
- Suggest без дисциплины HITL (слепой Send) и bias обучения на одних правках — в PoC UI нет, закрыто в docs.
- Юридический контур DPA/регион для реального LLM API ещё не внедрён (только зафиксирован как must-have).

## Что улучшить за +2 дня

- Небольшой eval-набор + калибровка порогов; больше paraphrase/adversarial кейсов.
- Подключить один LLM provider с circuit breaker и redact PII перед промптом.
- BM25 или простой embedding retrieve вместо чистого keyword.
- Shadow-метрики в логах (agreement с «ожидаемым» decision в fixtures).

## Перед production

- Разметка истории и lightweight classifier на sync-пути.
- Нормальный HITL UI (suggest) в текущем agent desktop.
- Дашборды/алерты из monitoring.md + kill-switch auto.
- Юридический контур для внешнего LLM (DPA/регион) и запрет сырого PII в промпте.
- Нагрузочный тест sync-пути и runbook на инцидент/пик.

## Что не стоит автоматизировать полностью

Споры об оплате и возвраты, удаление аккаунта, юридические/жалобы, любые PII-sensitive решения, неоднозначные «всё сломалось» без статуса инцидента, любые действия с деньгами пользователя.  
Токсичные обращения не «решаем» FAQ-ботом и не валим в очередь как обычный HIGH — только `reject_rewrite` (hard list сейчас; tiny model в цели).

## Какие данные пилота остановили бы проект

Остановить/откатить auto (или весь пилот), если:
- reopen auto-когорты стабильно &gt; baseline+3pp, **или**
- CSAT auto-когорты &lt; 4.0, **или**
- automation↑ при одновременном CSAT↓/reopen↑ (ложный успех), **или**
- ≥1 критический инцидент (неверный refund / утечка PII / авто на HIGH), **или**
- justified complaints про бота выше заранее заданного порога, **или**
- стоимость LLM на пилоте съедает &gt;X% ожидаемой экономии при том же качестве (порог X зафиксировать до старта).

## LLM self-review

LLM намеренно не стоит на classify. Риск LLM — cost, latency, галлюцинации и небезопасные «обещания» пользователю; поэтому draft grounded на KB, при outage — template, auto понижается до suggest, денежные решения — только HITL.

# Monitoring

Как понимаем в бою: система жива, модели/правила не «поехали», бизнес-цель выполняется, LLM не съедает бюджет.

## Технические метрики

- sync latency p50/p95 (цель: p95 &lt; 500 ms на classify+retrieve+policy)
- draft latency / длина очереди async worker (в проде)
- error rate API, timeout rate
- LLM availability, circuit breaker open/close
- cost: ₽ и tokens на 1k тикетов / на 1k drafts

## ML / policy метрики

- распределение topic/risk vs baseline (неделя назад)
- histogram confidence; доля unknown / low-conf
- retrieval hit-rate и empty-retrieve rate
- disagreement shadow vs решение оператора
- **false-auto на HIGH** (должно быть 0)

## Продуктовые / бизнес (см. также product.md)

- automation rate **только в safe-категориях** (North Star-связанная)
- reopen rate, CSAT, SLA breach (first response 15 мин) — **в разрезе channel** и **locale**
- доля escalate (резкий рост без инцидента = сигнал)
- reopen с причиной / тегом **wrong KB instruction** (сигнал гнилой статьи)
- доля тикетов в `burst_incident` / с `incident_id` во время пика (ожидаемо↑ при outage)
- **suggest send-as-is rate** (доля отправок без правки) — высокий % при CSAT↓ = слепой Send
- edit distance / доля существенных правок draft (качество suggest)

## Ложный успех (anti-pattern)

| Картина | Вердикт |
|---------|---------|
| automation↑, CSAT↓ или reopen↑ | пилот **провален** → kill-switch / откат auto |
| automation↑ только на одном locale/channel, на других CSAT↓ | не раскатывать глобально; чинить locale/channel |
| suggest acceptance↑, CSAT suggest-когорты↓ | UI/дисциплина HITL, не «модель стала лучше» |
| LLM cost↓ за счёт шаблонов, но wrong-instruction↑ | экономия ценой гнилой KB — откатить статьи с auto |

North Star без guardrails читать нельзя.

## Стартовые алерты

| Триггер | Что делаем |
|---------|------------|
| sync p95 &gt; 500 ms 5+ мин | упростить retrieve / scale / выключить тяжёлое |
| LLM errors/timeouts &gt; 20% | открыть circuit → templates, auto→suggest |
| auto@HIGH &gt; 0 | немедленный kill-switch auto |
| reopen auto-когорты &gt; baseline+3pp | откат auto → suggest |
| CSAT auto/suggest-когорты &lt; порога при automation↑ | kill-switch; разбор ложного успеха |
| suggest send-as-is↑ + CSAT↓ | усилить HITL UI/QA, временно сузить suggest |
| cost LLM / день &gt; budget | throttle drafts, больше шаблонов |
| доля unknown/low-conf резко↑ | проверить drift / инцидент формулировок |
| reopen wrong-instruction↑ по одной KB-статье | снять статью с auto, review owner |
| outage spike без роста `incident_id`/templates | проверить dedup/burst wiring; иначе LLM cost взлетит |

## Деградация модели vs изменение потока (drift)

| Сигнал | Скорее infra / LLM outage | Скорее data/model drift |
|--------|---------------------------|-------------------------|
| Ошибки/timeout LLM↑, topics стабильны | да | нет |
| Меняется смесь тем/лексика, low-conf↑, disagreement↑, infra OK | нет | да |
| Массовый outage в продукте, тема `service_outage`↑ | продуктовый инцидент (ожидаемо) | не путать с «модель сломалась» |

Действия: outage LLM → degrade path; drift → пересмотр порогов/дообучение/разметка; продуктовый инцидент → burst templates.

## Стоимость LLM

- отдельный дашборд: вызовы/день, ₽/день, ₽ на auto vs suggest
- лимит бюджета + throttle
- на пике приоритет шаблонов outage, не «LLM на каждый тикет»

## Решается ли исходная задача

Исходная задача: снизить нагрузку на операторов на типовых **без** ухудшения UX/SLA/безопасности.

Смотрим связку:
1. automation safe↑  
2. guardrails (CSAT/reopen/SLA/auto@HIGH) в норме  
3. handle time / очередь на FAQ↓  
4. audit доступен для разбора ошибок  

Если automation↑, а reopen/CSAT ломаются — задача **не** решена, откатываем auto.  
То же для suggest: рост «отправли черновик как есть» без удержания CSAT — это не эффективность, а потеря контроля HITL.

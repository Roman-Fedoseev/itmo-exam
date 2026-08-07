# ML / LLM

## Честно про PoC

В прототипе **нет обученной модели и нет внешнего LLM API**.  
Classify = keyword rules. Retrieve = пересечение слов с KB. Draft = склейка строки или шаблон статьи.

Это **baseline**, чтобы доказать policy + latency-контракт. Ниже — какие ML-задачи есть в системе и чем PoC заменяется в цели.

## Какие задачи есть

| # | Задача | Зачем |
|---|--------|--------|
| 1 | Topic / intent | понять тему тикета |
| 2 | Risk / sensitive | понять, можно ли авто |
| 3 | PII / injection hints | не слать опасное в авто/LLM |
| 4 | Toxicity / abuse | отсеять мат/оскорбления до FAQ-авто |
| 5 | Retrieval (KB / similar) | найти опору для ответа |
| 6 | Draft generation | текст ответа / черновик оператору |
| 7 | Policy | не модель: auto/suggest/escalate/reject_rewrite |

## Что чем решаем

| Задача | Сейчас (PoC) | Целевое | Почему так |
|--------|--------------|---------|------------|
| topic/risk | rules | классическая ML (logreg/boosting на TF-IDF или маленький encoder) | нужно &lt;500 ms, дёшево на пике |
| PII | regex | regex + NER (открытая/внутренняя) | до внешнего LLM |
| toxicity | hard list | list → tiny classifier (distil/BERT-класс) | sync &lt;500 ms; не LLM; не escalate |
| retrieval | keyword overlap | BM25 и/или embeddings + ANN | перефразы rules/keyword не тянут (см. LIMIT в smoke) |
| draft | mock / template / rewrite template | LLM API + grounding на KB | качество текста; async |
| low confidence | пороги + escalate | те же пороги после калибровки | безопаснее «угадать» |

## Где LLM нужен / не нужен

**Нужен (async):** черновик ответа, суммаризация длинного тикета для оператора, перефразирование шаблона KB.  

**Не нужен (и вреден на hot path):** classify/route каждого тикета через LLM — latency, cost, плохо аудитится на пике 10–20k/10 мин.  
**Не нужен для решения «вернуть деньги»:** это policy + HITL, не генерация.

## Baseline, которые разумно запустить первыми

1. Rules + keyword KB + policy (наш PoC) — уже есть.  
2. Классификатор темы на размеченной истории (offline accuracy / F1 + false-auto@HIGH=0).  
3. BM25/embeddings retrieve — recall@k, пустые retrieve↓.  
4. LLM draft только в suggest + eval «опирается на KB / нет запрещённых действий».

## Откуда модели и данные

| Компонент | Источник | Данные | Тех. метрики выбора |
|-----------|----------|--------|---------------------|
| Intent/risk classifier | обучить внутри на тикетах компании (или fine-tune открытого small encoder) | исторические тикеты + резолюции; разметка topic/risk/«можно auto» | F1 по темам; false-auto на HIGH → 0; latency p95 |
| Embeddings | открытая multilingual модель или внутренний encoder | пары ticket↔helpful KB / similar resolved | recall@k, nDCG; p95 retrieve |
| LLM draft | внешний API (с DPA) или self-host | промпт + KB snippets; без сырого PII | groundedness/ручная оценка; cost/1k; timeout rate |
| PII NER | открытый стек (напр. Presidio-like) + правила | паттерны + разметка утечек | precision/recall PII; 0 утечек в промпт |

### Разметка (если учим classifier)

- Выборка исторических тикетов после PII-scrub.  
- Лейблы: topic, risk_level, `auto_ok` (да/нет).  
- Двойная разметка на спорных + аудит ошибок shadow-режима операторами.  
- Регулярный refresh при drift (новые продукты/формулировки).

### Bias: нельзя учиться только на suggest-правках

Операторы правят в основном сложное; «отправили как есть» и простые FAQ реже попадают в обучающую выборку → перекос порогов/тем.  
Митигация: стратифицированный срез (в т.ч. accepted-as-is), shadow-agreement, отдельный eval на safe-темах; не фитить модель только под edit-логи.

## Мультиязычность

Задачи topic / risk / retrieve / draft зависят от языка; **policy** (auto/suggest/escalate на PII/billing) — нет.

| Слой | PoC | Target |
|------|-----|--------|
| locale | эвристика cyr/lat или поле тикета | locale канала + lang-detect |
| topic/risk | RU keyword rules (EN topic-слова убраны намеренно) | multilingual encoder или модели на locale |
| retrieve | RU KB + keyword | индекс/статьи per locale или multilingual embeddings |
| draft | RU mock/template | LLM: «отвечай на языке тикета» + локальные шаблоны |

EN access без русских ключей → unknown/escalate: **безопасно, но не автоматизируем** (smoke LIMIT `en_password`).  
Карта/PII ловятся regex независимо от языка (`en_billing_pii`).  
Смешанный RU+EN → `unknown` locale (эвристика доли cyr/lat); не auto (`mixed_locale` в smoke).  
Не масштабируем if-ы/словари на каждый язык.

## Сложные тексты (где baseline врёт)

| Кейс | PoC | Target |
|------|-----|--------|
| Multi-intent | ≥2 topic hits → `multi_intent`, escalate, risk = max | multi-label classifier / вторичные intents |
| Сарказм («всё супер, компенсируйте») | часто miss billing → LIMIT в smoke | размеченные adversarial + модель/LLM-assist только offline/eval |
| Перефраз / EN | LIMIT (уже в smoke) | embeddings + multilingual encode |
| Outage без статуса инцидента | suggest/template, не auto-close денег | связь с status page / incident id |

Правило защиты: на сомнении — escalate/suggest, не «дотянуть» keyword-костылями до auto.

## Низкая уверенность

- conf низкий или topic=unknown → **escalate**, не auto.  
- Пороги сначала эвристика (как в PoC), потом калибровка на validation + shadow.  
- «Серая зона» → suggest, не auto.

## Валидация качества

- Offline: F1, confusion по опасным темам, false-auto@HIGH=0.  
- Online shadow: agreement с решением оператора.  
- Продукт: automation (safe only), reopen, CSAT, SLA — **вместе**, не automation в одиночку.  
- Stop: см. product.md / SELF_REVIEW / monitoring (reopen/CSAT/критический инцидент / слепой suggest).

## PoC → target

| PoC | Target |
|-----|--------|
| `classifier.py` rules | calibrated ML classifier |
| `retrieval.py` keywords | embeddings/BM25 |
| `llm.py` mock | LLM + circuit breaker + queue |
| hardcoded thresholds | thresholds from validation + monitoring |

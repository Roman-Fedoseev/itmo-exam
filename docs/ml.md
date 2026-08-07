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
| 4 | Retrieval (KB / similar) | найти опору для ответа |
| 5 | Draft generation | текст ответа / черновик оператору |
| 6 | Policy | не модель: регламент auto/suggest/escalate |

## Что чем решаем

| Задача | Сейчас (PoC) | Целевое | Почему так |
|--------|--------------|---------|------------|
| topic/risk | rules | классическая ML (logreg/boosting на TF-IDF или маленький encoder) | нужно &lt;500 ms, дёшево на пике |
| PII | regex | regex + NER (открытая/внутренняя) | до внешнего LLM |
| retrieval | keyword overlap | BM25 и/или embeddings + ANN | перефразы rules/keyword не тянут (см. LIMIT в smoke) |
| draft | mock / template | LLM API + grounding на KB | качество текста; async |
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

## Низкая уверенность

- conf низкий или topic=unknown → **escalate**, не auto.  
- Пороги сначала эвристика (как в PoC), потом калибровка на validation + shadow.  
- «Серая зона» → suggest, не auto.

## Валидация качества

- Offline: F1, confusion по опасным темам, false-auto@HIGH=0.  
- Online shadow: agreement с решением оператора.  
- Продукт: automation (safe only), reopen, CSAT, SLA.  
- Stop: см. product.md / SELF_REVIEW (reopen/CSAT/критический инцидент).

## PoC → target

| PoC | Target |
|-----|--------|
| `classifier.py` rules | calibrated ML classifier |
| `retrieval.py` keywords | embeddings/BM25 |
| `llm.py` mock | LLM + circuit breaker + queue |
| hardcoded thresholds | thresholds from validation + monitoring |

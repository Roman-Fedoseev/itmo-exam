# WORKLOG

План на 4 часа: сначала поднять минимальный PoC (happy + risky) и зафиксировать его коммитом; затем расширить кейсы и degrade; затем architecture/risks; в конце — product/ml/monitoring и review-артефакты (AI_USAGE, WORKLOG, SELF_REVIEW), без раздувания кода.

По факту так и пошло по скоупу: коммит `feat: mvp sync route and policy poc` → `feat: edge cases and degrade path` → `docs: architecture constraints and target design`; doc-pack дописывается отдельным шагом под сдачу.

Что пошло не идеально по времени: часть времени ушла на согласование «что реально в PoC vs что только в docs» и на то, чтобы smoke честно показывал LIMIT правил (перефраз), а не только «всё зелёное».

Сознательно вырезали из скоупа: обучение классификатора, embeddings/vector DB, внешний LLM API, Docker/K8s, UI оператора, нагрузочный тест пика 10–20k/10 мин — это не требуется ТЗ за 4 часа и мешало бы компактной защите.

Итог скоупа: работающий rules-baseline PoC + обязательные документы с явными компромиссами; история коммитов отражает этот порядок решений.

После doc-pack прогнали stress-test системы: мультиязык (locale + EN LIMIT), toxicity→reject_rewrite, multi-intent/mixed locale, burst по incident_id, контракт KB owner/updated_at — зафиксировали в коде, smoke и docs одним коммитом.

Добили процессные риски в docs (без нового кода): suggest-дисциплина / bias логов, DPA+PII→LLM, ложный успех automation↑ при CSAT↓, метрики send-as-is и разрезы channel/locale.

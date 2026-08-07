# Risks and ops

Коротко по требованиям ТЗ: 3–4 ключевых пункта на направление.

## Highload и надёжность

1. **Sync vs async:** classify/route — sync (ориентир p95 &lt; 500 ms); генерация ответа — async-очередь с backpressure.
2. **Пики 10–20k / 10 мин:** приоритет очереди по SLA/risk; LLM throttle; **dedup**: похожие outage схлопываем к `incident_id` + общий status template (не 20k вызовов LLM).
3. **LLM недоступен:** circuit breaker → KB template + понижение `auto_reply` → `suggest`; маршрут пользователю/оператору всё равно отдаём быстро.
4. **Разделение бюджетов:** generation никогда не входит в sync-latency; иначе пик ломает SLA первого ответа.
5. **Устаревшая KB:** риск reopen «следовали инструкции — не сработало». Нужны owner + `updated_at`, мониторинг wrong-instruction, процесс review (в PoC — поля в JSON, без hard stale-gate).
6. **Каналы:** chat vs email — разные ожидания по скорости/длине; не смешивать метрики SLA без разреза по `channel`.

## Privacy, safety и risk

1. **PII:** карты/паспорта детектим → escalate; сырые PII не отправляем во внешний LLM API (в цели — redact/mask).
2. **Нельзя auto-close:** billing/refund, account delete, legal/abuse, injection, low confidence / unknown — только human-in-the-loop.
3. **Prompt injection:** эвристики + escalate; ответы grounded на KB; команды из текста тикета не исполняем.
4. **Toxicity / оскорбления:** не escalate в очередь оператора. Hard list (PoC) → затем tiny toxicity model (target) на sync-пути в бюджете &lt;500 ms → `reject_rewrite` + шаблон «переформулируйте корректно». Алерты на мат не нужны — нужен автоматический gate.
5. **Аудит:** каждое решение логируем (ticket_id, decision, reason, path, sync/draft latency, llm_used, toxicity) для разбора инцидентов и комплаенса.

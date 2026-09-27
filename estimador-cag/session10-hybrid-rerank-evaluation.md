# Sesión 10 — Búsqueda híbrida y reranking: golden set y medición

> Igual que `arquitectura-actual.md` en la Sesión 9, este documento es el entregable
> evaluativo de la sesión: no repite el diseño (ver el README, sección
> ["Búsqueda híbrida y reranking (Sesión 10)"](README.md#búsqueda-híbrida-y-reranking-sesión-10)),
> se centra en los números y en la conclusión razonada.

## 1. Golden set

5 queries (`scripts/golden_set.json`), redactadas como descripciones de proyecto a
estimar — no copias literales de `project_summary` — y anotadas a mano contra los 15
`budget_id` reales de `data/budgets_sample.json`. Criterio de anotación: *"Relevante si
el presupuesto histórico serviría como referencia directa de esfuerzo/alcance para
estimar el proyecto descrito en la query"*.

| id | Query | `relevant_budget_ids` | Por qué |
| --- | --- | --- | --- |
| q01 | Banca móvil, login OAuth2, conectores PSD2, detección de fraude en tiempo real | `BUD-2024-001`, `BUD-2024-003` | 001 es el match directo (OAuth2+PSD2); 003 aporta la pieza de fraude en tiempo real que 001 no cubre |
| q02 | E-commerce con catálogo, carrito, checkout y devoluciones post-venta | `BUD-2024-005`, `BUD-2024-008` | 005 cubre catálogo/carrito/checkout; 008 cubre devoluciones — ningún presupuesto único cubre ambas piezas |
| q03 | Telemedicina, citas de pacientes, videoconsulta, integración HL7 FHIR | `BUD-2024-009` | Único match real; el sector healthcare tiene 4 presupuestos distintos (010 monitorización remota, 011 farmacia, 012 ensayos clínicos) que no deberían colarse — mismo dominio que `02_ambiguous.txt` de Sesión 9 |
| q04 | IoT industrial, telemetría de sensores, mantenimiento predictivo, anomalías | `BUD-2024-013`, `BUD-2024-015` | 013 es el match directo; 015 comparte el patrón ingesta-de-telemetría + modelo predictivo aunque sea de otro dominio (red eléctrica) |
| q05 | Firma electrónica para contratos vinculantes, webhooks, archivado de documentos | `BUD-2024-002` | Diseñada para probar el rescate léxico de RRF: es un componente (`SIGN-003`) dentro de un presupuesto de originación de préstamos — semánticamente lejano del resto de la query, pero con match léxico exacto en "firma electrónica"/"webhook" — análogo al ejemplo "Stripe" del material de lectura |

**Nota de honestidad:** esta anotación es un borrador razonado, no una revisión de negocio — el propio `annotated_by` del JSON lo deja explícito. Antes de tratarla como vara de medir definitiva, alguien del equipo comercial debería confirmarla o ajustarla.

## 2. Metodología

`scripts/measure_retrieval.py` ejecuta las 4 configuraciones exigidas por el enunciado contra las 5 queries, 3 corridas por query (mediana de latencia), llamando a `search_chunks(...)` directamente en proceso (sin pasar por la reformulación LLM, para medir solo el retriever). Precisión\@5 cuenta cada chunk del top-5 independientemente, sin deduplicar por `budget_id` — ver el docstring del script para la justificación de por qué no se corrige ese efecto.

| Config | Búsqueda | Reranking |
| --- | --- | --- |
| A | Vectorial | No |
| B | Híbrida (RRF) | No |
| C | Vectorial | Sí |
| D | Híbrida (RRF) | Sí |

## 3. Resultados

_(pendiente de completar tras `docker compose run --rm ai_service python scripts/measure_retrieval.py`)_

| Config | Búsqueda / Reranking | Precisión\@5 media | Latencia mediana (ms) |
| --- | --- | --- | --- |
| A | Vectorial / No | — | — |
| B | Híbrida / No | — | — |
| C | Vectorial / Sí | — | — |
| D | Híbrida / Sí | — | — |

## 4. Conclusiones

_(pendiente)_

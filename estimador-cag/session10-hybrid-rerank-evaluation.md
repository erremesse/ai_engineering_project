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

Ejecución real contra el corpus de 15 presupuestos re-ingerido (`docker compose run --rm ai_service python scripts/measure_retrieval.py`, `RAG_DISTANCE_THRESHOLD=0.6`, `RAG_RECALL_POOL_SIZE=50`, `RAG_RRF_K=60`, reranker `cross-encoder/ms-marco-MiniLM-L-6-v2`):

| Config | Búsqueda / Reranking | Precisión\@5 media | Latencia mediana (ms) |
| --- | --- | --- | --- |
| A | Vectorial / No | **0.76** | **86** |
| B | Híbrida / No | 0.76 | 91 |
| C | Vectorial / Sí | 0.64 | 1689 |
| D | Híbrida / Sí | 0.64 | 1624 |

Desglose por query (precisión\@5; idéntico entre A/B y entre C/D en las 5 queries):

| Query | A / B (sin rerank) | C / D (con rerank) |
| --- | --- | --- |
| q01 — banca móvil OAuth2/PSD2/fraude | 1.00 | 1.00 |
| q02 — e-commerce catálogo/carrito/devoluciones | 1.00 | **0.40** |
| q03 — telemedicina FHIR | 0.80 | 0.80 |
| q04 — IoT industrial/mantenimiento predictivo | 0.60 | 0.60 |
| q05 — firma electrónica/webhook (test de rescate léxico) | 0.40 | 0.40 |

Dos observaciones no anticipadas antes de correr el script, ambas con la misma causa raíz:

1. **La rama híbrida no cambió ni una sola precisión respecto a la vectorial pura**, en ninguna de las 5 queries — ni siquiera en q05, diseñada expresamente para que RRF rescatara el match léxico "firma electrónica"/"webhook". Causa: las queries del golden set están en español, pero el corpus de muestra (`data/budgets_sample.json`) está enteramente en inglés (ver README). `to_tsvector('spanish', content)` sobre contenido inglés apenas encuentra solapamiento léxico real con una query en español — ni siquiera los anglicismos técnicos de la query ("webhook", "checkout") coinciden con palabras inglesas *distintas* en el chunk ("webhook handling" sí aparece en `BUD-2024-002`, pero el resto de la query en español no aporta términos que el chunk comparta). La rama léxica, tal como está configurada, es esencialmente inerte contra este corpus concreto.
2. **El reranking no mejoró nada y empeoró q02 de 1.00 a 0.40**, multiplicando la latencia mediana por ~19 (86 ms → 1689 ms). `cross-encoder/ms-marco-MiniLM-L-6-v2` está entrenado en pares pregunta-pasaje en inglés; evaluar pares (query en español, pasaje en inglés) es tan fuera de distribución para el cross-encoder como para la rama léxica — mismo problema de idioma, dos síntomas distintos.

**Esto no es un fallo del diseño, es el resultado esperado de una decisión ya documentada**: se configuró `spanish` (no `english`) porque es el idioma real de trabajo de ITA, a sabiendas de que el corpus de muestra actual es un placeholder en inglés. Esta medición es, en sí misma, la confirmación empírica de esa nota — y una razón más para no tratar estos números como definitivos hasta re-ejecutar el script con presupuestos históricos reales en español.

## 4. Conclusiones

**Para este proyecto, con el corpus de muestra actual, usaría la Configuración A (vectorial, sin reranking)**: misma precisión que la híbrida, precisión *mayor* que con reranking, y la latencia más baja con diferencia (86 ms frente a >1.6 s). La ganancia de relevancia del reranking no solo no compensa su coste de latencia en este caso concreto — es negativa, así que la decisión ni siquiera es un trade-off, es una elección dominada.

Dicho esto, esta conclusión está condicionada al desajuste de idioma diagnosticado arriba, no es una condena de la búsqueda híbrida ni del reranking como técnicas. Ambas piezas están construidas pensando en el corpus real que este sistema va a manejar (presupuestos históricos en español), no en el dataset de muestra en inglés usado aquí por conveniencia del ejercicio. Antes de decidir la configuración de producción definitiva, esta misma medición debería repetirse en cuanto haya presupuestos reales en español ingeridos — es plausible (aunque no seguro) que ahí la rama léxica sí rescate coincidencias de terminología exacta (números de norma, siglas, nombres de producto) que el embedding difumina, y que un cross-encoder mejor alineado con el idioma real del corpus deje de penalizar la precisión. Hasta entonces, la vectorial simple es la opción defendible: más simple, más barata, y — con los datos que tenemos hoy — mejor.

# Sesión 10 — Búsqueda híbrida y reranking: golden set y medición

> Igual que `arquitectura-actual.md` en la Sesión 9, este documento es el entregable
> evaluativo de la sesión: no repite el diseño (ver el README, sección
> ["Búsqueda híbrida y reranking (Sesión 10)"](README.md#búsqueda-híbrida-y-reranking-sesión-10)),
> se centra en los números y en la conclusión razonada.

## 1. Golden set y corpus

5 queries (`scripts/golden_set.json`), redactadas como descripciones de proyecto a
estimar — no copias literales de `project_summary` — y anotadas a mano contra los 15
`budget_id` reales del corpus de muestra. Criterio de anotación: *"Relevante si el
presupuesto histórico serviría como referencia directa de esfuerzo/alcance para estimar
el proyecto descrito en la query"*. Las propias queries están redactadas en español, con
los anglicismos técnicos naturales de este dominio (OAuth2, checkout, webhooks, HL7 FHIR).

| id | Query | `relevant_budget_ids` | Por qué |
| --- | --- | --- | --- |
| q01 | Banca móvil, login OAuth2, conectores PSD2, detección de fraude en tiempo real | `BUD-2024-001`, `BUD-2024-003` | 001 es el match directo (OAuth2+PSD2); 003 aporta la pieza de fraude en tiempo real que 001 no cubre |
| q02 | E-commerce con catálogo, carrito, checkout y devoluciones post-venta | `BUD-2024-005`, `BUD-2024-008` | 005 cubre catálogo/carrito/checkout; 008 cubre devoluciones — ningún presupuesto único cubre ambas piezas |
| q03 | Telemedicina, citas de pacientes, videoconsulta, integración HL7 FHIR | `BUD-2024-009` | Único match real; el sector healthcare tiene 4 presupuestos distintos (010 monitorización remota, 011 farmacia, 012 ensayos clínicos) que no deberían colarse — mismo dominio que `02_ambiguous.txt` de Sesión 9 |
| q04 | IoT industrial, telemetría de sensores, mantenimiento predictivo, anomalías | `BUD-2024-013`, `BUD-2024-015` | 013 es el match directo; 015 comparte el patrón ingesta-de-telemetría + modelo predictivo aunque sea de otro dominio (red eléctrica) |
| q05 | Firma electrónica para contratos vinculantes, webhooks, archivado de documentos | `BUD-2024-002` | Diseñada para probar el rescate léxico de RRF sobre un término específico, análoga al ejemplo "Stripe" del material de lectura — ver la Sección 3 para por qué esto no llegó a probarse realmente |

**Nota de honestidad:** esta anotación es un borrador razonado, no una revisión de negocio — el propio `annotated_by` del JSON lo deja explícito. Antes de tratarla como vara de medir definitiva, alguien del equipo comercial debería confirmarla o ajustarla.

**Dos corpus, mismos `budget_id`.** El ejercicio se corrió dos veces, contra dos versiones
del mismo corpus de 15 presupuestos que solo difieren en el idioma del texto narrativo
(`project_summary`, nombre/descripción de cada componente — sector, complejidad, stack
técnico y demás campos de esquema quedan igual en ambas, porque son valores de tipo, no
lenguaje natural):

- `data/budgets_sample.json` — el corpus original en **inglés** (ver Sección 4 para su
  procedencia).
- `data/budgets_sample_es.json` — traducción al **español** del mismo corpus, mismos
  `budget_id`, creada en esta sesión para poder aislar el efecto del idioma sin tocar el
  golden set ni las anotaciones.

Cada corrida parte de un `TRUNCATE` de `documents`/`chunks` y una reingesta con un solo
corpus activo a la vez (`scripts/query_examples.py --corpus <archivo>`); los dos nunca
convivieron en la misma base de datos durante la medición, para que los resultados de
cada fila de la tabla de la Sección 3 sean atribuibles a un único idioma de corpus.

## 2. Metodología

`scripts/measure_retrieval.py` ejecuta las 4 configuraciones exigidas por el enunciado contra las 5 queries, 3 corridas por query (mediana de latencia), llamando a `search_chunks(...)` directamente en proceso (sin pasar por la reformulación LLM, para medir solo el retriever). Precisión\@5 cuenta cada chunk del top-5 independientemente, sin deduplicar por `budget_id` — ver el docstring del script para la justificación de por qué no se corrige ese efecto.

| Config | Búsqueda | Reranking |
| --- | --- | --- |
| A | Vectorial | No |
| B | Híbrida (RRF) | No |
| C | Vectorial | Sí |
| D | Híbrida (RRF) | Sí |

## 3. Resultados

Dos ejecuciones reales (`docker compose run --rm ai_service python scripts/measure_retrieval.py`, `RAG_DISTANCE_THRESHOLD=0.6`, `RAG_RECALL_POOL_SIZE=50`, `RAG_RRF_K=60`, reranker `cross-encoder/ms-marco-MiniLM-L-6-v2`), una por corpus:

### Corpus en inglés (`data/budgets_sample.json`)

| Config | Búsqueda / Reranking | Precisión\@5 media | Latencia mediana (ms) |
| --- | --- | --- | --- |
| A | Vectorial / No | **0.76** | **86** |
| B | Híbrida / No | 0.76 | 91 |
| C | Vectorial / Sí | 0.64 | 1689 |
| D | Híbrida / Sí | 0.64 | 1624 |

### Corpus en español (`data/budgets_sample_es.json`)

| Config | Búsqueda / Reranking | Precisión\@5 media | Latencia mediana (ms) |
| --- | --- | --- | --- |
| A | Vectorial / No | 0.68 | 84 |
| B | Híbrida / No | 0.68 | 83 |
| C | Vectorial / Sí | **0.76** | 2044 |
| D | Híbrida / Sí | **0.76** | 2069 |

Desglose por query (precisión\@5; A/B y C/D son idénticos entre sí en las 5 queries, en ambos corpus — ver por qué en el punto 1 de abajo):

| Query | EN A/B | EN C/D | ES A/B | ES C/D |
| --- | --- | --- | --- | --- |
| q01 — banca móvil OAuth2/PSD2/fraude | 1.00 | 1.00 | 1.00 | 1.00 |
| q02 — e-commerce catálogo/carrito/devoluciones | 1.00 | 0.40 | 0.80 | 0.60 |
| q03 — telemedicina FHIR | 0.80 | 0.80 | 0.80 | 0.80 |
| q04 — IoT industrial/mantenimiento predictivo | 0.60 | 0.60 | 0.60 | 0.80 |
| q05 — firma electrónica/webhook | 0.40 | 0.40 | 0.20 | 0.60 |

### Dos hallazgos, y una corrección sobre la marcha

**1. La rama híbrida no cambió ni una sola precisión respecto a la vectorial pura, en ninguna query, en ninguno de los dos corpus.** La hipótesis inicial (antes de investigar) fue "desajuste de idioma entre la query en español y un corpus en inglés" — resultó **incorrecta**, y conviene dejar constancia del error en vez de esconderlo. La causa real, verificada directamente contra la base de datos:

```sql
-- Sobre el corpus en espanol, para la query completa de q05:
SELECT id FROM chunks
WHERE content_tsv @@ websearch_to_tsquery('spanish', '<texto completo de la query q05>');
-- 0 filas
```

Las 5 queries del golden set, en **los dos idiomas**, devuelven **cero** resultados de
`ChunkStore.search_fulltext` — no solo en el corpus "equivocado". `websearch_to_tsquery`
trata los términos no comillados como un **AND implícito**: una query de una frase
completa ("Sistema que necesita integración de firma electrónica para contratos
digitales legalmente vinculantes, con manejo de webhooks y archivado de documentos")
exige que un mismo chunk contenga las trece o catorce lexemas de esa frase a la vez, algo
que ningún chunk de ~100 palabras cumple casi nunca. La rama léxica no estaba "perdiendo"
por el idioma — estaba recibiendo una consulta que su propia semántica de `AND` no puede
satisfacer con texto libre largo, independientemente del idioma. Con `[[], vector_ids]`
como entrada, `reciprocal_rank_fusion` no tiene nada que fusionar: el resultado es,
matemáticamente, la lista vectorial sin cambios — de ahí que A≡B y C≡D en las cinco
queries, en ambos corpus.

**Esto es una limitación real del diseño actual, no del corpus.** `search_fulltext` (y
por tanto `search_mode="hybrid"`) tal como está implementado hoy solo puede aportar algo
cuando la query de entrada ya es corta y orientada a palabras clave (el propio ejemplo
"Stripe" del material de lectura asume eso), no cuando se le pasa una frase completa de
usuario o de golden set. Arreglarlo (p. ej. unir los términos con `OR` en vez de dejar el
`AND` implícito, o extraer keywords antes de construir la `tsquery`) es trabajo futuro,
fuera del alcance de esta sesión — se deja documentado aquí en vez de disimulado.

**2. El reranking sí cambia el resultado — y lo hace en direcciones opuestas según el idioma del corpus.** Sobre el corpus en inglés, reranking empeora la precisión media (0.76 → 0.64, q02 cae de 1.00 a 0.40) multiplicando la latencia por ~19. Sobre el corpus en español, reranking **mejora** la precisión media (0.68 → 0.76: q04 sube de 0.60 a 0.80, q05 sube de 0.20 a 0.60), a cambio de una latencia similar (~2 s). Esto sí es atribuible al idioma — pero al idioma del **cross-encoder**, no al de la búsqueda léxica: `cross-encoder/ms-marco-MiniLM-L-6-v2` se entrena sobre pares pregunta-pasaje en inglés exclusivamente (ver Sección 4, "¿el cross-encoder es multilingüe?"); evaluado con pasajes que ya están en su idioma de entrenamiento (el corpus en inglés) reordena razonablemente, pero cuando el mismatch de idioma se traslada al corpus en vez de a la query, el comportamiento se invierte — evidencia de que el modelo sí está usando alguna señal específica de idioma/superficie léxica, no solo semántica pura, y de que su comportamiento fuera de su dominio de entrenamiento es poco predecible en ambas direcciones.

## 4. Preguntas

### ¿De dónde salió el corpus original en inglés?

`data/budgets_sample.json` no tiene historial propio en `git`: la carpeta `data/` está en
`.gitignore` desde el inicio del proyecto, así que este fichero nunca se comprometió y no
hay ningún commit que documente su origen. Por el contenido y el estilo (15 presupuestos
sintéticos, uno por sector×tecnología, con nombres de cliente ficticios y cifras
redondas) es evidentemente un **dataset de fixture creado para el ejercicio** de las
Sesiones 06-08 (`embedding_pipeline`), no un dataset real de proyectos de ITA ni
descargado de una fuente pública. No hay forma de determinar desde este repositorio
quién lo escribió originalmente — lo más honesto es dejar constancia de que se desconoce
con certeza y remitir a los materiales/notas de las Sesiones 06-07 si se necesita
confirmar la autoría exacta.

`data/budgets_sample_es.json` (Sesión 10) es una traducción directa de ese mismo corpus,
creada en esta sesión: mismos `budget_id`, mismo `sector`/`complexity`/`tech_stack`
(valores de esquema, no se traducen), solo se tradujo el texto narrativo
(`project_summary`, nombre y descripción de cada componente).

### ¿El cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) es multilingüe?

**No.** Es un modelo `MiniLM` afinado sobre **MS MARCO**, un dataset de ranking de
pasajes exclusivamente en inglés — no hay ningún corpus de entrenamiento en español (ni
en ningún otro idioma) en su ficha de modelo. Esto explica directamente la Sección 3,
punto 2: sobre el corpus en inglés se comporta dentro de su dominio de entrenamiento
(aunque con una query en español) y termina degradando la precisión; sobre el corpus en
español el mismatch se invierte y, sorprendentemente, mejora la precisión — un resultado
que no se puede generalizar con confianza precisamente *porque* el modelo nunca vio
español en su entrenamiento.

Existe una alternativa multilingüe real: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`
(mMARCO, MS MARCO traducido automáticamente a 14 idiomas incluido el español) — es,
de hecho, el modelo que usa el repo de referencia del curso para esta misma sesión. No se
ha cambiado el modelo por defecto de este proyecto en esta sesión (no se pidió, y hacerlo
sin remedir sería solo sustituir una suposición por otra); queda anotado aquí como el
cambio más obvio a evaluar antes de decidir usar reranking en producción con presupuestos
reales en español.

## 5. Conclusiones

**Para este proyecto, con el corpus de muestra actual, seguiría usando la Configuración A (vectorial, sin reranking) como default de producción, pero por una razón más matizada de la que parecía al principio.** No es que la búsqueda híbrida "no funcione" — es que, con el `search_fulltext` de hoy, nunca llegó a activarse de verdad contra queries en lenguaje natural: A≡B siempre. El reranking sí se activó y sí cambió el resultado, pero en direcciones opuestas según el idioma del corpus (empeora en inglés, mejora en español) con un modelo que no es multilingüe — no hay base para confiar en ese resultado como algo que se repetirá con presupuestos reales, y multiplica la latencia entre ×19 y ×24 en ambos casos.

Antes de decidir la configuración de producción definitiva, dos cosas deberían resolverse — ninguna de las dos es una condena de las técnicas, ambas son huecos concretos en esta implementación, no en la idea:

1. **Arreglar `search_fulltext` para que la rama léxica realmente participe** con queries de lenguaje natural (OR en vez de AND implícito, o extracción de palabras clave antes de construir la `tsquery`) — sin esto, la comparación vectorial-vs-híbrida de este documento no ha probado nada todavía, solo ha confirmado que hoy son lo mismo.
2. **Repetir la medición con `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`** (multilingüe) en vez del modelo actual, sobre todo antes de activar reranking con presupuestos reales en español — el resultado favorable observado aquí en español bien podría no sostenerse, precisamente por venir de un modelo fuera de su idioma de entrenamiento.

Hasta que esas dos cosas se resuelvan, la vectorial simple sigue siendo la opción defendible: es la única de las cuatro configuraciones cuyo comportamiento no depende de una laguna de implementación (la rama léxica) o de una suposición no verificada (que un reranker en inglés se comporte razonablemente en español).

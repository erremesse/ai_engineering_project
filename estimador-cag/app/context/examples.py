ESTIMATION_EXAMPLES = [
    {
        "meeting_summary": """El cliente gestiona un almacén con 3.000 referencias y actualmente usa hojas Excel
compartidas que generan conflictos de versión continuamente. Necesitan una plataforma web
multiusuario con roles diferenciados (operario, supervisor, administrador), control de stock
en tiempo real, alertas de reposición automáticas cuando el stock baje del mínimo configurado,
historial de movimientos y un dashboard con los KPIs principales. Tienen previsto integrarla
con su ERP (SAP Business One) en una fase posterior. El plazo máximo es 4 meses.""",
        "estimation": """
## Estimación: Plataforma Web de Gestión de Inventario

### Resumen del proyecto
Sistema web multiusuario para gestión de inventario con control de stock en tiempo real,
alertas automáticas de reposición y dashboard de KPIs. Sustituye el flujo actual basado
en Excel. La integración con SAP Business One queda fuera de este alcance.

### Desglose de tareas

| Tarea                                      | Horas | Coste (€70/h) |
|--------------------------------------------|------:|-------------:|
| Diseño UX/UI (wireframes + prototipo)       |    40 |      2.800 € |
| Arquitectura y setup del proyecto           |    15 |      1.050 € |
| Backend API REST (CRUD productos y stock)   |    60 |      4.200 € |
| Sistema de roles y autenticación (JWT)      |    25 |      1.750 € |
| Motor de alertas de reposición              |    20 |      1.400 € |
| Historial de movimientos y auditoría        |    20 |      1.400 € |
| Dashboard con KPIs (gráficas, filtros)      |    35 |      2.450 € |
| Testing y QA                                |    30 |      2.100 € |
| Documentación y despliegue (staging + prod) |    15 |      1.050 € |

**Total: 260 horas — 18.200 €**

### Equipo recomendado
- 1 desarrollador senior full-stack (perfil principal)
- 1 desarrollador mid full-stack
- 1 diseñador UX (part-time, primeras 3 semanas)
- 1 QA engineer (part-time, últimas 3 semanas)

### Duración estimada
10-11 semanas (dentro del plazo de 4 meses)

### Riesgos y supuestos clave
- La integración SAP queda excluida; si se adelanta, requiere re-estimación (+40-60 h).
- El cliente debe proveer datos maestros de productos en formato CSV antes de la semana 3.
- Se asume infraestructura cloud gestionada por el cliente (AWS o Azure); si requiere
  DevOps dedicado, sumar ~20 h adicionales.
- El número de usuarios concurrentes estimado es <50; si escala más, revisar arquitectura.
"""
    },
    {
        "meeting_summary": """El cliente quiere una aplicación móvil para iOS y Android que ayude a los usuarios a
crear rutinas diarias y hacer seguimiento de sus hábitos. Funcionalidades clave: crear hábitos
personalizados con frecuencia (diaria, semanal, días concretos), racha de días consecutivos,
recordatorios push configurables, estadísticas semanales y mensuales, y un sistema de
logros/badges para motivar. El diseño debe ser "clean y motivador". Monetización futura
mediante suscripción premium, pero en la primera versión todo es gratuito. Plazo: 3 meses.""",
        "estimation": """
## Estimación: App Móvil de Seguimiento de Hábitos

### Resumen del proyecto
Aplicación nativa (iOS + Android) para creación y seguimiento de hábitos con gamificación,
notificaciones push y analíticas personales. Primera versión sin modelo de pago; la
arquitectura debe facilitar añadir suscripción en fases posteriores.

### Desglose de tareas

| Tarea                                              | Horas | Coste (€70/h) |
|----------------------------------------------------|------:|-------------:|
| Diseño UX/UI (flujos, componentes, guía de estilo) |    45 |      3.150 € |
| Backend API + base de datos (usuarios, hábitos)    |    40 |      2.800 € |
| Autenticación (email + OAuth Google/Apple)          |    20 |      1.400 € |
| Desarrollo iOS (Swift/SwiftUI)                      |    55 |      3.850 € |
| Desarrollo Android (Kotlin/Jetpack Compose)         |    55 |      3.850 € |
| Sistema de notificaciones push (FCM + APNs)         |    20 |      1.400 € |
| Motor de rachas, logros y estadísticas             |    25 |      1.750 € |
| Testing (unitario + integración + dispositivos)     |    30 |      2.100 € |
| Publicación en App Store y Google Play              |    10 |        700 € |

**Total: 300 horas — 21.000 €**

### Equipo recomendado
- 1 desarrollador iOS senior
- 1 desarrollador Android senior
- 1 desarrollador backend mid (API + BD)
- 1 diseñador UX/UI (dedicación completa primeras 4 semanas)

### Duración estimada
11-12 semanas (dentro del plazo de 3 meses si se arranca de inmediato)

### Riesgos y supuestos clave
- El proceso de revisión de App Store puede tardar 1-2 semanas; publicar con margen.
- Los logros y la lógica de rachas deben definirse completamente antes del sprint 2.
- Si se decide añadir sincronización offline, estimar +25 h adicionales.
- La arquitectura de backend usará Firebase o Supabase para reducir tiempo de desarrollo;
  migrar a infraestructura propia en el futuro requeriría re-estimación.
"""
    },
    {
        "meeting_summary": """Empresa de 200 empleados que necesita un portal interno de autoservicio de RRHH.
Los empleados deben poder consultar sus nóminas, solicitar vacaciones y ver el saldo
disponible, registrar ausencias y adjuntar justificantes. Los managers aprueban o rechazan
solicitudes y tienen una vista de su equipo. Integración con el sistema de nómina actual
(API REST ya documentada). Sin app móvil, solo web responsiva.""",
        "estimation": """
## Estimación: Portal de Autoservicio de RRHH

### Resumen del proyecto
Aplicación web responsiva para gestión de vacaciones, ausencias y consulta de nóminas.
Flujo de aprobación manager-empleado e integración con sistema de nómina existente.

### Desglose de tareas

| Tarea                                          | Horas | Coste (€70/h) |
|------------------------------------------------|------:|-------------:|
| Diseño UI/UX                                    |    30 |      2.100 € |
| Autenticación SSO (SAML/LDAP corporativo)       |    20 |      1.400 € |
| Módulo empleado (nóminas, vacaciones, ausencias)|    50 |      3.500 € |
| Módulo manager (aprobaciones, vista equipo)     |    30 |      2.100 € |
| Integración API nómina                          |    25 |      1.750 € |
| Notificaciones por email (solicitudes/respuestas)|   15 |      1.050 € |
| Testing y QA                                    |    25 |      1.750 € |
| Despliegue y documentación                      |    10 |        700 € |

**Total: 205 horas — 14.350 €**

### Equipo recomendado
- 1 desarrollador senior full-stack
- 1 desarrollador mid full-stack
- 1 diseñador UX (part-time)

### Duración estimada
8-9 semanas

### Riesgos y supuestos clave
- La documentación de la API de nómina debe estar disponible en la semana 1.
- SSO corporativo requiere acceso al servidor LDAP/AD del cliente para pruebas.
- Cambios en el flujo de aprobación tras inicio del desarrollo pueden impactar el plazo.
"""
    },
    {
        "meeting_summary": """Distribuidor industrial B2B que vende a talleres y pequeñas fábricas. Quieren digitalizar
su canal de ventas con una plataforma e-commerce propia. Catálogo de 8.000 referencias con
precios diferenciados por cliente (tarifa negociada). Los clientes deben ver solo sus precios.
Pedidos con aprobación interna, integración con su ERP (Sage) para sincronizar stock y
facturas, pasarela de pago (transferencia y tarjeta), área privada con historial de pedidos y
facturas descargables. El equipo comercial necesita un panel de administración para gestionar
clientes, tarifas y pedidos manualmente. Quieren salir al mercado en 5 meses.""",
        "estimation": """
## Estimación: Plataforma E-commerce B2B con Precios Diferenciados

### Resumen del proyecto
Plataforma e-commerce privada para distribución industrial B2B. Gestiona catálogos de 8.000
referencias, precios por cliente, flujo de pedido con aprobación interna y sincronización
bidireccional con Sage para stock y facturación. Panel de administración completo para el
equipo comercial.

### Desglose de tareas

| Tarea                                                    | Horas | Coste (€90/h) |
|----------------------------------------------------------|------:|-------------:|
| Arquitectura técnica y diseño de datos                    |    25 |      2.250 € |
| Diseño UX/UI (tienda + panel admin)                       |    60 |      5.400 € |
| Catálogo de productos (búsqueda, filtros, ficha)          |    50 |      4.500 € |
| Motor de precios por cliente (tarifas negociadas)         |    35 |      3.150 € |
| Carrito, checkout y flujo de aprobación de pedidos        |    45 |      4.050 € |
| Pasarela de pago (Stripe: tarjeta + SEPA transferencia)   |    25 |      2.250 € |
| Área privada cliente (historial, facturas PDF)            |    30 |      2.700 € |
| Panel de administración (clientes, tarifas, pedidos)      |    55 |      4.950 € |
| Integración ERP Sage (stock, pedidos, facturas)           |    60 |      5.400 € |
| Importación catálogo inicial (8.000 refs desde Excel/CSV) |    20 |      1.800 € |
| Testing y QA (funcional + carga)                          |    45 |      4.050 € |
| Despliegue, monitorización y documentación                |    20 |      1.800 € |

**Total: 470 horas — 42.300 €**

### Equipo recomendado
- 1 arquitecto/tech lead senior (perfil integración ERP)
- 2 desarrolladores senior full-stack
- 1 desarrollador mid (frontend + panel admin)
- 1 diseñador UX/UI
- 1 QA engineer (últimas 5 semanas)

### Duración estimada
16-18 semanas — el plazo de 5 meses es ajustado; requiere inicio inmediato y
sin cambios de alcance durante el desarrollo.

### Riesgos y supuestos clave
- La integración con Sage es el mayor riesgo técnico: requiere acceso al entorno de
  sandbox de Sage desde la semana 1 y un interlocutor técnico del cliente disponible.
- La migración de 8.000 referencias asume datos limpios en Excel. Si requieren limpieza
  o enriquecimiento, añadir 15-25 h.
- El motor de precios diferenciados es complejo; cambios en la lógica tras aprobación
  del diseño técnico afectarán el calendario.
- PCI-DSS: Stripe gestiona el cumplimiento de la pasarela; no se almacenan datos de
  tarjeta en nuestra infraestructura.
- Se excluye: app móvil, marketplace multi-vendedor, módulo de logística/envíos.
"""
    },
    {
        "meeting_summary": """Empresa SaaS de retail analytics que necesita un dashboard en tiempo real para que sus
clientes vean ventas, ticket medio, productos más vendidos y comparativa con el período
anterior. Los datos llegan desde un webhook de sus TPVs cada vez que se cierra una venta.
El dashboard debe actualizar los KPIs sin recargar la página. Multiempresa (cada cliente
ve solo sus datos). Exportación a Excel y PDF. Estimamos unos 50 clientes inicialmente
con picos de hasta 200 transacciones por minuto por cliente.""",
        "estimation": """
## Estimación: Dashboard de Analítica de Ventas en Tiempo Real

### Resumen del proyecto
Dashboard multiempresa con actualización en tiempo real vía WebSockets. Ingesta de eventos
de venta desde webhooks de TPV, procesamiento de KPIs y visualización interactiva con
comparativas temporales y exportación. Diseñado para soportar 50 clientes con picos de
200 tx/min.

### Desglose de tareas

| Tarea                                                   | Horas | Coste (€70/h) |
|---------------------------------------------------------|------:|-------------:|
| Diseño UX/UI del dashboard                               |    30 |      2.100 € |
| Arquitectura de ingesta (webhook receiver + cola)        |    20 |      1.400 € |
| Backend API + procesamiento de KPIs                      |    45 |      3.150 € |
| WebSockets / SSE para actualización en tiempo real       |    25 |      1.750 € |
| Frontend dashboard (gráficas, filtros, comparativas)     |    50 |      3.500 € |
| Aislamiento multiempresa (tenant isolation)              |    20 |      1.400 € |
| Exportación Excel y PDF                                  |    20 |      1.400 € |
| Testing de carga (200 tx/min × 50 clientes)             |    20 |      1.400 € |
| Testing funcional y QA                                   |    20 |      1.400 € |
| Despliegue y documentación                               |    10 |        700 € |

**Total: 260 horas — 18.200 €**

### Equipo recomendado
- 1 desarrollador senior backend (especialista en sistemas de eventos/tiempo real)
- 1 desarrollador mid frontend (React + librería de gráficas)
- 1 diseñador UX (part-time)

### Duración estimada
10-11 semanas

### Riesgos y supuestos clave
- El pico de 200 tx/min × 50 clientes = 10.000 eventos/min; requiere cola de mensajes
  (Redis Streams o similar) para desacoplar ingesta de procesamiento.
- El formato del webhook del TPV debe documentarse antes de la semana 2.
- Si se requiere retención histórica >12 meses con consultas analíticas rápidas,
  considerar columnar store (ClickHouse/BigQuery): +20-30 h de setup.
- La exportación PDF con gráficas requiere renderizado server-side (Puppeteer o similar).
"""
    },
]


def format_examples(examples: list[dict]) -> str:
    """Format estimation examples into a string suitable for injection into a system prompt."""
    parts: list[str] = []
    for i, example in enumerate(examples, start=1):
        parts.append(
            f"--- EXAMPLE {i} ---\n"
            f"Meeting Summary:\n{example['meeting_summary']}\n\n"
            f"Estimation:\n{example['estimation']}\n"
        )
    return "\n".join(parts)

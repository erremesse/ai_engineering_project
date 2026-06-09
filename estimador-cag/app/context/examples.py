ESTIMATION_EXAMPLES = [
    {
        "meeting_summary": "El cliente necesita una plataforma web de gestión de inventario...",
        "estimation": """
        ## Estimación: Plataforma de Gestión de Inventario
        
        ### Desglose de tareas:
        1. Diseño UI/UX: 40 horas
        2. Backend API (CRUD inventario): 60 horas
        3. Autenticación y roles: 20 horas
        4. Dashboard con métricas: 30 horas
        5. Testing y QA: 25 horas
        
        **Total estimado: 175 horas**
        **Equipo recomendado: 2 desarrolladores full-stack + 1 diseñador UX (part-time)**
        **Duración estimada: 6-8 semanas**
        """
    },
    {
        "meeting_summary": "El cliente quiere una aplicación móvil para seguimiento de hábitos...",
        "estimation": """
        ## Estimación: App Móvil de Seguimiento de Hábitos
        
        ### Desglose de tareas:
        1. Diseño UI/UX: 30 horas
        2. Desarrollo iOS: 50 horas
        3. Desarrollo Android: 50 horas
        4. Integración con backend (Firebase): 20 horas
        5. Testing y QA: 20 horas
        
        **Total estimado: 170 horas**
        **Equipo recomendado: 2 desarrolladores móviles (iOS y Android) + 1 diseñador UX (part-time)**
        **Duración estimada: 6-8 semanas**
        """
    }
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
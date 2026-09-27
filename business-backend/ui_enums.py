"""Enums de dominio que el frontend muestra en los formularios.

Copia ligera de app/schemas/estimation.py del servicio IA (Sesion 15): el
business-backend es un contenedor autocontenido y no importa `app.*`. Los
valores son el contrato HTTP con el servicio IA y deben coincidir.
"""

from enum import Enum


class ProjectType(str, Enum):
    MOBILE_APP = "mobile_app"
    WEB_SAAS = "web_saas"
    INTERNAL_TOOL = "internal_tool"
    DATA_PIPELINE = "data_pipeline"


class DetailLevel(str, Enum):
    SUMMARY = "summary"
    MEDIUM = "medium"
    DETAILED = "detailed"


class OutputFormat(str, Enum):
    PHASES_TABLE = "phases_table"
    LINE_ITEMS = "line_items"
    NARRATIVE = "narrative"

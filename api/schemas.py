from typing import Optional
from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    usuario: str = Field(..., min_length=1, examples=["alumno_1"])
    categoria: str = Field(..., examples=["Escuela"])
    subcategoria: str = Field(..., examples=["Proyecto / Código"])
    prioridad: int = Field(..., ge=1, le=3, examples=[2])
    complejidad: int = Field(..., ge=1, le=5, examples=[3])
    dia_semana: int = Field(..., ge=0, le=6, examples=[2])
    hora_creacion: int = Field(..., ge=0, le=23, examples=[14])
    dias_para_entrega: int = Field(..., ge=0, examples=[3])
    tareas_pendientes: int = Field(..., ge=0, examples=[2])


class PredictionResponse(BaseModel):
    probabilidad_completar: float
    riesgo_abandono: str
    tiempo_estimado_min: int


class TaskCreate(PredictionRequest):
    titulo: str = Field(..., min_length=1, examples=["Terminar API en FastAPI"])


class TaskCompleteRequest(BaseModel):
    completada: int = Field(..., ge=0, le=1, description="1 si se completó, 0 si se abandonó")
    tiempo_real_min: int = Field(..., ge=1, description="Minutos reales invertidos")


class TaskItem(TaskCreate):
    id: str
    probabilidad_completar: float
    riesgo_abandono: str
    tiempo_estimado_min: int
    estado: str = "pendiente"
    creada_en: str
import os
import json
import uuid
from datetime import datetime
from typing import List

import joblib
import pandas as pd
import mlflow
import mlflow.sklearn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

from api.schemas import (
    PredictionRequest,
    PredictionResponse,
    TaskCreate,
    TaskCompleteRequest,
    TaskItem,
)

app = FastAPI(
    title="Yarukoto MLOps API",
    description="API inteligente de gestión de tareas con predicción de cumplimiento y tiempo estimado.",
    version="1.0.0",
)

# Rutas de archivos de datos y modelos
ACTIVE_TASKS_PATH = "data/processed/active_tasks.json"
NEW_TASKS_CSV_PATH = "data/processed/new_tasks.csv"
REF_TASKS_CSV_PATH = "data/raw/reference_tasks.csv"
REPORT_HTML_PATH = "reports/monitoring_report.html"

FEATURE_COLS = [
    "usuario",
    "categoria",
    "subcategoria",
    "prioridad",
    "complejidad",
    "dia_semana",
    "hora_creacion",
    "dias_para_entrega",
    "tareas_pendientes",
]


class ModelManager:
    def __init__(self):
        self.classifier = None
        self.regressor = None
        self.model_source = "unloaded"
        self.load_models()

    def load_models(self):
        tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
        try:
            mlflow.set_tracking_uri(tracking_uri)
            self.classifier = mlflow.sklearn.load_model("models:/yarukoto_classifier@production")
            self.regressor = mlflow.sklearn.load_model("models:/yarukoto_regressor@production")
            self.model_source = "MLflow Registry (@production)"
            print("Modelos cargados exitosamente desde MLflow Registry (@production).")
        except Exception as e:
            print(f"Aviso: No se pudo conectar a MLflow Registry ({e}). Usando respaldo local models/...")
            if os.path.exists("models/classifier.joblib") and os.path.exists("models/regressor.joblib"):
                self.classifier = joblib.load("models/classifier.joblib")
                self.regressor = joblib.load("models/regressor.joblib")
                self.model_source = "Local Joblib Backup (models/)"
                print("Modelos cargados desde models/*.joblib.")
            else:
                raise RuntimeError("No se encontraron modelos entrenados. Ejecuta 'python src/train.py' primero.")


model_manager = ModelManager()


# --- Funciones auxiliares de persistencia ---
def _read_active_tasks() -> List[dict]:
    os.makedirs("data/processed", exist_ok=True)
    if not os.path.exists(ACTIVE_TASKS_PATH):
        return []
    with open(ACTIVE_TASKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_active_tasks(tasks: List[dict]):
    os.makedirs("data/processed", exist_ok=True)
    with open(ACTIVE_TASKS_PATH, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)


def _append_ground_truth(row: dict):
    os.makedirs("data/processed", exist_ok=True)
    df_row = pd.DataFrame([row])
    header = not os.path.exists(NEW_TASKS_CSV_PATH)
    df_row.to_csv(NEW_TASKS_CSV_PATH, mode="a", header=header, index=False)


def _run_inference(payload: PredictionRequest) -> PredictionResponse:
    df = pd.DataFrame([payload.model_dump()])[FEATURE_COLS]
    prob = float(model_manager.classifier.predict_proba(df)[0][1])
    est_min = max(5, int(round(float(model_manager.regressor.predict(df)[0]))))

    if prob >= 0.75:
        riesgo = "Bajo (Alta probabilidad)"
    elif prob >= 0.50:
        riesgo = "Moderado"
    else:
        riesgo = "Alto (Riesgo de posponer)"

    return PredictionResponse(
        probabilidad_completar=round(prob, 4),
        riesgo_abandono=riesgo,
        tiempo_estimado_min=est_min,
    )


# --- Endpoints de la API ---
@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "Yarukoto MLOps",
        "model_source": model_manager.model_source,
    }


@app.post("/api/models/reload")
def reload_models():
    model_manager.load_models()
    return {"status": "reloaded", "model_source": model_manager.model_source}


@app.post("/api/predict", response_model=PredictionResponse)
def predict_task(payload: PredictionRequest):
    return _run_inference(payload)


@app.get("/api/tasks/{usuario}", response_model=List[TaskItem])
def list_user_tasks(usuario: str):
    tasks = _read_active_tasks()
    return [t for t in tasks if t["usuario"].lower() == usuario.lower() and t["estado"] == "pendiente"]


@app.post("/api/tasks", response_model=TaskItem)
def create_task(payload: TaskCreate):
    tasks = _read_active_tasks()
    user_pending = [t for t in tasks if t["usuario"].lower() == payload.usuario.lower() and t["estado"] == "pendiente"]

    # Sincroniza tareas_pendientes real del usuario
    payload.tareas_pendientes = len(user_pending)
    pred = _run_inference(payload)

    new_task = {
        "id": str(uuid.uuid4())[:8],
        **payload.model_dump(),
        "probabilidad_completar": pred.probabilidad_completar,
        "riesgo_abandono": pred.riesgo_abandono,
        "tiempo_estimado_min": pred.tiempo_estimado_min,
        "estado": "pendiente",
        "creada_en": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    tasks.append(new_task)
    _write_active_tasks(tasks)
    return new_task


@app.post("/api/tasks/{task_id}/complete")
def complete_task(task_id: str, body: TaskCompleteRequest):
    tasks = _read_active_tasks()
    target_task = None

    for t in tasks:
        if t["id"] == task_id and t["estado"] == "pendiente":
            t["estado"] = "completada" if body.completada == 1 else "abandonada"
            target_task = t
            break

    if not target_task:
        raise HTTPException(status_code=404, detail="Tarea pendiente no encontrada")

    _write_active_tasks(tasks)

    # Guardar registro real (Ground Truth) para monitoreo y reentrenamiento en Airflow
    ground_truth_record = {col: target_task[col] for col in FEATURE_COLS}
    ground_truth_record["completada"] = body.completada
    ground_truth_record["tiempo_real_min"] = body.tiempo_real_min
    _append_ground_truth(ground_truth_record)

    return {
        "message": "Tarea cerrada y registrada en el dataset de entrenamiento continuo.",
        "task_id": task_id,
        "completada": body.completada,
        "tiempo_real_min": body.tiempo_real_min,
    }


@app.get("/api/dataset/history")
def get_dataset_history(limit: int = 20):
    if os.path.exists(NEW_TASKS_CSV_PATH):
        df = pd.read_csv(NEW_TASKS_CSV_PATH)
        source = "Nuevas tareas reales (new_tasks.csv)"
    elif os.path.exists(REF_TASKS_CSV_PATH):
        df = pd.read_csv(REF_TASKS_CSV_PATH)
        source = "Dataset de referencia inicial (reference_tasks.csv)"
    else:
        return {"source": "empty", "total": 0, "records": []}

    return {
        "source": source,
        "total": len(df),
        "records": df.tail(limit).iloc[::-1].to_dict(orient="records"),
    }


@app.get("/monitoring", response_class=HTMLResponse)
def view_monitoring_report():
    if os.path.exists(REPORT_HTML_PATH):
        with open(REPORT_HTML_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(
        content="""
        <html><body style="font-family:sans-serif;background:#0f172a;color:#f8fafc;padding:40px;text-align:center;">
        <h2>Reporte de Monitoreo (Evidently AI) aún no generado</h2>
        <p>Completa algunas tareas en Yarukoto y ejecuta <code>python src/monitor.py</code> o el DAG de Airflow.</p>
        </body></html>
        """
    )


# --- Servir Frontend Estático ---
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def serve_frontend():
    index_path = "frontend/index.html"
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Yarukoto MLOps API activa. Visita /docs para probar los endpoints."}
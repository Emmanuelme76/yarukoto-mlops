import os
import json
import pytest
from fastapi.testclient import TestClient

from src.generate_data import generate_synthetic_tasks
from src.train import train_and_register
from api.main import app, ACTIVE_TASKS_PATH, NEW_TASKS_CSV_PATH


@pytest.fixture(scope="session", autouse=True)
def setup_models_and_backup_data():
    """Asegura que los modelos existan antes de correr los tests y protege datos existentes."""
    os.makedirs("data/raw", exist_ok=True)
    if not os.path.exists("data/raw/reference_tasks.csv"):
        df = generate_synthetic_tasks(n_samples=200, seed=42)
        df.to_csv("data/raw/reference_tasks.csv", index=False)

    if not os.path.exists("models/classifier.joblib") or not os.path.exists("models/regressor.joblib"):
        train_and_register()

    # Respaldar archivos en data/processed si existen localmente
    active_backup = None
    csv_backup = None
    if os.path.exists(ACTIVE_TASKS_PATH):
        with open(ACTIVE_TASKS_PATH, "r", encoding="utf-8") as f:
            active_backup = f.read()
    if os.path.exists(NEW_TASKS_CSV_PATH):
        with open(NEW_TASKS_CSV_PATH, "r", encoding="utf-8") as f:
            csv_backup = f.read()

    yield

    # Restaurar estado original después de ejecutar pytest
    if active_backup is not None:
        with open(ACTIVE_TASKS_PATH, "w", encoding="utf-8") as f:
            f.write(active_backup)
    elif os.path.exists(ACTIVE_TASKS_PATH):
        os.remove(ACTIVE_TASKS_PATH)

    if csv_backup is not None:
        with open(NEW_TASKS_CSV_PATH, "w", encoding="utf-8") as f:
            f.write(csv_backup)
    elif os.path.exists(NEW_TASKS_CSV_PATH):
        os.remove(NEW_TASKS_CSV_PATH)


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "Yarukoto MLOps"


def test_predict_standard_task():
    payload = {
        "usuario": "alumno_1",
        "categoria": "Escuela",
        "subcategoria": "Proyecto / Código",
        "prioridad": 3,
        "complejidad": 4,
        "dia_semana": 2,
        "hora_creacion": 15,
        "dias_para_entrega": 2,
        "tareas_pendientes": 3,
    }
    response = client.post("/api/predict", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert 0.0 <= result["probabilidad_completar"] <= 1.0
    assert result["tiempo_estimado_min"] >= 5
    assert isinstance(result["riesgo_abandono"], str)


def test_predict_unseen_user_and_custom_subcategory():
    """Verifica que OneHotEncoder(handle_unknown='ignore') soporte usuarios y subcategorías nuevas."""
    payload = {
        "usuario": "usuario_nuevo_ci",
        "categoria": "Trabajo",
        "subcategoria": "Subcategoria_Inedita_Test",
        "prioridad": 2,
        "complejidad": 3,
        "dia_semana": 4,
        "hora_creacion": 10,
        "dias_para_entrega": 5,
        "tareas_pendientes": 1,
    }
    response = client.post("/api/predict", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert 0.0 <= result["probabilidad_completar"] <= 1.0
    assert result["tiempo_estimado_min"] >= 5


def test_full_task_lifecycle_and_ground_truth():
    """Prueba crear una tarea, listarla y cerrarla capturando el Ground Truth."""
    create_payload = {
        "titulo": "Tarea de prueba automatizada CI",
        "usuario": "test_runner",
        "categoria": "Personal",
        "subcategoria": "Ejercicio",
        "prioridad": 2,
        "complejidad": 2,
        "dia_semana": 5,
        "hora_creacion": 9,
        "dias_para_entrega": 1,
        "tareas_pendientes": 0,
    }
    create_res = client.post("/api/tasks", json=create_payload)
    assert create_res.status_code == 200
    created = create_res.json()
    task_id = created["id"]

    # Verificar que aparece en la lista de pendientes
    list_res = client.get("/api/tasks/test_runner")
    assert list_res.status_code == 200
    assert any(t["id"] == task_id for t in list_res.json())

    # Cerrar tarea y confirmar tiempo real
    complete_res = client.post(
        f"/api/tasks/{task_id}/complete",
        json={"completada": 1, "tiempo_real_min": 42},
    )
    assert complete_res.status_code == 200
    assert complete_res.json()["tiempo_real_min"] == 42
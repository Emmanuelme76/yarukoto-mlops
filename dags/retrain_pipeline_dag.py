import os
import sys
import urllib.request
from datetime import datetime, timedelta
import pandas as pd

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator

# Asegurar que Airflow pueda importar nuestros módulos en src/
PROJECT_ROOT = os.getenv("YARUKOTO_PROJECT_ROOT", "/opt/airflow/project")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())


default_args = {
    "owner": "yarukoto_mlops",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


def task_check_new_data(**context):
    """Verifica el volumen de tareas reales nuevas capturadas por la aplicación."""
    os.chdir(PROJECT_ROOT) if os.path.exists(PROJECT_ROOT) else None
    new_tasks_path = "data/processed/new_tasks.csv"

    new_count = 0
    if os.path.exists(new_tasks_path):
        df = pd.read_csv(new_tasks_path)
        new_count = len(df)

    dag_run = context.get("dag_run")
    conf = dag_run.conf if (dag_run and dag_run.conf) else {}
    force_retrain = bool(conf.get("force_retrain", False))
    simulate_drift = bool(conf.get("simulate_drift", False))

    print(f"Tareas reales nuevas detectadas: {new_count} | force_retrain={force_retrain}")
    ti = context["ti"]
    ti.xcom_push(key="new_tasks_count", value=new_count)
    ti.xcom_push(key="force_retrain", value=force_retrain)
    ti.xcom_push(key="simulate_drift", value=simulate_drift)


def task_evaluate_data_drift(**context):
    """Ejecuta Evidently AI para detectar Data Drift y actualizar el reporte HTML."""
    os.chdir(PROJECT_ROOT) if os.path.exists(PROJECT_ROOT) else None
    from src.monitor import run_monitoring

    ti = context["ti"]
    simulate_drift = ti.xcom_pull(task_ids="check_new_data", key="simulate_drift") or False

    summary = run_monitoring(simulate_drift=simulate_drift)
    drift_detected = bool(summary.get("dataset_drift", False))

    print(f"Resultado Evidently AI -> Data Drift detectado: {drift_detected}")
    ti.xcom_push(key="drift_detected", value=drift_detected)


def task_branch_decision(**context):
    """Decide si se dispara el reentrenamiento continuo o si el modelo actual sigue vigente."""
    ti = context["ti"]
    new_count = ti.xcom_pull(task_ids="check_new_data", key="new_tasks_count") or 0
    force_retrain = ti.xcom_pull(task_ids="check_new_data", key="force_retrain") or False
    drift_detected = ti.xcom_pull(task_ids="evaluate_data_drift", key="drift_detected") or False

    if force_retrain or drift_detected or new_count >= 10:
        print(
            f"Disparando reentrenamiento (drift={drift_detected}, "
            f"nuevas_tareas={new_count}, forzado={force_retrain})..."
        )
        return "retrain_and_promote_models"

    print("Sin drift significativo y menos de 10 tareas nuevas. Se mantiene el modelo actual.")
    return "skip_retraining"


def task_retrain_models(**context):
    """Ejecuta src/train.py para reentrenar con datos combinados y promocionar en MLflow."""
    os.chdir(PROJECT_ROOT) if os.path.exists(PROJECT_ROOT) else None
    from src.train import train_and_register

    train_and_register()
    print("Reentrenamiento completado y promovido a @production en MLflow.")


def task_reload_api_models(**context):
    """Notifica al servicio FastAPI para recargar en caliente los modelos recién entrenados."""
    api_url = os.getenv("YARUKOTO_API_URL", "http://yarukoto-web:8000/api/models/reload")
    try:
        req = urllib.request.Request(api_url, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            print(f"FastAPI recargó modelos correctamente: {body}")
    except Exception as e:
        print(f"Aviso: No se pudo notificar a FastAPI en {api_url} ({e}). Se cargará al reiniciar.")


with DAG(
    dag_id="yarukoto_continuous_retraining",
    default_args=default_args,
    description="Monitoreo con Evidently AI y reentrenamiento continuo en MLflow para Yarukoto MLOps",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["yarukoto", "mlops", "evidently", "mlflow"],
) as dag:

    check_new_data = PythonOperator(
        task_id="check_new_data",
        python_callable=task_check_new_data,
    )

    evaluate_data_drift = PythonOperator(
        task_id="evaluate_data_drift",
        python_callable=task_evaluate_data_drift,
    )

    branch_retrain_decision = BranchPythonOperator(
        task_id="branch_retrain_decision",
        python_callable=task_branch_decision,
    )

    retrain_and_promote_models = PythonOperator(
        task_id="retrain_and_promote_models",
        python_callable=task_retrain_models,
    )

    reload_fastapi_models = PythonOperator(
        task_id="reload_fastapi_models",
        python_callable=task_reload_api_models,
    )

    skip_retraining = EmptyOperator(
        task_id="skip_retraining",
    )

    check_new_data >> evaluate_data_drift >> branch_retrain_decision
    branch_retrain_decision >> retrain_and_promote_models >> reload_fastapi_models
    branch_retrain_decision >> skip_retraining
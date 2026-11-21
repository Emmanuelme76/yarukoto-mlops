import os
import sys
import json
import argparse
import numpy as np
import pandas as pd

# Soporte compatible para Evidently >= 0.7 (API moderna) y <= 0.6 (API clásica)
try:
    from evidently import Report
    from evidently.presets import DataDriftPreset
    EVIDENTLY_V2 = True
except ImportError:
    from evidently.report import Report
    from evidently.metric_preset import DataDriftPreset
    EVIDENTLY_V2 = False


REF_PATH = "data/raw/reference_tasks.csv"
NEW_PATH = "data/processed/new_tasks.csv"
REPORT_HTML_PATH = "reports/monitoring_report.html"
REPORT_JSON_PATH = "reports/monitoring_summary.json"

MONITORED_COLUMNS = [
    "usuario",
    "categoria",
    "subcategoria",
    "prioridad",
    "complejidad",
    "dia_semana",
    "hora_creacion",
    "dias_para_entrega",
    "tareas_pendientes",
    "completada",
    "tiempo_real_min",
]


def _create_drifted_sample(ref_df: pd.DataFrame, n_rows: int = 120) -> pd.DataFrame:
    """Genera un lote de prueba con cambio de hábitos (Data Drift) para demostraciones."""
    np.random.seed(99)
    sample = ref_df.sample(n=min(n_rows, len(ref_df)), random_state=99).copy()
    # Simular cambio de hábitos: tareas mucho más complejas y mayor carga pendiente
    sample["complejidad"] = np.random.choice([4, 5], size=len(sample), p=[0.4, 0.6])
    sample["tareas_pendientes"] = sample["tareas_pendientes"] + np.random.randint(4, 9, size=len(sample))
    sample["tiempo_real_min"] = (sample["tiempo_real_min"] * 1.45).astype(int)
    return sample


def run_monitoring(simulate_drift: bool = False) -> dict:
    if not os.path.exists(REF_PATH):
        raise FileNotFoundError(f"No se encontró el dataset de referencia en {REF_PATH}")

    ref_df = pd.read_csv(REF_PATH)[MONITORED_COLUMNS]

    if simulate_drift:
        print("Modo demostración: generando datos actuales con Data Drift simulado...")
        curr_df = _create_drifted_sample(ref_df)
    elif os.path.exists(NEW_PATH):
        new_df = pd.read_csv(NEW_PATH)
        if len(new_df) >= 15:
            curr_df = new_df[MONITORED_COLUMNS]
            print(f"Evaluando {len(curr_df)} tareas reales capturadas en producción.")
        else:
            print(
                f"Solo hay {len(new_df)} tareas nuevas en {NEW_PATH} (mínimo recomendado: 15). "
                "Combinando con una muestra reciente para estabilidad estadística..."
            )
            filler = ref_df.sample(n=50, random_state=42)
            curr_df = pd.concat([filler, new_df[MONITORED_COLUMNS]], ignore_index=True)
    else:
        print("Aún no existe new_tasks.csv. Usando muestra de referencia inicial sin drift.")
        curr_df = ref_df.sample(n=100, random_state=42)

    os.makedirs("reports", exist_ok=True)

    # Ejecutar reporte de Data Drift con Evidently AI
    report = Report(metrics=[DataDriftPreset()])

    if EVIDENTLY_V2:
        snapshot = report.run(reference_data=ref_df, current_data=curr_df)
        snapshot.save_html(REPORT_HTML_PATH)
        result_dict = snapshot.dict()
    else:
        report.run(reference_data=ref_df, current_data=curr_df)
        report.save_html(REPORT_HTML_PATH)
        result_dict = report.as_dict()

    # Extraer resumen de drift detectado
    drift_detected = False
    drifted_columns = 0
    total_columns = len(MONITORED_COLUMNS)

    for metric in result_dict.get("metrics", []):
        res = metric.get("result", metric.get("value", {}))
        if isinstance(res, dict):
            if "dataset_drift" in res:
                drift_detected = bool(res["dataset_drift"])
                drifted_columns = int(res.get("number_of_drifted_columns", 0))
                total_columns = int(res.get("number_of_columns", total_columns))
                break
            elif "count" in res and "share" in res:
                drifted_columns = int(res["count"])
                drift_detected = float(res["share"]) >= 0.30
                break

    summary = {
        "dataset_drift": drift_detected,
        "drifted_columns": drifted_columns,
        "total_columns": total_columns,
        "current_rows": len(curr_df),
        "report_path": REPORT_HTML_PATH,
    }

    with open(REPORT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Reporte HTML guardado en: {REPORT_HTML_PATH}")
    print(f"Resumen de monitoreo: {summary}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitoreo de Data Drift con Evidently AI")
    parser.add_argument(
        "--simulate-drift",
        action="store_true",
        help="Simula un cambio de distribución para probar alertas de Data Drift",
    )
    args = parser.parse_args()
    run_monitoring(simulate_drift=args.simulate_drift)
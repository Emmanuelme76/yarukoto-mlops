import os
import joblib
import numpy as np
import pandas as pd
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.ensemble import (
    RandomForestClassifier,
    GradientBoostingClassifier,
    RandomForestRegressor,
    GradientBoostingRegressor,
)
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    roc_auc_score,
    mean_absolute_error,
    root_mean_squared_error,
    r2_score,
)


CATEGORICAL_FEATURES = ["usuario", "categoria", "subcategoria"]
NUMERIC_FEATURES = [
    "prioridad",
    "complejidad",
    "dia_semana",
    "hora_creacion",
    "dias_para_entrega",
    "tareas_pendientes",
]
ALL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES

# Tipos confiables requeridos por MLflow/skops para modelos basados en árboles
TRUSTED_TREE_TYPES = ["sklearn.tree._tree.Tree"]


def load_training_data() -> pd.DataFrame:
    ref_path = "data/raw/reference_tasks.csv"
    new_path = "data/processed/new_tasks.csv"

    df = pd.read_csv(ref_path)
    if os.path.exists(new_path):
        new_df = pd.read_csv(new_path)
        if not new_df.empty:
            df = pd.concat([df, new_df], ignore_index=True)
            print(f"Datos combinados: {len(df)} registros totales (incluyendo {len(new_df)} tareas reales nuevas).")
    else:
        print(f"Usando dataset de referencia: {len(df)} registros.")

    return df


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
            ("num", StandardScaler(), NUMERIC_FEATURES),
        ]
    )


def promote_to_production(client: MlflowClient, model_name: str, run_id: str, artifact_name: str):
    model_uri = f"runs:/{run_id}/{artifact_name}"
    registered = mlflow.register_model(model_uri=model_uri, name=model_name)
    client.set_registered_model_alias(
        name=model_name,
        alias="production",
        version=registered.version,
    )
    print(f"Modelo '{model_name}' v{registered.version} promovido al alias @production.")


def train_and_register():
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("Yarukoto_MLOps_Experiment")
    client = MlflowClient()

    df = load_training_data()
    X = df[ALL_FEATURES]
    y_class = df["completada"]
    y_reg = df["tiempo_real_min"]

    X_train, X_test, yc_train, yc_test, yr_train, yr_test = train_test_split(
        X, y_class, y_reg, test_size=0.2, random_state=42
    )

    os.makedirs("models", exist_ok=True)

    # =========================================================================
    # 1. ENTRENAMIENTO DE CLASIFICACIÓN (Probabilidad de completar la tarea)
    # =========================================================================
    classifiers = {
        "RandomForestClassifier": RandomForestClassifier(n_estimators=150, max_depth=10, random_state=42),
        "GradientBoostingClassifier": GradientBoostingClassifier(n_estimators=120, learning_rate=0.08, random_state=42),
    }

    best_clf_f1 = -1.0
    best_clf_run_id = None
    best_clf_pipeline = None

    for name, model in classifiers.items():
        with mlflow.start_run(run_name=f"Clf_{name}") as run:
            pipeline = Pipeline([
                ("preprocessor", build_preprocessor()),
                ("model", model),
            ])
            pipeline.fit(X_train, yc_train)

            preds = pipeline.predict(X_test)
            probs = pipeline.predict_proba(X_test)[:, 1]

            acc = accuracy_score(yc_test, preds)
            f1 = f1_score(yc_test, preds)
            auc = roc_auc_score(yc_test, probs)

            mlflow.log_param("task_type", "classification")
            mlflow.log_param("algorithm", name)
            mlflow.log_param("total_samples", len(df))
            mlflow.log_metric("accuracy", acc)
            mlflow.log_metric("f1_score", f1)
            mlflow.log_metric("roc_auc", auc)

            mlflow.sklearn.log_model(
                pipeline,
                name="classifier_model",
                skops_trusted_types=TRUSTED_TREE_TYPES,
            )
            print(f"[Clasificación - {name}] Accuracy: {acc:.4f} | F1: {f1:.4f} | ROC-AUC: {auc:.4f}")

            if f1 > best_clf_f1:
                best_clf_f1 = f1
                best_clf_run_id = run.info.run_id
                best_clf_pipeline = pipeline

    promote_to_production(client, "yarukoto_classifier", best_clf_run_id, "classifier_model")
    joblib.dump(best_clf_pipeline, "models/classifier.joblib")

    # =========================================================================
    # 2. ENTRENAMIENTO DE REGRESIÓN (Estimación de minutos reales)
    # =========================================================================
    regressors = {
        "RandomForestRegressor": RandomForestRegressor(n_estimators=150, max_depth=12, random_state=42),
        "GradientBoostingRegressor": GradientBoostingRegressor(n_estimators=150, learning_rate=0.08, random_state=42),
    }

    best_reg_mae = float("inf")
    best_reg_run_id = None
    best_reg_pipeline = None

    for name, model in regressors.items():
        with mlflow.start_run(run_name=f"Reg_{name}") as run:
            pipeline = Pipeline([
                ("preprocessor", build_preprocessor()),
                ("model", model),
            ])
            pipeline.fit(X_train, yr_train)

            preds = pipeline.predict(X_test)

            mae = mean_absolute_error(yr_test, preds)
            rmse = root_mean_squared_error(yr_test, preds)
            r2 = r2_score(yr_test, preds)

            mlflow.log_param("task_type", "regression")
            mlflow.log_param("algorithm", name)
            mlflow.log_param("total_samples", len(df))
            mlflow.log_metric("mae_minutes", mae)
            mlflow.log_metric("rmse_minutes", rmse)
            mlflow.log_metric("r2_score", r2)

            mlflow.sklearn.log_model(
                pipeline,
                name="regressor_model",
                skops_trusted_types=TRUSTED_TREE_TYPES,
            )
            print(f"[Regresión - {name}] MAE: {mae:.2f} min | RMSE: {rmse:.2f} min | R2: {r2:.4f}")

            if mae < best_reg_mae:
                best_reg_mae = mae
                best_reg_run_id = run.info.run_id
                best_reg_pipeline = pipeline

    promote_to_production(client, "yarukoto_regressor", best_reg_run_id, "regressor_model")
    joblib.dump(best_reg_pipeline, "models/regressor.joblib")
    print("\nEntrenamiento completado. Modelos guardados en MLflow Registry y en models/.")


if __name__ == "__main__":
    train_and_register()
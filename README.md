# Yarukoto MLOps (やること) — Sistema Inteligente de Gestión de Tareas

**Yarukoto MLOps** es una aplicación web de productividad personal impulsada por aprendizaje automático y un ciclo completo de **MLOps** (*Continuous Integration, Continuous Delivery y Continuous Training*).

El sistema predice en tiempo real la **probabilidad de que un usuario complete una tarea** (clasificación binaria) y el **tiempo real en minutos que le tomará terminarla** (regresión), adaptándose a los hábitos individuales de cada perfil de usuario y retroalimentando los modelos con los tiempos reales capturados en producción.

- **Demo en vivo (Nube):** https://yarukoto-mlops.onrender.com
- **Documentación interactiva API (Swagger):** https://yarukoto-mlops.onrender.com/docs

---

## Arquitectura del Sistema MLOps

```text
+-------------------+       POST /api/predict        +-----------------------+
|   Frontend Web    | -----------------------------> |    FastAPI Backend    |
| (Tailwind + JS)   | <----------------------------- |  (api/main.py)        |
| - Login x usuario |       POST /api/tasks          +-----------+-----------+
| - Cronómetro      |       POST /complete                       | Carga @production
+-------------------+                                            |
        ^                                                        v
        | /monitoring (iframe)                       +-----------------------+
        |                                            |   MLflow Registry     |
+-------+-----------+       Detecta Data Drift       | - yarukoto_classifier |
|   Evidently AI    | <----------------------------- | - yarukoto_regressor  |
|  (src/monitor.py) |                                +-----------+-----------+
+-------------------+                                            ^
        ^                                                        | Reentrena y
        |                                                        | promociona
        |           +--------------------------------+           |
        +---------- |        Apache Airflow          | ----------+
                    | (dags/retrain_pipeline_dag.py) |
                    +--------------------------------+
```

### Stack Tecnológico

| Capa | Herramienta | Propósito en el proyecto |
| :--- | :--- | :--- |
| **Control de Versiones & CI/CD** | Git (`main` / `dev`) + GitHub Actions | Flujo de ramas, pruebas automatizadas con `pytest`, validación de build Docker y despliegue continuo. |
| **Versionado de Datos** | DVC (*Data Version Control*) | Versionado y trazabilidad del dataset base (`data/raw/reference_tasks.csv`). |
| **Experimentación y Modelos** | Scikit-Learn + MLflow + Model Registry | Comparación de algoritmos (`RandomForest` vs `GradientBoosting`), preprocesamiento con `OneHotEncoder(handle_unknown="ignore")` y promoción automática al alias `@production`. |
| **Backend & Inferencia** | FastAPI + Pydantic + Uvicorn | API REST de baja latencia con validación estricta de esquemas y captura de *Ground Truth*. |
| **Frontend** | HTML5 + Tailwind CSS + Vanilla JS | Interfaz responsiva con cambio rápido de usuario, subcategoría híbrida, predicción en vivo y cronómetro por tarea. |
| **Monitoreo y Observabilidad** | Evidently AI (`DataDriftPreset`) | Detección estadística de *Data Drift* entre datos históricos y producción, con reporte HTML incrustado en la web. |
| **Orquestación** | Apache Airflow | DAG diario con `BranchPythonOperator` que evalúa nuevas tareas, ejecuta monitoreo y dispara reentrenamiento continuo. |
| **Contenedores y Nube** | Docker + Docker Compose + Render | Empaquetado reproducible de la aplicación y despliegue público en la nube. |

## Estructura del Repositorio
```Plaintext
yarukoto-mlops/
├── .github/workflows/
│   └── ci.yml                      # Pipeline CI/CD (Pytest + Docker build + Deploy Hook)
├── api/
│   ├── main.py                     # Endpoints REST, inferencia MLflow y servidor estático
│   └── schemas.py                  # Modelos de validación Pydantic
├── dags/
│   └── retrain_pipeline_dag.py     # DAG de Apache Airflow para monitoreo y reentrenamiento
├── data/
│   └── raw/
│       └── reference_tasks.csv.dvc # Puntero de dataset versionado con DVC
├── frontend/
│   ├── index.html                  # Interfaz web principal (Tareas, Historial, Monitoreo)
│   └── app.js                      # Lógica de predicción en tiempo real, cronómetro y CRUD
├── src/
│   ├── generate_data.py            # Generador de datos sintéticos con perfiles de usuario
│   ├── train.py                    # Pipeline de entrenamiento y registro en MLflow
│   └── monitor.py                  # Evaluación de Data Drift con Evidently AI
├── tests/
│   └── test_api.py                 # Suite de pruebas unitarias y de integración (Pytest)
├── Dockerfile                      # Imagen ligera lista para despliegue en nube
├── docker-compose.yml              # Orquestación local (Web + FastAPI + MLflow + Airflow)
├── pyproject.toml                  # Configuración de Pytest
└── requirements.txt                # Dependencias del proyecto
```

## Ejecución Local

### Opción 1: Entorno Virtual Python (Desarrollo rápido)

~~~Bash
# 1. Clonar repositorio y activar entorno virtual
git clone https://github.com/Emmanuelme76/yarukoto-mlops
cd yarukoto-mlops
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Generar dataset base, entrenar modelos en MLflow y generar reporte inicial
python src/generate_data.py
python src/train.py
python src/monitor.py

# 4. Levantar la aplicación web + API
uvicorn api.main:app --reload
~~~

#### Accede a:

- Aplicación Web: `http://127.0.0.1:8000`

- API Docs (Swagger): `http://127.0.0.1:8000/docs`

- MLflow UI (en otra terminal):` mlflow ui --backend-store-uri sqlite:///mlflow.db (http://127.0.0.1:5000)`

 ### Opción 2: Stack Completo con Docker Compose (Web + MLflow + Airflow)

~~~shell
docker compose up --build
~~~

#### Servicios disponibles:

- Yarukoto Web + FastAPI: `http://localhost:8000`

- Apache Airflow UI: `http://localhost:8080` (Credenciales: `admin` / `admin`)

## Pruebas Automatizadas
Para validar los endpoints de predicción, el manejo de usuarios/subcategorías inéditas y la captura de Ground Truth:

~~~bash
pytest -v
~~~

## Contexto Académico

Proyecto desarrollado para la materia de Minería de Datos / MLOps — Centro Universitario de Ciencias Exactas e Ingeniería (CUCEI), Universidad de Guadalajara.


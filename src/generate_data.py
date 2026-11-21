import os
import numpy as np
import pandas as pd


def generate_synthetic_tasks(n_samples: int = 1500, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)

    # Perfiles de usuario con distintos ritmos y tasas base de cumplimiento
    user_profiles = {
        "alumno_1": {"speed_factor": 1.0, "discipline_bias": 0.2},
        "alumno_2": {"speed_factor": 1.25, "discipline_bias": -0.3},
        "profe": {"speed_factor": 0.85, "discipline_bias": 0.6},
        "invitado": {"speed_factor": 1.1, "discipline_bias": 0.0},
    }
    usuarios = list(user_profiles.keys())

    # Catálogo de categorías y subcategorías base con su tiempo base en minutos
    catalog = {
        "Escuela": {
            "Tarea / Ejercicios": 45,
            "Proyecto / Código": 120,
            "Estudio para examen": 90,
            "Lectura / Resumen": 35,
        },
        "Trabajo": {
            "Reunión": 40,
            "Desarrollo / Técnico": 110,
            "Documentación / Reporte": 60,
            "Correo / Admin": 20,
        },
        "Hogar": {
            "Limpieza": 50,
            "Compras / Mandados": 45,
            "Cocina": 40,
            "Mantenimiento": 75,
        },
        "Personal": {
            "Ejercicio": 55,
            "Trámites / Finanzas": 40,
            "Cita médica": 60,
            "Ocio / Lectura": 45,
        },
    }

    categorias = list(catalog.keys())
    records = []

    for _ in range(n_samples):
        user = np.random.choice(usuarios, p=[0.40, 0.30, 0.15, 0.15])
        profile = user_profiles[user]

        cat = np.random.choice(categorias, p=[0.35, 0.30, 0.20, 0.15])
        subcat = np.random.choice(list(catalog[cat].keys()))
        base_time = catalog[cat][subcat]

        prioridad = np.random.choice([1, 2, 3], p=[0.25, 0.45, 0.30])
        complejidad = np.random.choice([1, 2, 3, 4, 5], p=[0.15, 0.25, 0.30, 0.20, 0.10])
        dia_semana = np.random.randint(0, 7)  # 0=Lunes, 6=Domingo
        hora_creacion = np.random.randint(7, 24)
        dias_para_entrega = np.random.choice([0, 1, 2, 3, 5, 7, 14], p=[0.10, 0.20, 0.25, 0.20, 0.10, 0.10, 0.05])
        tareas_pendientes = np.random.poisson(lam=4)

        # Cálculo realista de tiempo_real_min ajustado al perfil del usuario
        factor_complejidad = 0.65 + (complejidad * 0.22)
        ruido_tiempo = np.random.normal(0, base_time * 0.15)
        tiempo_estimado_base = base_time * factor_complejidad * profile["speed_factor"]
        tiempo_real_min = max(10, int(round(tiempo_estimado_base + ruido_tiempo)))

        # Cálculo realista de probabilidad de completarse
        logit = 1.3 + profile["discipline_bias"]
        logit += 0.55 * (prioridad - 2)
        logit -= 0.35 * (complejidad - 3)
        logit -= 0.22 * max(0, tareas_pendientes - 4)
        logit += 0.15 * min(dias_para_entrega, 5)
        if hora_creacion >= 21:
            logit -= 0.65
        if cat in ["Hogar", "Personal"] and dia_semana >= 5:
            logit += 0.40

        prob_completar = 1 / (1 + np.exp(-logit))
        completada = int(np.random.rand() < prob_completar)

        records.append({
            "usuario": user,
            "categoria": cat,
            "subcategoria": subcat,
            "prioridad": prioridad,
            "complejidad": complejidad,
            "dia_semana": dia_semana,
            "hora_creacion": hora_creacion,
            "dias_para_entrega": dias_para_entrega,
            "tareas_pendientes": tareas_pendientes,
            "completada": completada,
            "tiempo_real_min": tiempo_real_min,
        })

    return pd.DataFrame(records)


if __name__ == "__main__":
    os.makedirs("data/raw", exist_ok=True)
    df = generate_synthetic_tasks(n_samples=1500)
    output_path = "data/raw/reference_tasks.csv"
    df.to_csv(output_path, index=False)

    print(f"Dataset v2 generado en {output_path} con {len(df)} registros.")
    print(f"Columnas: {list(df.columns)}")
    print(f"Tasa global de tareas completadas: {df['completada'].mean():.2%}")


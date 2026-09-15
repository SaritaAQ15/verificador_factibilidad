"""
Cálculo Independiente de Métricas y Función Objetivo
-----------------------------------------------------------------
Calcula de forma determinista y desacoplada las métricas de recorrido,
tiempos, distancias euclidianas, satisfacción acumulada y diagnóstico
de rendimiento algorítmico para la flota global.
"""

from typing import List, Dict, Set
from models import (
    ConfiguracionOperativa, CONFIG, MetricasRuta,
    ResultadoValidacion, DiagnosticoRendimiento
)
from loader import DatasetSitios


def calcular_metricas_ruta(
    van_id: str,
    secuencia_sitios: List[int],
    dataset: DatasetSitios,
    config: ConfiguracionOperativa = CONFIG
) -> MetricasRuta:
    """
    Calcula de forma exacta las métricas operacionales de una ruta asignada a una van.
    Añade automáticamente el origen (hotel) y retorno (hotel) al recorrido:
        Hotel (0) -> s_1 -> s_2 -> ... -> s_m -> Hotel (0)
    """
    metricas = MetricasRuta(
        van_id=van_id,
        secuencia_visitas=list(secuencia_sitios),
        num_sitios=len(secuencia_sitios),
        puntaje_acumulado=0,
        distancia_total_km=0.0,
        tiempo_traslado_horas=0.0,
        tiempo_estancia_horas=0.0,
        tiempo_total_horas=0.0,
        es_factible=True,
        errores=[]
    )

    if not secuencia_sitios:
        metricas.es_factible = False
        metricas.errores.append(f"La van {van_id} no tiene sitios asignados.")
        return metricas

    for sid in secuencia_sitios:
        if not dataset.existe_sitio(sid):
            metricas.es_factible = False
            metricas.errores.append(f"El sitio con ID {sid} no existe en el dataset.")

    if not metricas.es_factible:
        return metricas

    paradas_completas = [config.hotel_id] + secuencia_sitios + [config.hotel_id]

    distancia_acumulada = 0.0
    for i in range(len(paradas_completas) - 1):
        origen = paradas_completas[i]
        destino = paradas_completas[i + 1]
        distancia_acumulada += dataset.distancia(origen, destino)

    tiempo_traslado = distancia_acumulada / config.velocidad_km_h
    tiempo_estancia = len(secuencia_sitios) * config.duracion_visita_horas
    tiempo_total = tiempo_traslado + tiempo_estancia

    puntaje_total = sum(dataset.obtener_sitio(sid).puntaje for sid in secuencia_sitios)

    metricas.distancia_total_km = round(distancia_acumulada, 4)
    metricas.tiempo_traslado_horas = round(tiempo_traslado, 4)
    metricas.tiempo_estancia_horas = round(tiempo_estancia, 4)
    metricas.tiempo_total_horas = round(tiempo_total, 4)
    metricas.puntaje_acumulado = puntaje_total

    if tiempo_total > (config.jornada_maxima_horas + config.tolerancia_epsilon):
        metricas.es_factible = False
        metricas.errores.append(
            f"La van {van_id} excede la jornada de 8 horas (Tiempo calculado: {tiempo_total:.2f} h)."
        )

    return metricas


def calcular_metricas_globales(
    metricas_vans: Dict[str, MetricasRuta],
    dataset: DatasetSitios
) -> Dict[str, object]:
    """
    Agrega los KPIs operacionales de toda la flota turística.
    """
    total_sitios = sum(m.num_sitios for m in metricas_vans.values())
    satisfaccion_total = sum(m.puntaje_acumulado for m in metricas_vans.values())
    distancia_flota = round(sum(m.distancia_total_km for m in metricas_vans.values()), 4)
    tiempo_max_van = max((m.tiempo_total_horas for m in metricas_vans.values()), default=0.0)

    sitios_visitados: Set[int] = set()
    for m in metricas_vans.values():
        sitios_visitados.update(m.secuencia_visitas)

    todos_los_sitios = dataset.obtener_todos_los_ids(incluir_hotel=False)
    sitios_no_visitados = sorted(list(todos_los_sitios - sitios_visitados))

    return {
        "total_sitios_visitados": total_sitios,
        "satisfaccion_total_acumulada": satisfaccion_total,
        "distancia_total_flota_km": distancia_flota,
        "tiempo_maximo_van_horas": tiempo_max_van,
        "sitios_no_visitados": sitios_no_visitados
    }


def evaluar_diagnostico_rendimiento(
    total_sitios: int,
    satisfaccion_total: int,
    metricas_vans: Dict[str, MetricasRuta],
    dataset: DatasetSitios,
    config: ConfiguracionOperativa = CONFIG
) -> DiagnosticoRendimiento:
    """
    Evalúa la calidad algorítmica de la solución frente a los objetivos del problema (con estancia de 30 min):
    1. Maximizar cantidad de atractivos atendidos (Objetivo Primario, techo físico ~36-37 sitios).
    2. Maximizar satisfacción total acumulada de la flota (Objetivo Secundario / Desempate).
    3. Nivel de aprovechamiento de la jornada laboral de 8 horas.
    """
    total_catalogo = len(dataset)
    pct_cobertura = round((total_sitios / total_catalogo) * 100, 1)

    tiempos = [m.tiempo_total_horas for m in metricas_vans.values()]
    tiempo_max = max(tiempos) if tiempos else 0.0
    pct_uso_jornada_max = round((tiempo_max / config.jornada_maxima_horas) * 100, 1)
    
    tiempo_promedio = (sum(tiempos) / len(tiempos)) if tiempos else 0.0
    pct_promedio_flota = round((tiempo_promedio / config.jornada_maxima_horas) * 100, 1)

    observaciones: List[str] = []

    # Clasificación de calidad algorítmica calibrada para estancia de 30 min (0.5 h)
    if total_sitios >= 34:
        nivel = "EXCELENTE / COMPETITIVO"
        observaciones.append(
            f"Alta cobertura de red ({total_sitios}/{total_catalogo} sitios, {pct_cobertura}%). "
            f"La solución opera cerca del techo óptimo físico del sistema (~36 sitios)."
        )
    elif total_sitios >= 27:
        nivel = "ACEPTABLE / MEJORABLE"
        observaciones.append(
            f"Cobertura intermedia ({total_sitios}/{total_catalogo} sitios, {pct_cobertura}%). "
            f"Existe margen para incorporar más paradas o refinar el orden de traslados."
        )
    else:
        nivel = "SUBÓPTIMO / DEFICIENTE"
        observaciones.append(
            f"Baja cobertura de atractivos ({total_sitios}/{total_catalogo} sitios, {pct_cobertura}%). "
            f"El objetivo primario de la empresa es maximizar el número de visitas atendidas."
        )

    # Diagnóstico de utilización temporal (capacidad ociosa)
    if pct_promedio_flota < 70.0:
        observaciones.append(
            f"Capacidad ociosa elevada: la flota solo utiliza en promedio el {pct_promedio_flota}% "
            f"de su jornada laboral ({tiempo_promedio:.2f} h de 8.0 h). Se recomienda ampliar los itinerarios."
        )
    elif pct_uso_jornada_max >= 90.0:
        observaciones.append(
            f"Aprovechamiento temporal óptimo: al menos un vehículo utiliza el {pct_uso_jornada_max}% "
            f"de su jornada ({tiempo_max:.2f} h / 8.0 h)."
        )

    # Observación sobre satisfacción acumulada (criterio de desempate)
    if satisfaccion_total >= 2150:
        observaciones.append(
            f"Satisfacción global acumulada destacada: {satisfaccion_total} puntos recolectados."
        )
    else:
        observaciones.append(
            f"Satisfacción global acumulada: {satisfaccion_total} puntos. Recuerde que ante igual "
            f"número de sitios visitados, se prioriza la solución con mayor puntaje acumulado."
        )

    return DiagnosticoRendimiento(
        nivel_calidad=nivel,
        porcentaje_cobertura_sitios=pct_cobertura,
        porcentaje_uso_jornada_max=pct_uso_jornada_max,
        promedio_uso_jornada_flota=pct_promedio_flota,
        observaciones=observaciones
    )
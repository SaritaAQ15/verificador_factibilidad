"""
Generador de Reportes de Evaluación y Diagnóstico
------------------------------------------------------------
Transforma el objeto ResultadoValidacion en reportes legibles en consola
(con formato estructurado) y en diccionarios serializables a JSON para
evaluación automatizada o exportación.
"""

import json
from typing import Optional, Dict, Any
from models import ResultadoValidacion, MetricasRuta, CONFIG
from loader import DatasetSitios


def formatear_tiempo(horas: float) -> str:
    """Convierte horas decimales a formato legible de horas y minutos."""
    h = int(horas)
    m = int(round((horas - h) * 60))
    if m == 60:
        h += 1
        m = 0
    return f"{h}h {m:02d}m ({horas:.2f} h)"


def generar_reporte_consola(
    resultado: ResultadoValidacion,
    dataset: Optional[DatasetSitios] = None,
    titulo: str = "REPORTE DE EVALUACIÓN - FACTIBILIDAD Y RENDIMIENTO"
) -> str:
    """
    Genera un reporte en texto con formato visual y tablas para terminal.
    """
    ancho = 80
    linea_doble = "=" * ancho
    linea_simple = "-" * ancho

    lineas = []
    lineas.append(linea_doble)
    lineas.append(f"{titulo.center(ancho)}")
    lineas.append(linea_doble)

    # 1. ESTADO DE FACTIBILIDAD
    if resultado.es_factible:
        estado_badge = "[ FACTIBLE - SOLUCIÓN VÁLIDA ]"
    else:
        estado_badge = "[ NO FACTIBLE - SOLUCIÓN RECHAZADA ]"
    
    lineas.append(f"ESTADO GENERAL : {estado_badge}")
    lineas.append(linea_simple)

    # 2. ERRORES Y ADVERTENCIAS
    if resultado.errores_globales:
        lineas.append("ERRORES DETECTADOS (RESTRICCIONES VIOLADAS):")
        for idx, err in enumerate(resultado.errores_globales, start=1):
            lineas.append(f"  [{idx}] {err}")
        lineas.append(linea_simple)

    if resultado.advertencias:
        lineas.append("ADVERTENCIAS:")
        for idx, adv in enumerate(resultado.advertencias, start=1):
            lineas.append(f"  (*) {adv}")
        lineas.append(linea_simple)

    # 3. TABLA RESUMEN POR VAN
    if resultado.metricas_por_van:
        lineas.append("DESGLOSE OPERACIONAL POR VEHÍCULO:")
        encabezado = f"{'Van':<8} | {'Sitios':<8} | {'Distancia':<12} | {'T. Traslado':<12} | {'T. Total':<14} | {'Satisfacción':<12}"
        lineas.append(encabezado)
        lineas.append("-" * len(encabezado))

        for van_id, m in resultado.metricas_por_van.items():
            t_total_str = f"{m.tiempo_total_horas:.2f} h"
            fila = (
                f"{van_id:<8} | "
                f"{m.num_sitios:<8} | "
                f"{m.distancia_total_km:>8.2f} km | "
                f"{m.tiempo_traslado_horas:>8.2f} h | "
                f"{t_total_str:>10} | "
                f"{m.puntaje_acumulado:>8} pts"
            )
            lineas.append(fila)
        lineas.append(linea_simple)

    # 4. KPIS GLOBALES Y FUNCIÓN OBJETIVO
    lineas.append("MÉTRICAS GLOBALES DE LA FLOTA (KPIs):")
    lineas.append(f"  * Total Atractivos Visitados : {resultado.total_sitios_visitados} / 45")
    lineas.append(f"  * Satisfacción Total Acumulada: {resultado.satisfaccion_total_acumulada} puntos")
    lineas.append(f"  * Distancia Total Recorrida   : {resultado.distancia_total_flota_km:.2f} km")
    lineas.append(f"  * Jornada Máxima Empleada     : {formatear_tiempo(resultado.tiempo_maximo_van_horas)} de {CONFIG.jornada_maxima_horas:.0f}h max")
    
    total_no_visitados = len(resultado.sitios_no_visitados)
    lineas.append(f"  * Atractivos No Visitados    : {total_no_visitados} sitios")
    if total_no_visitados > 0:
        lineas.append(f"    IDs: {resultado.sitios_no_visitados}")
    
    # 5. DETALLE DE RUTAS
    if resultado.metricas_por_van:
        lineas.append(linea_simple)
        lineas.append("ITINERARIOS DETALLADOS POR VAN:")
        for van_id, m in resultado.metricas_por_van.items():
            if dataset:
                nombres = []
                for sid in m.secuencia_visitas:
                    if dataset.existe_sitio(sid):
                        nombres.append(f"{sid} ({dataset.obtener_sitio(sid).nombre})")
                    else:
                        nombres.append(f"{sid} (ID INVÁLIDO)")
                secuencia_str = "Hotel -> " + " -> ".join(nombres) + " -> Hotel"
            else:
                secuencia_str = "0 -> " + " -> ".join(map(str, m.secuencia_visitas)) + " -> 0"
            lineas.append(f"  * {van_id}: {secuencia_str}")

    lineas.append(linea_doble)
    return "\n".join(lineas)


def generar_reporte_dict(resultado: ResultadoValidacion) -> Dict[str, Any]:
    """Convierte el resultado en un diccionario estructurado serializable a JSON."""
    return {
        "es_factible": resultado.es_factible,
        "total_sitios_visitados": resultado.total_sitios_visitados,
        "satisfaccion_total_acumulada": resultado.satisfaccion_total_acumulada,
        "distancia_total_flota_km": resultado.distancia_total_flota_km,
        "tiempo_maximo_van_horas": resultado.tiempo_maximo_van_horas,
        "errores": resultado.errores_globales,
        "advertencias": resultado.advertencias,
        "sitios_no_visitados": resultado.sitios_no_visitados,
        "detalle_vans": {
            vid: {
                "secuencia": m.secuencia_visitas,
                "num_sitios": m.num_sitios,
                "distancia_km": m.distancia_total_km,
                "tiempo_traslado_horas": m.tiempo_traslado_horas,
                "tiempo_estancia_horas": m.tiempo_estancia_horas,
                "tiempo_total_horas": m.tiempo_total_horas,
                "satisfaccion": m.puntaje_acumulado,
                "es_factible": m.es_factible,
                "errores": m.errores
            }
            for vid, m in resultado.metricas_por_van.items()
        }
    }


def exportar_reporte_json(resultado: ResultadoValidacion, filepath: str, indent: int = 2) -> None:
    """Exporta el reporte a un archivo .json legible."""
    datos = generar_reporte_dict(resultado)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=indent, ensure_ascii=False)
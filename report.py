"""
Generador de Reportes de Evaluación y Diagnóstico
------------------------------------------------------------
Transforma el objeto ResultadoValidacion en reportes legibles en consola
(con tablas estructuradas y formato claro) y en diccionarios serializables
a JSON para evaluación automatizada o exportación.
"""

import json
from typing import Optional, Dict, Any, List
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
    Genera un reporte estructurado y de alta legibilidad en consola o notebooks.
    """
    ancho = 86
    lineas: List[str] = []

    # Encabezado principal
    lineas.append("╔" + "═" * (ancho - 2) + "╗")
    lineas.append(f"║{titulo.center(ancho - 2)}║")
    lineas.append("╚" + "═" * (ancho - 2) + "╝")

    # 1. Estado de factibilidad
    if resultado.es_factible:
        estado_badge = " ✔ FACTIBLE (SOLUCIÓN VÁLIDA) "
    else:
        estado_badge = " ✖ NO FACTIBLE (SOLUCIÓN RECHAZADA) "

    lineas.append(f"\n[ ESTADO GENERAL ]: {estado_badge}")
    lineas.append("─" * ancho)

    # 2. Errores detectados
    if resultado.errores_globales:
        lineas.append("✖ RESTRICCIONES VIOLADAS:")
        for idx, err in enumerate(resultado.errores_globales, start=1):
            lineas.append(f"  [{idx:02d}] {err}")
        lineas.append("─" * ancho)

    # 3. Advertencias
    if resultado.advertencias:
        lineas.append("⚠ ADVERTENCIAS / NORMALIZACIONES:")
        for idx, adv in enumerate(resultado.advertencias, start=1):
            lineas.append(f"  * {adv}")
        lineas.append("─" * ancho)

    # 4. Tabla de métricas por van
    if resultado.metricas_por_van:
        lineas.append("DESGLOSE OPERACIONAL POR VEHÍCULO:\n")
        lineas.append("┌──────────┬────────┬─────────────┬─────────────┬─────────────┬─────────────┬──────────────┐")
        lineas.append("│ Van      │ Sitios │ Distancia   │ T. Traslado │ T. Estancia │ T. Total    │ Satisfacción │")
        lineas.append("├──────────┼────────┼─────────────┼─────────────┼─────────────┼─────────────┼──────────────┤")

        tot_sitios = 0
        tot_dist = 0.0
        tot_t_traslado = 0.0
        tot_t_estancia = 0.0
        tot_pts = 0

        for van_id, m in resultado.metricas_por_van.items():
            tot_sitios += m.num_sitios
            tot_dist += m.distancia_total_km
            tot_t_traslado += m.tiempo_traslado_horas
            tot_t_estancia += m.tiempo_estancia_horas
            tot_pts += m.puntaje_acumulado

            lineas.append(
                f"│ {van_id:<8} │ "
                f"{m.num_sitios:>6} │ "
                f"{m.distancia_total_km:>9.2f} km │ "
                f"{m.tiempo_traslado_horas:>9.2f} h │ "
                f"{m.tiempo_estancia_horas:>9.2f} h │ "
                f"{m.tiempo_total_horas:>9.2f} h │ "
                f"{m.puntaje_acumulado:>10} pts │"
            )

        lineas.append("├──────────┼────────┼─────────────┼─────────────┼─────────────┼─────────────┼──────────────┤")
        max_t = resultado.tiempo_maximo_van_horas
        lineas.append(
            f"│ TOTAL    │ "
            f"{tot_sitios:>6} │ "
            f"{tot_dist:>9.2f} km │ "
            f"{tot_t_traslado:>9.2f} h │ "
            f"{tot_t_estancia:>9.2f} h │ "
            f"{max_t:>7.2f} h max │ "
            f"{tot_pts:>10} pts │"
        )
        lineas.append("└──────────┴────────┴─────────────┴─────────────┴─────────────┴─────────────┴──────────────┘")
        lineas.append("─" * ancho)

    # 5. Indicadores globales (KPIs)
    total_catalogo = len(dataset) if dataset else 45
    lineas.append("INDICADORES CLAVE DE RENDIMIENTO (KPIs):")
    lineas.append(f"  • Cobertura de Atractivos : {resultado.total_sitios_visitados} / {total_catalogo} sitios")
    lineas.append(f"  • Satisfacción Acumulada  : {resultado.satisfaccion_total_acumulada} puntos")
    lineas.append(f"  • Distancia Total Flota   : {resultado.distancia_total_flota_km:.2f} km")
    lineas.append(f"  • Cuello de Botella Flota : {formatear_tiempo(resultado.tiempo_maximo_van_horas)} (Límite: {CONFIG.jornada_maxima_horas:.0f}h)")

    no_vis = len(resultado.sitios_no_visitados)
    lineas.append(f"  • Atractivos Sin Visitar  : {no_vis} sitios")
    if 0 < no_vis <= 20:
        lineas.append(f"    IDs: {resultado.sitios_no_visitados}")
    elif no_vis > 20:
        lineas.append(f"    IDs (primeros 20): {resultado.sitios_no_visitados[:20]} ...")
    lineas.append("─" * ancho)

    # 6. Diagnóstico de calidad algorítmica
    if resultado.rendimiento:
        diag = resultado.rendimiento
        lineas.append("DIAGNÓSTICO ALGORÍTMICO:")
        lineas.append(f"  • Nivel de Calidad        : [ {diag.nivel_calidad} ]")
        lineas.append(f"  • Cobertura de Red        : {diag.porcentaje_cobertura_sitios:.1f}%")
        lineas.append(f"  • Uso de Jornada Máxima   : {diag.porcentaje_uso_jornada_max:.1f}%")
        lineas.append(f"  • Aprovechamiento Flota   : {diag.promedio_uso_jornada_flota:.1f}%")
        if diag.observaciones:
            lineas.append("  • Observaciones Técnicas  :")
            for obs in diag.observaciones:
                lineas.append(f"     ↳ {obs}")
        lineas.append("─" * ancho)

    # 7. Desglose detallado de itinerarios
    if resultado.metricas_por_van:
        lineas.append("🗺  ITINERARIOS DETALLADOS POR VEHÍCULO:")
        for van_id, m in resultado.metricas_por_van.items():
            lineas.append(f"\n   {van_id.upper()} ({m.num_sitios} paradas | {m.puntaje_acumulado} pts | {formatear_tiempo(m.tiempo_total_horas)}):")
            
            # Secuencia compacta de IDs
            secuencia_ids = [CONFIG.hotel_id] + m.secuencia_visitas + [CONFIG.hotel_id]
            lineas.append(f"     Ruta: " + " -> ".join(map(str, secuencia_ids)))
            
            # Detalle con nombres y puntajes individuales
            if dataset:
                lineas.append("     Paradas intermedias:")
                for idx, sid in enumerate(m.secuencia_visitas, start=1):
                    if dataset.existe_sitio(sid):
                        sitio = dataset.obtener_sitio(sid)
                        lineas.append(f"       {idx:02d}. [ID {sid:>2}] {sitio.nombre:<32} ({sitio.puntaje:>3} pts)")
                    else:
                        lineas.append(f"       {idx:02d}. [ID {sid:>2}] ID INVÁLIDO O INEXISTENTE")

    lineas.append("\n" + "═" * ancho)
    return "\n".join(lineas)


def generar_reporte_dict(resultado: ResultadoValidacion) -> Dict[str, Any]:
    """Convierte el resultado en un diccionario estructurado serializable a JSON."""
    reporte = {
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

    if resultado.rendimiento:
        reporte["diagnostico"] = {
            "nivel_calidad": resultado.rendimiento.nivel_calidad,
            "porcentaje_cobertura_sitios": resultado.rendimiento.porcentaje_cobertura_sitios,
            "porcentaje_uso_jornada_max": resultado.rendimiento.porcentaje_uso_jornada_max,
            "promedio_uso_jornada_flota": resultado.rendimiento.promedio_uso_jornada_flota,
            "observaciones": resultado.rendimiento.observaciones
        }

    return reporte


def exportar_reporte_json(resultado: ResultadoValidacion, filepath: str, indent: int = 2) -> None:
    """Exporta el reporte a un archivo .json legible."""
    datos = generar_reporte_dict(resultado)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=indent, ensure_ascii=False)
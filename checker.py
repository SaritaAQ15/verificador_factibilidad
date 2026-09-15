"""
Motor de Factibilidad y Parser de Soluciones
---------------------------------------------------------
Normaliza la entrada del estudiante y ejecuta el pipeline de validación
de restricciones duras para certificar la factibilidad de la solución,
agregando el diagnóstico de rendimiento algorítmico.
"""

import json
import re
from pathlib import Path
from typing import Union, Dict, List, Any, Tuple
from collections import Counter

from models import ConfiguracionOperativa, CONFIG, ResultadoValidacion, MetricasRuta
from loader import DatasetSitios
from metrics import calcular_metricas_ruta, calcular_metricas_globales, evaluar_diagnostico_rendimiento


def normalizar_entrada_solucion(
    entrada: Union[str, Path, Dict[str, Any], List[Any]],
    config: ConfiguracionOperativa = CONFIG
) -> Tuple[Dict[str, List[int]], List[str], List[str]]:
    """
    Parsea y normaliza la solución entregada por el estudiante.
    
    Acepta:
    1. Archivo .json (str o Path).
    2. Cadena con formato JSON (str).
    3. Diccionario con llaves de vans (dict) - insensible a mayúsculas/minúsculas.
    4. Lista de 3 listas con secuencias de sitios (list o tuple).
    
    Normalizaciones automáticas aplicadas:
    - Normalización de llaves (case-insensitive): 'Van 1', 'VAN_1', 'van1', '1' -> 'van_1'.
    - Conversión de IDs tipo string ('5') a enteros (5).
    - Remoción no penalizada del nodo Hotel (0) si se incluye al inicio o al final.
    """
    errores: List[str] = []
    advertencias: List[str] = []
    datos_crudos: Any = entrada

    # 1. Cargar desde archivo o string si aplica
    if isinstance(entrada, (str, Path)):
        p = Path(entrada)
        if p.exists() and p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    datos_crudos = json.load(f)
            except Exception as e:
                return {}, [f"Error de sintaxis al leer el archivo JSON: {e}"], []
        elif isinstance(entrada, str):
            try:
                datos_crudos = json.loads(entrada)
            except Exception as e:
                return {}, [f"La cadena proporcionada no es un formato JSON válido: {e}"], []

    rutas_intermedias: Dict[str, List[Any]] = {}

    # 2. Interpretar como lista o como diccionario
    if isinstance(datos_crudos, list):
        if len(datos_crudos) != config.num_vans_requeridas:
            errores.append(
                f"La solución debe contemplar exactamente {config.num_vans_requeridas} vans activas. "
                f"Se recibieron {len(datos_crudos)} elementos en la lista."
            )
            return {}, errores, advertencias
        for idx, sublista in enumerate(datos_crudos, start=1):
            if not isinstance(sublista, (list, tuple)):
                errores.append(f"El elemento de la van {idx} debe ser una lista o tupla de IDs de atractivos.")
            rutas_intermedias[f"van_{idx}"] = list(sublista) if isinstance(sublista, (list, tuple)) else []

    elif isinstance(datos_crudos, dict):
        if len(datos_crudos) != config.num_vans_requeridas:
            errores.append(
                f"La solución debe contemplar exactamente {config.num_vans_requeridas} vans activas. "
                f"Se recibieron {len(datos_crudos)} vans en el diccionario."
            )
            return {}, errores, advertencias

        # Normalización case-insensitive y soporte para formatos: "Van 1", "van_1", "VAN 1", "1"
        mapeo_vans: Dict[str, List[Any]] = {}
        llaves_asignadas = set()

        for clave_original, valor in datos_crudos.items():
            clave_str = str(clave_original).strip().lower()
            
            # Extraer número de van si existe (ej. 'van 1', 'van_1', '1', 'van1')
            coincidencia = re.search(r'\b([1-3])\b|van[_\s]*([1-3])', clave_str)
            if coincidencia:
                num_van = coincidencia.group(1) or coincidencia.group(2)
                clave_normalizada = f"van_{num_van}"
            else:
                clave_normalizada = f"van_{len(mapeo_vans) + 1}"

            if clave_normalizada in llaves_asignadas:
                errores.append(f"Identificador de vehículo ambiguo o duplicado para '{clave_original}'.")
            llaves_asignadas.add(clave_normalizada)

            if not isinstance(valor, (list, tuple)):
                errores.append(f"El valor para '{clave_original}' debe ser una lista de IDs.")
                mapeo_vans[clave_normalizada] = []
            else:
                mapeo_vans[clave_normalizada] = list(valor)

        # Ordenar canónicamente: van_1, van_2, van_3
        for idx in range(1, config.num_vans_requeridas + 1):
            vid = f"van_{idx}"
            rutas_intermedias[vid] = mapeo_vans.get(vid, [])
    else:
        errores.append("El formato de la solución debe ser un archivo JSON, un diccionario o una lista de listas.")
        return {}, errores, advertencias

    if errores:
        return {}, errores, advertencias

    # 3. Limpieza de IDs y tratamiento del nodo 0 (Hotel)
    rutas_normalizadas: Dict[str, List[int]] = {}

    for van_id, paradas in rutas_intermedias.items():
        secuencia_limpia: List[int] = []
        for elem in paradas:
            try:
                elem_int = int(elem)
                secuencia_limpia.append(elem_int)
            except (ValueError, TypeError):
                errores.append(f"El valor '{elem}' en {van_id} no es un identificador numérico válido.")

        # Detectar y remover nodo Hotel (0) en extremos sin penalización
        if secuencia_limpia and secuencia_limpia[0] == config.hotel_id:
            advertencias.append(f"En {van_id} se omitió el nodo inicial 0 (el hotel se conecta automáticamente).")
            secuencia_limpia.pop(0)

        if secuencia_limpia and secuencia_limpia[-1] == config.hotel_id:
            advertencias.append(f"En {van_id} se omitió el nodo final 0 (el retorno al hotel se conecta automáticamente).")
            secuencia_limpia.pop()

        rutas_normalizadas[van_id] = secuencia_limpia

    return rutas_normalizadas, errores, advertencias


def verificar_solucion(
    entrada_solucion: Union[str, Path, Dict[str, Any], List[Any]],
    dataset: DatasetSitios,
    config: ConfiguracionOperativa = CONFIG
) -> ResultadoValidacion:
    """
    Ejecuta el pipeline completo de validación de factibilidad, cálculo de métricas
    y diagnóstico de calidad algorítmica.
    """
    errores_globales: List[str] = []
    
    # Paso 1: Parser y Esquema
    rutas, errores_parser, advertencias = normalizar_entrada_solucion(entrada_solucion, config)
    if errores_parser:
        return ResultadoValidacion(
            es_factible=False,
            errores_globales=errores_parser,
            advertencias=advertencias
        )

    # Paso 2: Motor de Restricciones Duras
    
    # Regla 1 (ERR_FLOTA): Exactamente 3 vans activas con al menos un atractivo
    for van_id, parada_list in rutas.items():
        if len(parada_list) == 0:
            errores_globales.append(f"La solución debe contemplar exactamente 3 vans activas (la {van_id} no tiene sitios asignados).")

    # Regla 2 (ERR_ID_INVALIDO): Existencia en el dataset
    todos_los_ids_usados: List[int] = []
    for van_id, parada_list in rutas.items():
        for sid in parada_list:
            todos_los_ids_usados.append(sid)
            if not dataset.existe_sitio(sid):
                errores_globales.append(f"El sitio con ID {sid} no existe en el dataset.")

    # Regla 3 (ERR_REPETICION): Unicidad global (partición disjunta)
    conteo_visitas = Counter(todos_los_ids_usados)
    for sid, count in conteo_visitas.items():
        if count > 1 and dataset.existe_sitio(sid):
            errores_globales.append(
                f"El sitio con ID {sid} está duplicado (asignado a más de una van o repetido en la misma)."
            )

    # Paso 3: Función Objetivo y Métricas por Van
    metricas_vans: Dict[str, MetricasRuta] = {}
    for van_id, parada_list in rutas.items():
        m = calcular_metricas_ruta(van_id, parada_list, dataset, config)
        metricas_vans[van_id] = m
        if not m.es_factible:
            for err in m.errores:
                if err not in errores_globales and "no tiene sitios asignados" not in err:
                    errores_globales.append(err)

    # Veredicto de factibilidad física
    es_factible = (len(errores_globales) == 0) and all(m.es_factible for m in metricas_vans.values())

    # Métricas agregadas de la flota
    kpis_globales = calcular_metricas_globales(metricas_vans, dataset)

    # Diagnóstico de rendimiento algorítmico (desacoplado de la factibilidad)
    diagnostico = None
    if es_factible:
        diagnostico = evaluar_diagnostico_rendimiento(
            total_sitios=kpis_globales["total_sitios_visitados"],
            satisfaccion_total=kpis_globales["satisfaccion_total_acumulada"],
            metricas_vans=metricas_vans,
            dataset=dataset,
            config=config
        )

    return ResultadoValidacion(
        es_factible=es_factible,
        errores_globales=errores_globales,
        advertencias=advertencias,
        metricas_por_van=metricas_vans,
        total_sitios_visitados=kpis_globales["total_sitios_visitados"],
        satisfaccion_total_acumulada=kpis_globales["satisfaccion_total_acumulada"],
        distancia_total_flota_km=kpis_globales["distancia_total_flota_km"],
        tiempo_maximo_van_horas=kpis_globales["tiempo_maximo_van_horas"],
        sitios_no_visitados=kpis_globales["sitios_no_visitados"],
        rendimiento=diagnostico
    )
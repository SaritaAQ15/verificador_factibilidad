"""
Interfaz de Alto Nivel para Estudiantes
------------------------------------------------------
Punto de entrada diseñado para integrarse directamente en Google Colab,
Jupyter Notebooks o scripts de Python locales.

Uso básico en una celda de código:
    from validador import evaluar_itinerarios

    # salida_algoritmo = mi_algoritmo_de_optimizacion(...)
    evaluar_itinerarios(salida_algoritmo)
"""

from pathlib import Path
from typing import Union, Dict, List, Any, Optional

from models import ResultadoValidacion
from loader import cargar_dataset_sitios, DatasetSitios
from checker import verificar_solucion
from report import generar_reporte_consola, exportar_reporte_json

# Cache global en memoria para evitar re-leer el Excel en cada ejecución de celda
_DATASET_CACHE: Dict[str, DatasetSitios] = {}


def _obtener_dataset(ruta_dataset: Union[str, Path] = "sitios_turisticos.xlsx") -> DatasetSitios:
    """Carga y almacena en caché el dataset de atractivos para ejecuciones rápidas."""
    ruta_str = str(Path(ruta_dataset).resolve())
    if ruta_str not in _DATASET_CACHE:
        _DATASET_CACHE[ruta_str] = cargar_dataset_sitios(ruta_dataset)
    return _DATASET_CACHE[ruta_str]


def evaluar_itinerarios(
    solucion: Union[str, Path, Dict[str, Any], List[Any]],
    ruta_dataset: Union[str, Path] = "sitios_turisticos.xlsx",
    imprimir_reporte: bool = True,
    guardar_json: bool = False,
    ruta_salida_json: Optional[Union[str, Path]] = None
) -> ResultadoValidacion:
    """
    Evalúa la factibilidad física y el rendimiento algorítmico de la solución propuesta.

    Parámetros:
    -----------
    solucion:
        Estructura con las rutas planificadas (Diccionario, Lista de listas, o ruta a un archivo .json).
    ruta_dataset:
        Ruta al archivo Excel 'sitios_turisticos.xlsx' (por defecto busca en el directorio actual).
    imprimir_reporte:
        Si es True, imprime en consola/celda el reporte formateado con tablas y diagnósticos.
    guardar_json:
        Si es True, exporta el reporte técnico detallado en formato .json.
    ruta_salida_json:
        Ruta personalizada para el archivo JSON (si no se especifica, usa 'reporte_evaluacion.json').

    Retorna:
    --------
    ResultadoValidacion:
        Objeto con los atributos de evaluación: .es_factible, .total_sitios_visitados,
        .satisfaccion_total_acumulada, .metricas_por_van, etc.
    """
    # 1. Cargar dataset oficial (desde caché)
    try:
        dataset = _obtener_dataset(ruta_dataset)
    except Exception as e:
        print(f"[ERROR DEL VALIDADOR] No se pudo cargar el dataset oficial: {e}")
        return ResultadoValidacion(
            es_factible=False,
            errores_globales=[f"Error al cargar el archivo de datos: {e}"]
        )

    # 2. Ejecutar motor de factibilidad y métricas
    resultado = verificar_solucion(solucion, dataset)

    # 3. Presentar reporte visual
    if imprimir_reporte:
        print(generar_reporte_consola(resultado, dataset))

    # 4. Exportar JSON si fue solicitado
    if guardar_json:
        destino = ruta_salida_json or "reporte_evaluacion.json"
        exportar_reporte_json(resultado, str(destino))
        print(f"[*] Reporte exportado exitosamente en: {destino}")

    return resultado


def es_factible(
    solucion: Union[str, Path, Dict[str, Any], List[Any]],
    ruta_dataset: Union[str, Path] = "sitios_turisticos.xlsx"
) -> bool:
    """
    Función de utilidad rápida que retorna únicamente True o False.
    Ideal para validaciones lógicas dentro de bucles o algoritmos genéticos/metaheurísticas.
    """
    res = evaluar_itinerarios(solucion, ruta_dataset=ruta_dataset, imprimir_reporte=False)
    return res.es_factible
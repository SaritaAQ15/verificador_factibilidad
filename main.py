"""
main.py - Punto de Entrada CLI para Evaluación de Soluciones
------------------------------------------------------------
Permite validar una solución desde la línea de comandos:
    python main.py ruta_solucion.json [ruta_dataset.xlsx]
"""

import sys
from pathlib import Path
from loader import cargar_dataset_sitios
from checker import verificar_solucion
from report import generar_reporte_consola, exportar_reporte_json


def main():
    if len(sys.argv) < 2:
        print("Uso: python main.py <archivo_solucion.json> [sitios_turisticos.xlsx]")
        sys.exit(1)

    solucion_path = Path(sys.argv[1])
    dataset_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("sitios_turisticos.xlsx")

    if not dataset_path.exists():
        print(f"Error: No se encontró el dataset en '{dataset_path}'")
        sys.exit(1)

    if not solucion_path.exists():
        print(f"Error: No se encontró el archivo de solución en '{solucion_path}'")
        sys.exit(1)

    # 1. Cargar datos oficiales y verificar solución
    dataset = cargar_dataset_sitios(dataset_path)
    resultado = verificar_solucion(solucion_path, dataset)

    # 2. Imprimir reporte formateado en terminal
    print(generar_reporte_consola(resultado, dataset))

    # 3. Exportar reporte en JSON estructurado
    salida_json = solucion_path.with_suffix(".reporte.json")
    exportar_reporte_json(resultado, str(salida_json))
    print(f"\nReporte JSON guardado en: {salida_json}")


if __name__ == "__main__":
    main()
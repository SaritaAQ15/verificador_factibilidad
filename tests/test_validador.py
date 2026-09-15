"""
Pruebas Unitarias y Casos Límite
------------------------------------------------------------------
Verifica la robustez del motor de validación frente a:
1. Formatos de entrada y parser (JSON, diccionarios, listas, espacios).
2. Restricciones duras (flota, IDs inválidos, duplicados, tiempo de 8h).
3. Casos de borde / frontera numérica (nodo 0 en extremos y medios).
4. Calidad algorítmica y capacidad ociosa (30 min de estancia).
"""

import unittest
from pathlib import Path

import models
from loader import cargar_dataset_sitios
import checker
import metrics


class TestValidadorFactibilidad(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.dataset = cargar_dataset_sitios("sitios_turisticos.xlsx")

    # =============================================================
    # 1. PRUEBAS DE PARSER Y FORMATO
    # =============================================================

    def test_formato_diccionario_estandar(self):
        """Valida que un diccionario nativo con paradas válidas sea aceptado."""
        sol = {"van_1": [1, 2], "van_2": [3, 4], "van_3": [5, 8]}
        res = checker.verificar_solucion(sol, self.dataset)
        self.assertTrue(res.es_factible)
        self.assertEqual(res.total_sitios_visitados, 6)

    def test_formato_lista_de_listas(self):
        """Valida que una lista anidada con 3 sublistas sea aceptada."""
        sol = [[1, 2], [3, 4], [5, 8]]
        res = checker.verificar_solucion(sol, self.dataset)
        self.assertTrue(res.es_factible)
        self.assertEqual(res.total_sitios_visitados, 6)

    def test_formato_case_insensitive_y_espacios(self):
        """Valida tolerancia a mayúsculas, espacios y tuplas."""
        sol = {"  Van 1  ": [" 1 ", 2], "VAN 2": [3, "4"], "van_3": (5, 8)}
        res = checker.verificar_solucion(sol, self.dataset)
        self.assertTrue(res.es_factible)
        self.assertEqual(res.total_sitios_visitados, 6)

    def test_formato_invalido_tipo_incorrecto(self):
        """Valida que entradas no estructuradas (enteros o None) no quiebren el script."""
        res_int = checker.verificar_solucion(12345, self.dataset)
        self.assertFalse(res_int.es_factible)
        self.assertIn("El formato de la solución debe ser", res_int.errores_globales[0])

        res_none = checker.verificar_solucion(None, self.dataset)
        self.assertFalse(res_none.es_factible)

    # =============================================================
    # 2. PRUEBAS DE RESTRICCIONES DURAS (FACTIBILIDAD FÍSICA)
    # =============================================================

    def test_err_flota_cantidad_vans_distinta_de_tres(self):
        """Falla si se entregan 2 o 4 vans en lugar de 3."""
        # Caso 2 vans
        res_2 = checker.verificar_solucion([[1, 2], [3, 4]], self.dataset)
        self.assertFalse(res_2.es_factible)
        self.assertTrue(any("exactamente 3 vans" in err for err in res_2.errores_globales))

        # Caso 4 vans
        res_4 = checker.verificar_solucion([[1], [2], [3], [4]], self.dataset)
        self.assertFalse(res_4.es_factible)

    def test_err_flota_van_vacia(self):
        """Falla si alguna de las 3 vans no tiene paradas asignadas."""
        sol = {"van_1": [1, 2], "van_2": [], "van_3": [3, 4]}
        res = checker.verificar_solucion(sol, self.dataset)
        self.assertFalse(res.es_factible)
        self.assertTrue(any("no tiene sitios asignados" in err for err in res.errores_globales))

    def test_err_id_invalido_fuera_de_dataset(self):
        """Falla si un ID no existe en el catálogo de 45 sitios."""
        sol = {"van_1": [1, 99], "van_2": [3, 4], "van_3": [5, 8]}
        res = checker.verificar_solucion(sol, self.dataset)
        self.assertFalse(res.es_factible)
        self.assertTrue(any("ID 99 no existe" in err for err in res.errores_globales))

    def test_err_id_invalido_negativo_o_texto(self):
        """Falla ante IDs negativos o alfanuméricos."""
        sol = {"van_1": [1, -5], "van_2": [3, 4], "van_3": [5, "plaza"]}
        res = checker.verificar_solucion(sol, self.dataset)
        self.assertFalse(res.es_factible)
        self.assertTrue(len(res.errores_globales) > 0)

    def test_err_repeticion_sitio_duplicado_intra_van(self):
        """Falla si una misma van repite una parada."""
        sol = {"van_1": [1, 5, 1], "van_2": [3, 4], "van_3": [8, 9]}
        res = checker.verificar_solucion(sol, self.dataset)
        self.assertFalse(res.es_factible)
        self.assertTrue(any("está duplicado" in err for err in res.errores_globales))

    def test_err_repeticion_sitio_duplicado_inter_van(self):
        """Falla si dos vans distintas visitan el mismo sitio."""
        sol = {"van_1": [1, 5], "van_2": [5, 4], "van_3": [8, 9]}
        res = checker.verificar_solucion(sol, self.dataset)
        self.assertFalse(res.es_factible)
        self.assertTrue(any("está duplicado" in err for err in res.errores_globales))

    def test_err_tiempo_exceso_de_jornada(self):
        """Falla si una ruta supera las 8 horas laborales."""
        # 16 sitios en 1 van: 16 * 0.5h = 8.0h solo en visitas, más de 8h con traslados
        sol = {"van_1": list(range(1, 17)), "van_2": [17, 18], "van_3": [19, 20]}
        res = checker.verificar_solucion(sol, self.dataset)
        self.assertFalse(res.es_factible)
        self.assertTrue(any("excede la jornada de 8 horas" in err for err in res.errores_globales))

    # =============================================================
    # 3. PRUEBAS DE BORDES Y FRONTERA
    # =============================================================

    def test_nodo_cero_en_extremos_no_penalizado(self):
        """El hotel (0) al inicio y fin se remueve automáticamente sin penalización."""
        sol_cero = {"van_1": [0, 1, 2, 0], "van_2": [3, 4], "van_3": [5, 8]}
        res = checker.verificar_solucion(sol_cero, self.dataset)
        self.assertTrue(res.es_factible)
        self.assertEqual(res.metricas_por_van["van_1"].num_sitios, 2)
        self.assertTrue(len(res.advertencias) > 0)

    def test_nodo_cero_intermedio_es_invalido(self):
        """Un nodo 0 a mitad de recorrido debe ser rechazado."""
        sol = {"van_1": [1, 0, 2], "van_2": [3, 4], "van_3": [5, 8]}
        res = checker.verificar_solucion(sol, self.dataset)
        self.assertFalse(res.es_factible)
        self.assertTrue(any("ID 0 no existe" in err for err in res.errores_globales))

    # =============================================================
    # 4. PRUEBAS DE CALIDAD ALGORÍTMICA (DIAGNÓSTICO)
    # =============================================================

    def test_diagnostico_solucion_suboptima_ociosa(self):
        """Una solución válida con pocos sitios debe diagnosticarse como deficiente/ociosa."""
        sol = {"van_1": [1, 2], "van_2": [3, 4], "van_3": [5, 8]}
        res = checker.verificar_solucion(sol, self.dataset)
        self.assertTrue(res.es_factible)
        self.assertIsNotNone(res.rendimiento)
        self.assertEqual(res.rendimiento.nivel_calidad, "SUBÓPTIMO / DEFICIENTE")
        self.assertTrue(any("Capacidad ociosa elevada" in obs for obs in res.rendimiento.observaciones))


if __name__ == "__main__":
    unittest.main()
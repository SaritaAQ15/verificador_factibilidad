"""
models.py - Modelos de Dominio y Estructuras de Datos
---------------------------------------------------
Define las entidades inmutables y contratos de datos para la validación
del problema de ruteo de vans turísticas (Team Orienteering Problem).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Set, Optional


@dataclass(frozen=True)
class ConfiguracionOperativa:
    """Parámetros operacionales y constantes físicas del sistema."""
    velocidad_km_h: float = 45.0
    duracion_visita_min: float = 30.0           # 30 minutos de permanencia fija
    duracion_visita_horas: float = 30.0 / 60.0  # Exactamente 0.5 h
    jornada_maxima_horas: float = 8.0           # 8 horas laborales (8:00 a.m. a 4:00 p.m.)
    tolerancia_epsilon: float = 1e-6            # Margen contra error numérico IEEE 754
    num_vans_requeridas: int = 3                # Flota exacta de 3 vans
    hotel_id: int = 0
    hotel_nombre: str = "Hotel (Origen/Destino)"
    hotel_coordenadas: Tuple[float, float] = (0.0, 0.0)


CONFIG = ConfiguracionOperativa()


@dataclass(frozen=True)
class SitioTuristico:
    """Entidad inmutable que representa un nodo turístico o el punto base (hotel)."""
    id_sitio: int
    nombre: str
    x: float
    y: float
    puntaje: int
    es_hotel: bool = False

    @property
    def coordenadas(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass
class MetricasRuta:
    """Métricas operacionales calculadas de forma independiente para una van."""
    van_id: str
    secuencia_visitas: List[int]
    num_sitios: int = 0
    puntaje_acumulado: int = 0
    distancia_total_km: float = 0.0
    tiempo_traslado_horas: float = 0.0
    tiempo_estancia_horas: float = 0.0
    tiempo_total_horas: float = 0.0
    es_factible: bool = True
    errores: List[str] = field(default_factory=list)


@dataclass
class DiagnosticoRendimiento:
    """Evaluación de calidad algorítmica y eficiencia operacional (desacoplada de la factibilidad)."""
    nivel_calidad: str                          # EXCELENTE / ACEPTABLE / SUBÓPTIMO
    porcentaje_cobertura_sitios: float = 0.0    # % de atractivos visitados (sobre 45)
    porcentaje_uso_jornada_max: float = 0.0     # % de uso de la jornada máxima (sobre 8h)
    promedio_uso_jornada_flota: float = 0.0     # % promedio de tiempo usado por las vans
    observaciones: List[str] = field(default_factory=list)


@dataclass
class ResultadoValidacion:
    """Veredicto final integral de la solución propuesta por un estudiante."""
    es_factible: bool
    errores_globales: List[str] = field(default_factory=list)
    advertencias: List[str] = field(default_factory=list)
    metricas_por_van: Dict[str, MetricasRuta] = field(default_factory=dict)
    total_sitios_visitados: int = 0
    satisfaccion_total_acumulada: int = 0
    distancia_total_flota_km: float = 0.0
    tiempo_maximo_van_horas: float = 0.0
    sitios_no_visitados: List[int] = field(default_factory=list)
    rendimiento: Optional[DiagnosticoRendimiento] = None

    def __repr__(self) -> str:
        """Resumen conciso en una sola línea en lugar del volcado crudo."""
        estado = "FACTIBLE" if self.es_factible else "NO FACTIBLE"
        return (
            f"<ResultadoValidacion: [{estado}] | "
            f"Visitas: {self.total_sitios_visitados}/45 | "
            f"Puntaje: {self.satisfaccion_total_acumulada} pts>"
        )

    def _repr_pretty_(self, p, cycle) -> None:
        """Evita la impresión de texto residual al ejecutarse en Google Colab/Jupyter."""
        estado = "FACTIBLE" if self.es_factible else "NO FACTIBLE"
        p.text(f"✔ Resumen: [{estado}] {self.total_sitios_visitados}/45 sitios visitados | {self.satisfaccion_total_acumulada} pts")
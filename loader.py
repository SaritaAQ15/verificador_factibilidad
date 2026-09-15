"""
Módulo de Carga y Gestión del Dataset de Sitios Turísticos
---------------------------------------------------------------------
Responsable de la lectura, validación de integridad y precomputación de
distancias euclidianas a partir del archivo Excel de sitios turísticos.
"""

from pathlib import Path
from typing import Dict, Set, Tuple, Union
import math
import numpy as np
import pandas as pd

from models import SitioTuristico, ConfiguracionOperativa, CONFIG


class DatasetError(Exception):
    """Excepción base para fallas relacionadas con el dataset."""
    pass


class DatasetFileNotFoundError(DatasetError):
    """Lanzada cuando el archivo del dataset no existe en la ruta especificada."""
    pass


class DatasetSchemaError(DatasetError):
    """Lanzada cuando las columnas esperadas no coinciden con el archivo."""
    pass


class DatasetDataIntegrityError(DatasetError):
    """Lanzada cuando se detectan anomalías de contenido, tipos o rangos en los datos."""
    pass


class DatasetSitios:
    """
    Contenedor inmutable de la red de sitios turísticos y el hotel base.
    Provee métodos eficientes para consulta y cálculo de distancias/tiempos.
    """

    def __init__(self, sitios: Dict[int, SitioTuristico], config: ConfiguracionOperativa = CONFIG):
        self._config = config
        self._sitios: Dict[int, SitioTuristico] = sitios.copy()
        
        # Registrar el hotel explícitamente en ID 0
        if config.hotel_id not in self._sitios:
            self._sitios[config.hotel_id] = SitioTuristico(
                id_sitio=config.hotel_id,
                nombre=config.hotel_nombre,
                x=config.hotel_coordenadas[0],
                y=config.hotel_coordenadas[1],
                puntaje=0,
                es_hotel=True
            )
        
        # Precomputación de matriz de distancias euclidianas (NumPy)
        self._ids = sorted(list(self._sitios.keys()))
        self._id_to_idx = {site_id: idx for idx, site_id in enumerate(self._ids)}
        
        coords = np.array([[self._sitios[sid].x, self._sitios[sid].y] for sid in self._ids])
        diff = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
        self._dist_matrix = np.sqrt(np.sum(diff ** 2, axis=-1))

    def existe_sitio(self, id_sitio: int) -> bool:
        """Verifica si un ID de atractivo existe en el dataset (excluyendo el hotel)."""
        return id_sitio in self._sitios and not self._sitios[id_sitio].es_hotel

    def obtener_sitio(self, id_sitio: int) -> SitioTuristico:
        """Retorna la entidad SitioTuristico para un ID dado."""
        if id_sitio not in self._sitios:
            raise KeyError(f"El ID {id_sitio} no existe en el dataset.")
        return self._sitios[id_sitio]

    def distancia(self, id_a: int, id_b: int) -> float:
        """Calcula la distancia euclidiana exacta en kilómetros entre dos IDs."""
        if id_a not in self._id_to_idx or id_b not in self._id_to_idx:
            raise KeyError(f"Uno de los identificadores ({id_a}, {id_b}) no existe en el dataset.")
        idx_a = self._id_to_idx[id_a]
        idx_b = self._id_to_idx[id_b]
        return float(self._dist_matrix[idx_a, idx_b])

    def tiempo_traslado(self, id_a: int, id_b: int) -> float:
        """Calcula el tiempo de viaje en horas entre dos nodos a la velocidad constante."""
        dist = self.distancia(id_a, id_b)
        return dist / self._config.velocidad_km_h

    def obtener_todos_los_ids(self, incluir_hotel: bool = False) -> Set[int]:
        """Retorna el conjunto de IDs disponibles."""
        if incluir_hotel:
            return set(self._sitios.keys())
        return {sid for sid, s in self._sitios.items() if not s.es_hotel}

    def __len__(self) -> int:
        """Retorna el total de atractivos turísticos (excluyendo el hotel)."""
        return len(self.obtener_todos_los_ids(incluir_hotel=False))


def cargar_dataset_sitios(filepath: Union[str, Path], config: ConfiguracionOperativa = CONFIG) -> DatasetSitios:
    """
    Carga y valida rigurosamente el archivo .xlsx de sitios turísticos.
    """
    path = Path(filepath)
    if not path.exists() or not path.is_file():
        raise DatasetFileNotFoundError(f"No se encontró el archivo del dataset en: {path.resolve()}")

    try:
        df = pd.read_excel(path)
    except Exception as exc:
        raise DatasetError(f"Error al intentar leer el archivo Excel '{path.name}': {exc}") from exc

    columnas_esperadas = {"ID_Sitio", "Nombre_Sitio", "Coordenada_X", "Coordenada_Y", "Puntaje"}
    columnas_presentes = set(df.columns)
    if not columnas_esperadas.issubset(columnas_presentes):
        faltantes = columnas_esperadas - columnas_presentes
        raise DatasetSchemaError(f"El dataset no contiene las columnas requeridas. Faltan: {faltantes}")

    if df[list(columnas_esperadas)].isnull().any().any():
        nulos = df[list(columnas_esperadas)].isnull().sum().to_dict()
        raise DatasetDataIntegrityError(f"El dataset contiene valores nulos en columnas obligatorias: {nulos}")

    if df["ID_Sitio"].duplicated().any():
        duplicados = df[df["ID_Sitio"].duplicated()]["ID_Sitio"].tolist()
        raise DatasetDataIntegrityError(f"Existen identificadores ID_Sitio duplicados en el dataset: {duplicados}")

    sitios_dict: Dict[int, SitioTuristico] = {}
    for _, row in df.iterrows():
        try:
            id_sitio = int(row["ID_Sitio"])
        except (ValueError, TypeError):
            raise DatasetDataIntegrityError(f"El valor de ID_Sitio '{row['ID_Sitio']}' no es convertible a entero.")

        if id_sitio <= 0:
            raise DatasetDataIntegrityError(f"El ID_Sitio {id_sitio} debe ser mayor a 0 (0 reservado para el hotel).")

        try:
            x = float(row["Coordenada_X"])
            y = float(row["Coordenada_Y"])
        except (ValueError, TypeError):
            raise DatasetDataIntegrityError(f"Las coordenadas del sitio {id_sitio} deben ser numéricas.")

        try:
            puntaje = int(row["Puntaje"])
        except (ValueError, TypeError):
            raise DatasetDataIntegrityError(f"El puntaje del sitio {id_sitio} debe ser entero.")

        if not (0 <= puntaje <= 100):
            raise DatasetDataIntegrityError(f"El puntaje del sitio {id_sitio} ({puntaje}) está fuera del rango [0, 100].")

        nombre = str(row["Nombre_Sitio"]).strip()

        sitios_dict[id_sitio] = SitioTuristico(
            id_sitio=id_sitio,
            nombre=nombre,
            x=x,
            y=y,
            puntaje=puntaje,
            es_hotel=False
        )

    return DatasetSitios(sitios=sitios_dict, config=config)
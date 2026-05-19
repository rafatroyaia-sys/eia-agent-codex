"""
aemet_client -- CL-01
Cliente HTTP para la API OpenData de AEMET.

Encapsula autenticación por API key, retry con backoff exponencial y el patrón
de descarga en dos pasos de AEMET: petición al endpoint → URL de datos → JSON final.

No selecciona estación climática (CL-02).
No calcula Köppen ni Martonne (CL-03).
No genera climogramas (CL-04).
No escribe archivos.
No usa IA.

Uso:
    from eia_agent.core.aemet_client import AEMETClient

    # Desde variable de entorno (recomendado)
    client = AEMETClient.from_env()
    normales = client.get_normales_climatologicas("C447A")

    # Con API key explícita (solo para tests)
    client = AEMETClient("mi_api_key", base_url="http://localhost:8080")
    normales = client.get_normales_climatologicas("B228")
"""
from __future__ import annotations

import os
import time

import requests


# ---------------------------------------------------------------------------
# Excepciones
# ---------------------------------------------------------------------------

class AEMETError(Exception):
    """Excepción base para todos los errores del cliente AEMET."""


class AEMETConfigError(AEMETError):
    """Falta de configuración: API key ausente o vacía antes de hacer la petición."""


class AEMETAuthError(AEMETError):
    """La API key fue rechazada por AEMET (HTTP 401 o 403)."""


class AEMETNotFoundError(AEMETError):
    """El recurso solicitado no existe en AEMET (HTTP 404)."""


class AEMETTimeoutError(AEMETError):
    """La petición superó el timeout configurado."""


class AEMETRateLimitError(AEMETError):
    """El rate limit de AEMET se agotó tras todos los reintentos (HTTP 429)."""


class AEMETServiceError(AEMETError):
    """Error del servicio AEMET (HTTP 5xx) agotado tras todos los reintentos."""


class AEMETResponseError(AEMETError):
    """La respuesta de AEMET no tiene el formato o estructura esperados."""


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL: str = "https://opendata.aemet.es/opendata"


# ---------------------------------------------------------------------------
# AEMETClient
# ---------------------------------------------------------------------------

class AEMETClient:
    """Cliente para la API OpenData de AEMET.

    El patrón estándar de AEMET OpenData usa dos pasos:
    1. GET al endpoint → respuesta con campo ``"datos"`` (URL temporal)
    2. GET a esa URL → JSON final con los datos climatológicos

    Este cliente gestiona ambos pasos de forma transparente.
    El retry aplica solo al primer paso (endpoint de AEMET).
    """

    def __init__(
        self,
        api_key: str,
        timeout: int = 10,
        max_retries: int = 3,
        base_url: str | None = None,
    ) -> None:
        """
        Args:
            api_key:     Clave de API AEMET. No puede estar vacía.
            timeout:     Segundos de espera máximo por petición (default: 10).
            max_retries: Número total de intentos en errores transitorios
                         (default: 3; incluye el primer intento).
            base_url:    URL base de la API AEMET. None usa la URL de producción.
                         Útil para pruebas contra un servidor local.
        """
        if not api_key or not api_key.strip():
            raise AEMETConfigError(
                "api_key no puede estar vacía. "
                "Use AEMETClient.from_env() o pase la clave explícitamente."
            )
        self._api_key: str = api_key.strip()
        self._timeout: int = timeout
        self._max_retries: int = max_retries
        self._base_url: str = (base_url or _DEFAULT_BASE_URL).rstrip("/")

    @classmethod
    def from_env(cls) -> "AEMETClient":
        """Crea un AEMETClient leyendo AEMET_API_KEY de las variables de entorno.

        Raises:
            AEMETConfigError: si AEMET_API_KEY no está configurada o está vacía.
        """
        api_key = os.environ.get("AEMET_API_KEY", "").strip()
        if not api_key:
            raise AEMETConfigError(
                "Variable de entorno AEMET_API_KEY no encontrada o vacía. "
                "Configúrela en el archivo .env del proyecto."
            )
        return cls(api_key)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def get_normales_climatologicas(self, id_estacion: str) -> object:
        """Descarga las normales climatológicas 1981-2010 de la estación indicada.

        No selecciona estación. No calcula Köppen. No genera archivos.

        Patrón AEMET (dos pasos):
        1. GET /api/valores/climatologicos/normales/estacion/{idema}
           → {"datos": "https://...", "estado": 200, ...}
        2. GET <datos_url> → lista de normales climatológicas mensuales

        Args:
            id_estacion: Indicativo climatológico AEMET (ej. ``"C447A"``, ``"B228"``).

        Returns:
            Lista o dict con las normales climatológicas en formato AEMET.

        Raises:
            ValueError:          si ``id_estacion`` está vacío.
            AEMETAuthError:      si la API key es rechazada (HTTP 401/403).
            AEMETNotFoundError:  si la estación no existe (HTTP 404).
            AEMETTimeoutError:   si la petición supera el timeout.
            AEMETRateLimitError: si se supera el rate limit tras reintentos.
            AEMETServiceError:   si AEMET devuelve 5xx tras reintentos.
            AEMETResponseError:  si la respuesta no tiene el formato esperado.
        """
        if not id_estacion or not str(id_estacion).strip():
            raise ValueError("id_estacion no puede estar vacío")

        id_clean = str(id_estacion).strip()
        url = (
            f"{self._base_url}"
            f"/api/valores/climatologicos/normales/estacion/{id_clean}"
        )
        headers = {"api_key": self._api_key}
        metadata = self._request_json(url, headers=headers)

        # Patrón estándar AEMET: la respuesta contiene "datos" con la URL de descarga
        if isinstance(metadata, dict) and "datos" in metadata:
            return self._download_json_from_datos_url(metadata["datos"])

        # Fallback defensivo: si la respuesta ya es la lista de datos
        if isinstance(metadata, list):
            return metadata

        keys = list(metadata.keys()) if isinstance(metadata, dict) else type(metadata).__name__
        raise AEMETResponseError(
            f"Respuesta de AEMET sin campo 'datos' ni datos directos reconocibles. "
            f"Estructura recibida: {keys}"
        )

    # ------------------------------------------------------------------
    # Métodos internos
    # ------------------------------------------------------------------

    def _request_json(self, url: str, headers: dict | None = None) -> dict:
        """Petición GET con retry y gestión completa de errores HTTP.

        Reintenta automáticamente en HTTP 429 (rate limit) y 5xx (errores del servidor).
        No reintenta en 401, 403, 404, timeout ni errores de red.

        Args:
            url:     URL completa a consultar.
            headers: Cabeceras HTTP adicionales (p.ej. ``{"api_key": "..."}``).

        Returns:
            El JSON de la respuesta parseado.

        Raises:
            AEMETAuthError, AEMETNotFoundError, AEMETTimeoutError,
            AEMETRateLimitError, AEMETServiceError, AEMETResponseError.
        """
        last_status: int | None = None

        for attempt in range(self._max_retries):
            try:
                response = requests.get(
                    url,
                    headers=headers or {},
                    timeout=self._timeout,
                )
            except requests.Timeout as exc:
                raise AEMETTimeoutError(
                    f"Timeout ({self._timeout}s) esperando respuesta de AEMET: {url}"
                ) from exc
            except requests.RequestException as exc:
                raise AEMETServiceError(
                    f"Error de red en petición AEMET ({url}): {exc}"
                ) from exc

            last_status = response.status_code

            if response.status_code in {401, 403}:
                raise AEMETAuthError(
                    f"Autenticación rechazada por AEMET (HTTP {response.status_code}). "
                    "Verifique AEMET_API_KEY en el archivo .env."
                )

            if response.status_code == 404:
                raise AEMETNotFoundError(
                    f"Recurso no encontrado en AEMET (HTTP 404): {url}"
                )

            if response.status_code == 429:
                if attempt < self._max_retries - 1:
                    self._sleep_before_retry(attempt)
                    continue
                raise AEMETRateLimitError(
                    f"Rate limit de AEMET agotado tras {self._max_retries} intentos."
                )

            if response.status_code >= 500:
                if attempt < self._max_retries - 1:
                    self._sleep_before_retry(attempt)
                    continue
                raise AEMETServiceError(
                    f"Servicio AEMET no disponible (HTTP {response.status_code}) "
                    f"tras {self._max_retries} intentos."
                )

            if response.status_code != 200:
                raise AEMETResponseError(
                    f"Respuesta inesperada de AEMET (HTTP {response.status_code}): {url}"
                )

            try:
                return response.json()
            except ValueError as exc:
                raise AEMETResponseError(
                    f"JSON inválido en respuesta de AEMET ({url}): {exc}"
                ) from exc

        # Inalcanzable en flujo normal (el bucle siempre raise o return antes)
        raise AEMETServiceError(  # pragma: no cover
            f"Sin respuesta válida de AEMET tras {self._max_retries} intentos. "
            f"Último status HTTP: {last_status}"
        )

    def _download_json_from_datos_url(self, datos_url: str) -> object:
        """Descarga la URL de datos que AEMET devuelve en el campo ``"datos"``.

        Esta URL no requiere autenticación y puede apuntar a un host diferente
        al de la API principal de AEMET.

        Args:
            datos_url: URL completa devuelta por AEMET en el campo ``"datos"``.

        Returns:
            El JSON descargado (normalmente una lista de dicts con las normales).

        Raises:
            AEMETTimeoutError:  si la descarga supera el timeout.
            AEMETServiceError:  si hay error de red.
            AEMETResponseError: si el status no es 200 o el JSON es inválido.
        """
        try:
            response = requests.get(datos_url, timeout=self._timeout)
        except requests.Timeout as exc:
            raise AEMETTimeoutError(
                f"Timeout descargando datos AEMET de {datos_url}"
            ) from exc
        except requests.RequestException as exc:
            raise AEMETServiceError(
                f"Error de red descargando datos AEMET: {exc}"
            ) from exc

        if response.status_code != 200:
            raise AEMETResponseError(
                f"Error HTTP al descargar datos AEMET "
                f"(HTTP {response.status_code}): {datos_url}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise AEMETResponseError(
                f"JSON inválido en datos AEMET descargados de {datos_url}: {exc}"
            ) from exc

    def _sleep_before_retry(self, attempt: int) -> None:
        """Backoff exponencial antes de reintentar: 1s, 2s, 4s, 8s...

        Para deshabilitar la espera en tests, mockear este método:

            with unittest.mock.patch.object(client, '_sleep_before_retry'):
                result = client.get_normales_climatologicas("C447A")
        """
        time.sleep(2 ** attempt)

"""
tests/test_aemet_client.py -- CL-01
Tests para AEMETClient.

Todas las llamadas HTTP están mockeadas via unittest.mock.patch.
No se hacen llamadas reales a AEMET excepto en TestAEMETIntegration,
que se salta si AEMET_API_KEY no está en el entorno.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import requests
    from eia_agent.core.aemet_client import (
        AEMETClient,
        AEMETError,
        AEMETConfigError,
        AEMETAuthError,
        AEMETNotFoundError,
        AEMETTimeoutError,
        AEMETRateLimitError,
        AEMETServiceError,
        AEMETResponseError,
    )
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, json_data=None, raise_json=None):
    """Crea un mock de requests.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    if raise_json is not None:
        mock.json.side_effect = raise_json
    else:
        mock.json.return_value = json_data
    return mock


def _make_client(**kwargs):
    """Crea un AEMETClient de test con clave ficticia y base_url local."""
    return AEMETClient(
        api_key=kwargs.pop("api_key", "test_api_key_12345"),
        base_url=kwargs.pop("base_url", "http://aemet.test"),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# TestAEMETExceptions
# ---------------------------------------------------------------------------

@unittest.skipUnless(_REQUESTS_OK, "requests no disponible")
class TestAEMETExceptions(unittest.TestCase):
    def test_aemet_config_error_is_aemet_error(self):
        self.assertTrue(issubclass(AEMETConfigError, AEMETError))

    def test_aemet_auth_error_is_aemet_error(self):
        self.assertTrue(issubclass(AEMETAuthError, AEMETError))

    def test_aemet_not_found_error_is_aemet_error(self):
        self.assertTrue(issubclass(AEMETNotFoundError, AEMETError))

    def test_aemet_timeout_error_is_aemet_error(self):
        self.assertTrue(issubclass(AEMETTimeoutError, AEMETError))

    def test_aemet_rate_limit_error_is_aemet_error(self):
        self.assertTrue(issubclass(AEMETRateLimitError, AEMETError))

    def test_aemet_service_error_is_aemet_error(self):
        self.assertTrue(issubclass(AEMETServiceError, AEMETError))

    def test_aemet_response_error_is_aemet_error(self):
        self.assertTrue(issubclass(AEMETResponseError, AEMETError))

    def test_aemet_error_is_exception(self):
        self.assertTrue(issubclass(AEMETError, Exception))

    def test_exceptions_carry_message(self):
        for cls in [
            AEMETConfigError, AEMETAuthError, AEMETNotFoundError,
            AEMETTimeoutError, AEMETRateLimitError, AEMETServiceError,
            AEMETResponseError,
        ]:
            exc = cls("mensaje de prueba")
            self.assertEqual(str(exc), "mensaje de prueba", f"{cls.__name__} no preserva mensaje")

    def test_all_catchable_as_aemet_error(self):
        exceptions = [
            AEMETConfigError("c"), AEMETAuthError("a"), AEMETNotFoundError("n"),
            AEMETTimeoutError("t"), AEMETRateLimitError("r"),
            AEMETServiceError("s"), AEMETResponseError("r"),
        ]
        for exc in exceptions:
            try:
                raise exc
            except AEMETError:
                pass
            else:
                self.fail(f"{type(exc).__name__} no capturado como AEMETError")


# ---------------------------------------------------------------------------
# TestAEMETClientInit
# ---------------------------------------------------------------------------

@unittest.skipUnless(_REQUESTS_OK, "requests no disponible")
class TestAEMETClientInit(unittest.TestCase):
    def test_valid_api_key_accepted(self):
        client = AEMETClient("valid_key_123")
        self.assertIsInstance(client, AEMETClient)

    def test_empty_api_key_raises_config_error(self):
        with self.assertRaises(AEMETConfigError):
            AEMETClient("")

    def test_whitespace_api_key_raises_config_error(self):
        with self.assertRaises(AEMETConfigError):
            AEMETClient("   ")

    def test_none_api_key_raises_config_error(self):
        with self.assertRaises(AEMETConfigError):
            AEMETClient(None)

    def test_api_key_is_stripped(self):
        client = AEMETClient("  my_key  ")
        self.assertEqual(client._api_key, "my_key")

    def test_default_timeout_is_10(self):
        client = AEMETClient("key")
        self.assertEqual(client._timeout, 10)

    def test_custom_timeout_stored(self):
        client = AEMETClient("key", timeout=30)
        self.assertEqual(client._timeout, 30)

    def test_default_max_retries_is_3(self):
        client = AEMETClient("key")
        self.assertEqual(client._max_retries, 3)

    def test_custom_max_retries_stored(self):
        client = AEMETClient("key", max_retries=5)
        self.assertEqual(client._max_retries, 5)

    def test_default_base_url_is_aemet(self):
        client = AEMETClient("key")
        self.assertEqual(client._base_url, "https://opendata.aemet.es/opendata")

    def test_custom_base_url_stored(self):
        client = AEMETClient("key", base_url="http://localhost:9000")
        self.assertEqual(client._base_url, "http://localhost:9000")

    def test_base_url_trailing_slash_stripped(self):
        client = AEMETClient("key", base_url="http://example.com/api/")
        self.assertEqual(client._base_url, "http://example.com/api")

    def test_none_base_url_uses_default(self):
        client = AEMETClient("key", base_url=None)
        self.assertIn("aemet.es", client._base_url)


# ---------------------------------------------------------------------------
# TestAEMETClientFromEnv
# ---------------------------------------------------------------------------

@unittest.skipUnless(_REQUESTS_OK, "requests no disponible")
class TestAEMETClientFromEnv(unittest.TestCase):
    def test_from_env_with_key_present(self):
        with patch.dict(os.environ, {"AEMET_API_KEY": "real_api_key"}, clear=False):
            client = AEMETClient.from_env()
            self.assertIsInstance(client, AEMETClient)

    def test_from_env_key_stored_correctly(self):
        with patch.dict(os.environ, {"AEMET_API_KEY": "my_key_123"}, clear=False):
            client = AEMETClient.from_env()
            self.assertEqual(client._api_key, "my_key_123")

    def test_from_env_without_key_raises_config_error(self):
        env = {k: v for k, v in os.environ.items() if k != "AEMET_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(AEMETConfigError) as ctx:
                AEMETClient.from_env()
            self.assertIn("AEMET_API_KEY", str(ctx.exception))

    def test_from_env_with_empty_key_raises_config_error(self):
        with patch.dict(os.environ, {"AEMET_API_KEY": ""}, clear=False):
            with self.assertRaises(AEMETConfigError):
                AEMETClient.from_env()

    def test_from_env_with_whitespace_key_raises_config_error(self):
        with patch.dict(os.environ, {"AEMET_API_KEY": "   "}, clear=False):
            with self.assertRaises(AEMETConfigError):
                AEMETClient.from_env()


# ---------------------------------------------------------------------------
# TestSleepBeforeRetry
# ---------------------------------------------------------------------------

@unittest.skipUnless(_REQUESTS_OK, "requests no disponible")
class TestSleepBeforeRetry(unittest.TestCase):
    def setUp(self):
        self.client = _make_client()

    def test_attempt_0_sleeps_1_second(self):
        with patch("eia_agent.core.aemet_client.time.sleep") as mock_sleep:
            self.client._sleep_before_retry(0)
        mock_sleep.assert_called_once_with(1)

    def test_attempt_1_sleeps_2_seconds(self):
        with patch("eia_agent.core.aemet_client.time.sleep") as mock_sleep:
            self.client._sleep_before_retry(1)
        mock_sleep.assert_called_once_with(2)

    def test_attempt_2_sleeps_4_seconds(self):
        with patch("eia_agent.core.aemet_client.time.sleep") as mock_sleep:
            self.client._sleep_before_retry(2)
        mock_sleep.assert_called_once_with(4)


# ---------------------------------------------------------------------------
# TestRequestJson
# ---------------------------------------------------------------------------

@unittest.skipUnless(_REQUESTS_OK, "requests no disponible")
class TestRequestJson(unittest.TestCase):
    def setUp(self):
        self.client = _make_client()

    def _patch_get(self, *responses):
        return patch(
            "eia_agent.core.aemet_client.requests.get",
            side_effect=list(responses),
        )

    def test_200_returns_json_dict(self):
        data = {"estado": 200, "datos": "http://datos.test/abc"}
        with self._patch_get(_mock_response(200, data)):
            result = self.client._request_json("http://aemet.test/api/test")
        self.assertEqual(result, data)

    def test_401_raises_auth_error(self):
        with self._patch_get(_mock_response(401)):
            with self.assertRaises(AEMETAuthError):
                self.client._request_json("http://aemet.test/api/test")

    def test_403_raises_auth_error(self):
        with self._patch_get(_mock_response(403)):
            with self.assertRaises(AEMETAuthError):
                self.client._request_json("http://aemet.test/api/test")

    def test_404_raises_not_found_error(self):
        with self._patch_get(_mock_response(404)):
            with self.assertRaises(AEMETNotFoundError):
                self.client._request_json("http://aemet.test/api/test")

    def test_timeout_raises_aemet_timeout_error(self):
        with patch(
            "eia_agent.core.aemet_client.requests.get",
            side_effect=requests.Timeout("timeout"),
        ):
            with self.assertRaises(AEMETTimeoutError):
                self.client._request_json("http://aemet.test/api/test")

    def test_request_exception_raises_service_error(self):
        with patch(
            "eia_agent.core.aemet_client.requests.get",
            side_effect=requests.RequestException("network error"),
        ):
            with self.assertRaises(AEMETServiceError):
                self.client._request_json("http://aemet.test/api/test")

    def test_invalid_json_raises_response_error(self):
        with self._patch_get(_mock_response(200, raise_json=ValueError("bad json"))):
            with self.assertRaises(AEMETResponseError):
                self.client._request_json("http://aemet.test/api/test")

    def test_400_raises_response_error(self):
        client = _make_client(max_retries=1)
        with patch.object(client, "_sleep_before_retry"):
            with self._patch_get(_mock_response(400)):
                with self.assertRaises(AEMETResponseError):
                    client._request_json("http://aemet.test/api/test")

    def test_302_raises_response_error(self):
        client = _make_client(max_retries=1)
        with patch.object(client, "_sleep_before_retry"):
            with self._patch_get(_mock_response(302)):
                with self.assertRaises(AEMETResponseError):
                    client._request_json("http://aemet.test/api/test")

    def test_429_with_max_retries_1_raises_rate_limit(self):
        client = _make_client(max_retries=1)
        with patch.object(client, "_sleep_before_retry"):
            with patch(
                "eia_agent.core.aemet_client.requests.get",
                return_value=_mock_response(429),
            ):
                with self.assertRaises(AEMETRateLimitError):
                    client._request_json("http://aemet.test/api/test")

    def test_503_with_max_retries_1_raises_service_error(self):
        client = _make_client(max_retries=1)
        with patch.object(client, "_sleep_before_retry"):
            with patch(
                "eia_agent.core.aemet_client.requests.get",
                return_value=_mock_response(503),
            ):
                with self.assertRaises(AEMETServiceError):
                    client._request_json("http://aemet.test/api/test")

    def test_500_with_max_retries_1_raises_service_error(self):
        client = _make_client(max_retries=1)
        with patch.object(client, "_sleep_before_retry"):
            with patch(
                "eia_agent.core.aemet_client.requests.get",
                return_value=_mock_response(500),
            ):
                with self.assertRaises(AEMETServiceError):
                    client._request_json("http://aemet.test/api/test")

    def test_headers_passed_to_requests(self):
        data = {"estado": 200, "datos": "url"}
        with patch(
            "eia_agent.core.aemet_client.requests.get",
            return_value=_mock_response(200, data),
        ) as mock_get:
            self.client._request_json(
                "http://aemet.test/api/test",
                headers={"api_key": "my_key"},
            )
        self.assertEqual(mock_get.call_args[1]["headers"], {"api_key": "my_key"})

    def test_timeout_value_passed_to_requests(self):
        client = _make_client(timeout=25)
        data = {"estado": 200}
        with patch(
            "eia_agent.core.aemet_client.requests.get",
            return_value=_mock_response(200, data),
        ) as mock_get:
            client._request_json("http://aemet.test/api/test")
        self.assertEqual(mock_get.call_args[1]["timeout"], 25)

    def test_none_headers_defaults_to_empty_dict(self):
        data = {"estado": 200}
        with patch(
            "eia_agent.core.aemet_client.requests.get",
            return_value=_mock_response(200, data),
        ) as mock_get:
            self.client._request_json("http://aemet.test/api/test", headers=None)
        self.assertEqual(mock_get.call_args[1]["headers"], {})


# ---------------------------------------------------------------------------
# TestRetryBehavior
# ---------------------------------------------------------------------------

@unittest.skipUnless(_REQUESTS_OK, "requests no disponible")
class TestRetryBehavior(unittest.TestCase):
    def setUp(self):
        self.client = _make_client(max_retries=3)

    def test_two_503_then_200_returns_data(self):
        data = {"datos": "http://datos.url"}
        responses = [_mock_response(503), _mock_response(503), _mock_response(200, data)]
        with patch("eia_agent.core.aemet_client.requests.get", side_effect=responses):
            with patch.object(self.client, "_sleep_before_retry"):
                result = self.client._request_json("http://aemet.test/api/test")
        self.assertEqual(result, data)

    def test_two_429_then_200_returns_data(self):
        data = {"datos": "http://datos.url"}
        responses = [_mock_response(429), _mock_response(429), _mock_response(200, data)]
        with patch("eia_agent.core.aemet_client.requests.get", side_effect=responses):
            with patch.object(self.client, "_sleep_before_retry"):
                result = self.client._request_json("http://aemet.test/api/test")
        self.assertEqual(result, data)

    def test_two_503_then_200_makes_three_requests(self):
        data = {"datos": "http://datos.url"}
        responses = [_mock_response(503), _mock_response(503), _mock_response(200, data)]
        with patch(
            "eia_agent.core.aemet_client.requests.get", side_effect=responses
        ) as mock_get:
            with patch.object(self.client, "_sleep_before_retry"):
                self.client._request_json("http://aemet.test/api/test")
        self.assertEqual(mock_get.call_count, 3)

    def test_two_503_then_200_sleeps_twice(self):
        data = {"datos": "http://datos.url"}
        responses = [_mock_response(503), _mock_response(503), _mock_response(200, data)]
        with patch("eia_agent.core.aemet_client.requests.get", side_effect=responses):
            with patch.object(self.client, "_sleep_before_retry") as mock_sleep:
                self.client._request_json("http://aemet.test/api/test")
        self.assertEqual(mock_sleep.call_count, 2)

    def test_immediate_success_no_sleep(self):
        data = {"datos": "http://datos.url"}
        with patch(
            "eia_agent.core.aemet_client.requests.get",
            return_value=_mock_response(200, data),
        ):
            with patch.object(self.client, "_sleep_before_retry") as mock_sleep:
                self.client._request_json("http://aemet.test/api/test")
        mock_sleep.assert_not_called()

    def test_one_503_then_success_sleeps_once(self):
        data = {"datos": "url"}
        responses = [_mock_response(503), _mock_response(200, data)]
        with patch("eia_agent.core.aemet_client.requests.get", side_effect=responses):
            with patch.object(self.client, "_sleep_before_retry") as mock_sleep:
                self.client._request_json("http://aemet.test/api/test")
        mock_sleep.assert_called_once()

    def test_three_503_raises_service_error(self):
        responses = [_mock_response(503)] * 3
        with patch("eia_agent.core.aemet_client.requests.get", side_effect=responses):
            with patch.object(self.client, "_sleep_before_retry"):
                with self.assertRaises(AEMETServiceError):
                    self.client._request_json("http://aemet.test/api/test")

    def test_three_429_raises_rate_limit_error(self):
        responses = [_mock_response(429)] * 3
        with patch("eia_agent.core.aemet_client.requests.get", side_effect=responses):
            with patch.object(self.client, "_sleep_before_retry"):
                with self.assertRaises(AEMETRateLimitError):
                    self.client._request_json("http://aemet.test/api/test")

    def test_retry_called_with_correct_attempt_numbers(self):
        data = {"datos": "url"}
        responses = [_mock_response(503), _mock_response(503), _mock_response(200, data)]
        with patch("eia_agent.core.aemet_client.requests.get", side_effect=responses):
            with patch.object(self.client, "_sleep_before_retry") as mock_sleep:
                self.client._request_json("http://aemet.test/api/test")
        self.assertEqual(mock_sleep.call_args_list, [call(0), call(1)])


# ---------------------------------------------------------------------------
# TestDownloadJsonFromDatosUrl
# ---------------------------------------------------------------------------

@unittest.skipUnless(_REQUESTS_OK, "requests no disponible")
class TestDownloadJsonFromDatosUrl(unittest.TestCase):
    def setUp(self):
        self.client = _make_client()

    def test_200_with_list_returns_list(self):
        data = [{"mes": "1", "tm_mes": "18.5"}, {"mes": "2"}]
        with patch(
            "eia_agent.core.aemet_client.requests.get",
            return_value=_mock_response(200, data),
        ):
            result = self.client._download_json_from_datos_url("http://datos.url/abc")
        self.assertEqual(result, data)

    def test_200_with_dict_returns_dict(self):
        data = {"key": "value"}
        with patch(
            "eia_agent.core.aemet_client.requests.get",
            return_value=_mock_response(200, data),
        ):
            result = self.client._download_json_from_datos_url("http://datos.url/abc")
        self.assertEqual(result, data)

    def test_non_200_raises_response_error(self):
        with patch(
            "eia_agent.core.aemet_client.requests.get",
            return_value=_mock_response(404),
        ):
            with self.assertRaises(AEMETResponseError):
                self.client._download_json_from_datos_url("http://datos.url/abc")

    def test_invalid_json_raises_response_error(self):
        with patch(
            "eia_agent.core.aemet_client.requests.get",
            return_value=_mock_response(200, raise_json=ValueError("bad json")),
        ):
            with self.assertRaises(AEMETResponseError):
                self.client._download_json_from_datos_url("http://datos.url/abc")

    def test_timeout_raises_aemet_timeout_error(self):
        with patch(
            "eia_agent.core.aemet_client.requests.get",
            side_effect=requests.Timeout("timeout"),
        ):
            with self.assertRaises(AEMETTimeoutError):
                self.client._download_json_from_datos_url("http://datos.url/abc")

    def test_request_exception_raises_service_error(self):
        with patch(
            "eia_agent.core.aemet_client.requests.get",
            side_effect=requests.RequestException("network error"),
        ):
            with self.assertRaises(AEMETServiceError):
                self.client._download_json_from_datos_url("http://datos.url/abc")

    def test_uses_client_timeout(self):
        client = _make_client(timeout=15)
        data = [{"mes": "1"}]
        with patch(
            "eia_agent.core.aemet_client.requests.get",
            return_value=_mock_response(200, data),
        ) as mock_get:
            client._download_json_from_datos_url("http://datos.url/abc")
        self.assertEqual(mock_get.call_args[1]["timeout"], 15)


# ---------------------------------------------------------------------------
# TestGetNormalesClimatologicas
# ---------------------------------------------------------------------------

@unittest.skipUnless(_REQUESTS_OK, "requests no disponible")
class TestGetNormalesClimatologicas(unittest.TestCase):
    def setUp(self):
        self.client = _make_client(api_key="test_key_abc")

    def test_empty_id_estacion_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.client.get_normales_climatologicas("")

    def test_whitespace_id_estacion_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.client.get_normales_climatologicas("   ")

    def test_none_id_estacion_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.client.get_normales_climatologicas(None)

    def test_valid_id_calls_request_json(self):
        normales = [{"mes": "1", "p_mes": "15.0"}]
        with patch.object(
            self.client, "_request_json", return_value={"datos": "http://datos.url/x"}
        ) as mock_rj:
            with patch.object(
                self.client, "_download_json_from_datos_url", return_value=normales
            ):
                self.client.get_normales_climatologicas("C447A")
        mock_rj.assert_called_once()

    def test_correct_url_constructed(self):
        normales = [{"mes": "1"}]
        with patch.object(
            self.client, "_request_json", return_value={"datos": "http://datos.url/x"}
        ) as mock_rj:
            with patch.object(
                self.client, "_download_json_from_datos_url", return_value=normales
            ):
                self.client.get_normales_climatologicas("C447A")
        expected_url = (
            "http://aemet.test/api/valores/climatologicos/normales/estacion/C447A"
        )
        self.assertEqual(mock_rj.call_args[0][0], expected_url)

    def test_api_key_in_headers(self):
        normales = [{"mes": "1"}]
        with patch.object(
            self.client, "_request_json", return_value={"datos": "http://datos.url/x"}
        ) as mock_rj:
            with patch.object(
                self.client, "_download_json_from_datos_url", return_value=normales
            ):
                self.client.get_normales_climatologicas("C447A")
        headers_passed = mock_rj.call_args[1]["headers"]
        self.assertEqual(headers_passed, {"api_key": "test_key_abc"})

    def test_datos_key_triggers_download(self):
        normales = [{"mes": "1", "p_mes": "15.0"}]
        with patch.object(
            self.client, "_request_json", return_value={"datos": "http://datos.url/xyz"}
        ):
            with patch.object(
                self.client, "_download_json_from_datos_url", return_value=normales
            ) as mock_dl:
                self.client.get_normales_climatologicas("C447A")
        mock_dl.assert_called_once_with("http://datos.url/xyz")

    def test_returns_downloaded_data(self):
        normales = [{"mes": "1", "p_mes": "15.0"}, {"mes": "2", "p_mes": "12.0"}]
        with patch.object(
            self.client, "_request_json", return_value={"datos": "http://datos.url/x"}
        ):
            with patch.object(
                self.client, "_download_json_from_datos_url", return_value=normales
            ):
                result = self.client.get_normales_climatologicas("C447A")
        self.assertEqual(result, normales)

    def test_id_estacion_stripped_before_url(self):
        normales = [{"mes": "1"}]
        with patch.object(
            self.client, "_request_json", return_value={"datos": "http://datos.url/x"}
        ) as mock_rj:
            with patch.object(
                self.client, "_download_json_from_datos_url", return_value=normales
            ):
                self.client.get_normales_climatologicas("  C447A  ")
        url = mock_rj.call_args[0][0]
        self.assertTrue(url.endswith("/C447A"), f"URL debe terminar en /C447A, obtenido: {url}")

    def test_dict_without_datos_raises_response_error(self):
        with patch.object(
            self.client, "_request_json",
            return_value={"estado": 200, "descripcion": "ok sin datos"},
        ):
            with self.assertRaises(AEMETResponseError):
                self.client.get_normales_climatologicas("C447A")

    def test_empty_dict_response_raises_response_error(self):
        with patch.object(self.client, "_request_json", return_value={}):
            with self.assertRaises(AEMETResponseError):
                self.client.get_normales_climatologicas("C447A")

    def test_list_response_returned_directly(self):
        direct_data = [{"mes": "1"}, {"mes": "2"}]
        with patch.object(self.client, "_request_json", return_value=direct_data):
            result = self.client.get_normales_climatologicas("C447A")
        self.assertEqual(result, direct_data)

    def test_custom_base_url_used_in_url(self):
        client = AEMETClient("key", base_url="http://mock.server:9999")
        normales = [{"mes": "1"}]
        with patch.object(
            client, "_request_json", return_value={"datos": "http://datos.url/x"}
        ) as mock_rj:
            with patch.object(
                client, "_download_json_from_datos_url", return_value=normales
            ):
                client.get_normales_climatologicas("B228")
        url = mock_rj.call_args[0][0]
        self.assertTrue(url.startswith("http://mock.server:9999"), f"URL no usa base_url, obtenido: {url}")

    def test_propagates_auth_error_from_request_json(self):
        with patch.object(
            self.client, "_request_json", side_effect=AEMETAuthError("bad key")
        ):
            with self.assertRaises(AEMETAuthError):
                self.client.get_normales_climatologicas("C447A")

    def test_propagates_not_found_error_from_request_json(self):
        with patch.object(
            self.client, "_request_json", side_effect=AEMETNotFoundError("not found")
        ):
            with self.assertRaises(AEMETNotFoundError):
                self.client.get_normales_climatologicas("C447A")

    def test_propagates_rate_limit_error_from_request_json(self):
        with patch.object(
            self.client, "_request_json", side_effect=AEMETRateLimitError("rate limit")
        ):
            with self.assertRaises(AEMETRateLimitError):
                self.client.get_normales_climatologicas("C447A")


# ---------------------------------------------------------------------------
# TestFullTwoStepFlow — flujo completo mockeando solo requests.get
# ---------------------------------------------------------------------------

@unittest.skipUnless(_REQUESTS_OK, "requests no disponible")
class TestFullTwoStepFlow(unittest.TestCase):
    """Ejercita el flujo completo sin mockear métodos internos."""

    def setUp(self):
        self.client = _make_client(api_key="full_test_key")

    def test_full_flow_returns_final_data(self):
        metadata = {"estado": 200, "datos": "http://datos.aemet.test/abc123"}
        normales = [{"mes": "1", "tm_mes": "18.2"}, {"mes": "2", "tm_mes": "18.8"}]
        responses = [_mock_response(200, metadata), _mock_response(200, normales)]
        with patch("eia_agent.core.aemet_client.requests.get", side_effect=responses):
            with patch.object(self.client, "_sleep_before_retry"):
                result = self.client.get_normales_climatologicas("C447A")
        self.assertEqual(result, normales)

    def test_full_flow_makes_exactly_two_requests(self):
        metadata = {"estado": 200, "datos": "http://datos.aemet.test/abc123"}
        normales = [{"mes": "1"}, {"mes": "2"}]
        responses = [_mock_response(200, metadata), _mock_response(200, normales)]
        with patch(
            "eia_agent.core.aemet_client.requests.get", side_effect=responses
        ) as mock_get:
            with patch.object(self.client, "_sleep_before_retry"):
                self.client.get_normales_climatologicas("C447A")
        self.assertEqual(mock_get.call_count, 2)

    def test_full_flow_first_request_has_api_key_header(self):
        metadata = {"estado": 200, "datos": "http://datos.aemet.test/abc123"}
        normales = [{"mes": "1"}]
        responses = [_mock_response(200, metadata), _mock_response(200, normales)]
        with patch(
            "eia_agent.core.aemet_client.requests.get", side_effect=responses
        ) as mock_get:
            with patch.object(self.client, "_sleep_before_retry"):
                self.client.get_normales_climatologicas("C447A")
        first_call_headers = mock_get.call_args_list[0][1]["headers"]
        self.assertEqual(first_call_headers, {"api_key": "full_test_key"})

    def test_full_flow_second_request_to_datos_url(self):
        datos_url = "http://datos.aemet.test/abc123"
        metadata = {"estado": 200, "datos": datos_url}
        normales = [{"mes": "1"}]
        responses = [_mock_response(200, metadata), _mock_response(200, normales)]
        with patch(
            "eia_agent.core.aemet_client.requests.get", side_effect=responses
        ) as mock_get:
            with patch.object(self.client, "_sleep_before_retry"):
                self.client.get_normales_climatologicas("C447A")
        second_call_url = mock_get.call_args_list[1][0][0]
        self.assertEqual(second_call_url, datos_url)

    def test_full_flow_with_retry_on_first_request(self):
        metadata = {"estado": 200, "datos": "http://datos.test/xyz"}
        normales = [{"mes": "1"}, {"mes": "2"}]
        responses = [
            _mock_response(503),           # primer intento: error transitorio
            _mock_response(200, metadata), # reintento: éxito
            _mock_response(200, normales), # descarga URL de datos
        ]
        with patch("eia_agent.core.aemet_client.requests.get", side_effect=responses):
            with patch.object(self.client, "_sleep_before_retry"):
                result = self.client.get_normales_climatologicas("C447A")
        self.assertEqual(result, normales)

    def test_auth_error_in_first_request_propagates(self):
        with patch(
            "eia_agent.core.aemet_client.requests.get",
            return_value=_mock_response(401),
        ):
            with self.assertRaises(AEMETAuthError):
                self.client.get_normales_climatologicas("C447A")


# ---------------------------------------------------------------------------
# TestAEMETIntegration — requiere AEMET_API_KEY real en el entorno
# ---------------------------------------------------------------------------

@unittest.skipUnless(_REQUESTS_OK, "requests no disponible")
class TestAEMETIntegration(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("AEMET_API_KEY"),
        "AEMET_API_KEY no configurada — test de integración saltado",
    )
    def test_real_normales_call_returns_list(self):
        """Llama a AEMET real. Solo se ejecuta si AEMET_API_KEY está configurada."""
        client = AEMETClient.from_env()
        try:
            # Estación de Las Palmas de Gran Canaria (C447A)
            result = client.get_normales_climatologicas("C447A")
            self.assertIsInstance(result, (list, dict))
            if isinstance(result, list):
                self.assertGreater(len(result), 0)
        except (AEMETNotFoundError, AEMETServiceError, AEMETTimeoutError):
            self.skipTest("Servicio AEMET no disponible durante el test")


if __name__ == "__main__":
    unittest.main()

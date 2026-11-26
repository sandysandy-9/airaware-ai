"""Stage 2 Regression Tests — Historical CAMS Domain & Future-Timestamp Boundary."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.providers.models import ProviderError, ProviderValidationError
from app.providers.open_meteo import OpenMeteoProvider


@pytest.mark.asyncio
async def test_historical_excludes_future_forecast_timestamps_and_pins_cams_domain():
    """Historical series must request cams_global, forecast_days=1, and exclude dt_utc > reference_time_utc."""
    ref_utc = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
    # Mix past hours (-24h, -1h, 0h) + future forecast hours (+1h, +24h) + stale (>past_days)
    timestamps = [
        (ref_utc - timedelta(days=8)).strftime("%Y-%m-%dT%H:%M"),
        (ref_utc - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
        ref_utc.strftime("%Y-%m-%dT%H:%M"),
        (ref_utc + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
        (ref_utc + timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M"),
    ]
    mock_payload = {
        "latitude": 28.6,
        "longitude": 77.2,
        "timezone": "GMT",
        "utc_offset_seconds": 0,
        "hourly": {
            "time": timestamps,
            "pm2_5": [50.0, 95.0, 105.0, 220.0, 310.0],
            "pm10": [60.0, 110.0, 120.0, 240.0, 330.0],
            "nitrogen_dioxide": [20.0, 40.0, 45.0, 70.0, 80.0],
            "sulphur_dioxide": [10.0, 15.0, 20.0, 25.0, 30.0],
            "carbon_monoxide": [500.0, 1000.0, 1200.0, 2000.0, 2500.0],
            "ozone": [30.0, 40.0, 45.0, 60.0, 70.0],
        },
    }

    captured_params = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None):
            captured_params.update(params or {})
            req = httpx.Request("GET", url, params=params)
            return httpx.Response(200, json=mock_payload, request=req)

    provider = OpenMeteoProvider()
    with patch("app.providers.open_meteo.httpx.AsyncClient", FakeClient):
        trends = await provider.get_historical_air_quality(
            location_name="New Delhi",
            latitude=28.6139,
            longitude=77.2090,
            past_days=7,
            reference_time_utc=ref_utc,
        )

    assert captured_params["domains"] == "cams_global"
    assert captured_params["forecast_days"] == 1
    assert trends.total_points == 2
    assert [p.timestamp for p in trends.data_points] == [
        (ref_utc - timedelta(hours=2)).isoformat(),
        ref_utc.isoformat(),
    ]
    assert trends.start_time == (ref_utc - timedelta(hours=2)).isoformat()
    assert trends.end_time == ref_utc.isoformat()
    assert "not physical monitoring station observations" in trends.note.lower()


@pytest.mark.asyncio
async def test_historical_preserves_missing_values_as_none_and_rejects_bad_payload():
    """Unavailable/negative historical samples remain None (never 0); malformed payload raises ProviderValidationError."""
    ref_utc = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
    bad_sample_payload = {
        "timezone": "UTC",
        "utc_offset_seconds": 0,
        "hourly": {
            "time": [ref_utc.strftime("%Y-%m-%dT%H:%M")],
            "pm2_5": [None],
            "pm10": [-5.0],
            "nitrogen_dioxide": [float("nan")],
            "sulphur_dioxide": [True],
            "carbon_monoxide": [None],
            "ozone": [None],
        },
    }

    class FakeClient:
        def __init__(self, payload):
            self.payload = payload

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None):
            req = httpx.Request("GET", url, params=params)
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = lambda: None
            resp.json = lambda: self.payload
            resp.request = req
            return resp

    provider = OpenMeteoProvider()
    with patch("app.providers.open_meteo.httpx.AsyncClient", return_value=FakeClient(bad_sample_payload)):
        trends = await provider.get_historical_air_quality(
            location_name="New Delhi",
            latitude=28.6139,
            longitude=77.2090,
            past_days=1,
            reference_time_utc=ref_utc,
        )

    assert trends.total_points == 1
    pt = trends.data_points[0]
    assert pt.pm25 is None
    assert pt.pm10 is None
    assert pt.no2 is None
    assert pt.so2 is None
    assert pt.co is None
    assert pt.o3 is None
    assert pt.aqi is None

    with patch("app.providers.open_meteo.httpx.AsyncClient", return_value=FakeClient({"error": True, "reason": "bad"})):
        with pytest.raises(ProviderValidationError):
            await provider.get_historical_air_quality("New Delhi", 28.6, 77.2, past_days=1, reference_time_utc=ref_utc)


@pytest.mark.asyncio
async def test_historical_maps_timeout_to_provider_error():
    """Upstream timeouts raise ProviderError(is_timeout=True) rather than unhandled httpx exceptions."""

    class TimeoutClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None):
            raise httpx.ReadTimeout("timeout")

    provider = OpenMeteoProvider()
    with patch("app.providers.open_meteo.httpx.AsyncClient", return_value=TimeoutClient()):
        with pytest.raises(ProviderError) as exc_info:
            await provider.get_historical_air_quality("New Delhi", 28.6, 77.2, past_days=7)
    assert exc_info.value.is_timeout is True


@pytest.mark.asyncio
async def test_historical_24h_lookback_includes_yesterday_evening_and_todays_elapsed_hours_only():
    """With forecast_days=1, past_days=1 retains yesterday evening through today's elapsed UTC hours (inclusive) and drops future hours."""
    # Mid-afternoon UTC: lookback window is [2026-11-25 15:00Z, 2026-11-26 15:00Z]
    ref_utc = datetime(2026, 11, 26, 15, 0, tzinfo=timezone.utc)
    candidate_hours_utc = [
        datetime(2026, 11, 25, 14, 0, tzinfo=timezone.utc),  # outside (25h ago) -> excluded
        datetime(2026, 11, 25, 15, 0, tzinfo=timezone.utc),  # exact lookback boundary (24h ago) -> included
        datetime(2026, 11, 25, 22, 0, tzinfo=timezone.utc),  # yesterday evening -> included
        datetime(2026, 11, 26, 0, 0, tzinfo=timezone.utc),   # today's first hour -> included
        datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc),   # today's morning -> included
        datetime(2026, 11, 26, 15, 0, tzinfo=timezone.utc),  # current retrieval hour -> included
        datetime(2026, 11, 26, 16, 0, tzinfo=timezone.utc),  # future hour today (forecast_days=1) -> excluded
        datetime(2026, 11, 26, 23, 0, tzinfo=timezone.utc),  # future hour end of today -> excluded
    ]
    n = len(candidate_hours_utc)
    payload = {
        "latitude": 28.6,
        "longitude": 77.2,
        "timezone": "GMT",
        "utc_offset_seconds": 0,
        "hourly": {
            "time": [dt.strftime("%Y-%m-%dT%H:%M") for dt in candidate_hours_utc],
            "pm2_5": [float(100 + i) for i in range(n)],
            "pm10": [float(140 + i) for i in range(n)],
            "nitrogen_dioxide": [40.0] * n,
            "sulphur_dioxide": [12.0] * n,
            "carbon_monoxide": [900.0] * n,
            "ozone": [35.0] * n,
        },
    }

    captured_params = {}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None):
            captured_params.update(params or {})
            req = httpx.Request("GET", url, params=params)
            return httpx.Response(200, json=payload, request=req)

    provider = OpenMeteoProvider()
    with patch("app.providers.open_meteo.httpx.AsyncClient", return_value=FakeClient()):
        trends = await provider.get_historical_air_quality(
            location_name="New Delhi",
            latitude=28.6139,
            longitude=77.2090,
            past_days=1,
            reference_time_utc=ref_utc,
        )

    assert captured_params["past_days"] == 1
    assert captured_params["forecast_days"] == 1
    expected_included = [
        datetime(2026, 11, 25, 15, 0, tzinfo=timezone.utc),
        datetime(2026, 11, 25, 22, 0, tzinfo=timezone.utc),
        datetime(2026, 11, 26, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc),
        datetime(2026, 11, 26, 15, 0, tzinfo=timezone.utc),
    ]
    assert trends.total_points == len(expected_included)
    assert [p.timestamp for p in trends.data_points] == [dt.isoformat() for dt in expected_included]
    assert trends.start_time == expected_included[0].isoformat()
    assert trends.end_time == expected_included[-1].isoformat()


@pytest.mark.asyncio
async def test_historical_timezone_conversion_ist_filters_strict_utc_window():
    """Provider timestamps in Asia/Kolkata (+05:30) convert accurately to UTC before lookback/future filtering."""
    # Reference time: 2026-11-26T20:30+05:30 == 2026-11-26T15:00:00+00:00
    # 24h lookback boundary: 2026-11-25T20:30+05:30 == 2026-11-25T15:00:00+00:00
    ref_utc = datetime(2026, 11, 26, 15, 0, tzinfo=timezone.utc)
    ist_times = [
        "2026-11-25T20:00",  # 14:30Z -> older than 24h -> excluded
        "2026-11-25T20:30",  # 15:00Z -> exact 24h boundary -> included
        "2026-11-26T00:30",  # 2026-11-25T19:00Z (yesterday UTC, today IST) -> included
        "2026-11-26T06:00",  # 2026-11-26T00:30Z (today's elapsed IST/UTC) -> included
        "2026-11-26T20:30",  # 2026-11-26T15:00Z (exact retrieval time) -> included
        "2026-11-26T21:00",  # 2026-11-26T15:30Z (future forecast in IST) -> excluded
    ]
    n = len(ist_times)
    payload = {
        "latitude": 19.076,
        "longitude": 72.8777,
        "timezone": "Asia/Kolkata",
        "utc_offset_seconds": 19800,
        "hourly": {
            "time": ist_times,
            "pm2_5": [80.0 + i for i in range(n)],
            "pm10": [110.0 + i for i in range(n)],
            "nitrogen_dioxide": [30.0] * n,
            "sulphur_dioxide": [10.0] * n,
            "carbon_monoxide": [700.0] * n,
            "ozone": [40.0] * n,
        },
    }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None):
            req = httpx.Request("GET", url, params=params)
            return httpx.Response(200, json=payload, request=req)

    provider = OpenMeteoProvider()
    with patch("app.providers.open_meteo.httpx.AsyncClient", return_value=FakeClient()):
        trends = await provider.get_historical_air_quality(
            location_name="Mumbai",
            latitude=19.0760,
            longitude=72.8777,
            past_days=1,
            reference_time_utc=ref_utc,
        )

    assert [p.timestamp for p in trends.data_points] == [
        "2026-11-25T15:00:00+00:00",
        "2026-11-25T19:00:00+00:00",
        "2026-11-26T00:30:00+00:00",
        "2026-11-26T15:00:00+00:00",
    ]
    assert trends.end_time == "2026-11-26T15:00:00+00:00"

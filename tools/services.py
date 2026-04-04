import requests
from django.conf import settings


def get_weather(lat: float, lng: float) -> dict:
    """Get current weather and 7-day precipitation forecast from OpenWeatherMap."""
    api_key = settings.OPENWEATHERMAP_API_KEY
    if not api_key:
        return _static_weather()

    try:
        # Current weather
        current_url = "https://api.openweathermap.org/data/2.5/weather"
        current_resp = requests.get(current_url, params={
            "lat": lat, "lon": lng, "appid": api_key, "units": "imperial"
        }, timeout=10)
        current_resp.raise_for_status()
        current = current_resp.json()

        # 5-day forecast (free tier)
        forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
        forecast_resp = requests.get(forecast_url, params={
            "lat": lat, "lon": lng, "appid": api_key, "units": "imperial"
        }, timeout=10)
        forecast_resp.raise_for_status()
        forecast = forecast_resp.json()

        # Build precipitation forecast from 3-hour intervals
        precip_forecast = []
        seen_dates = set()
        for item in forecast.get("list", []):
            date = item["dt_txt"].split(" ")[0]
            if date not in seen_dates:
                seen_dates.add(date)
                rain = item.get("rain", {}).get("3h", 0)
                pop = item.get("pop", 0) * 100
                precip_forecast.append({
                    "date": date,
                    "precip_in": round(rain / 25.4, 2),
                    "prob_pct": round(pop),
                })

        return {
            "temp_f": current["main"]["temp"],
            "temp_c": round((current["main"]["temp"] - 32) * 5 / 9, 1),
            "humidity_pct": current["main"]["humidity"],
            "wind_mph": current["wind"]["speed"],
            "conditions": current["weather"][0]["description"],
            "uv_index": current.get("uvi", None),
            "precipitation_forecast": precip_forecast[:7],
        }
    except Exception:
        return _static_weather()


def get_crop_health(field_id: str) -> dict:
    """Get NDVI vegetation health score. Static data for hackathon demo."""
    return {
        "field_id": field_id,
        "ndvi_score": 0.42,
        "stress_level": "moderate",
        "vegetation_trend": "declining",
        "last_satellite_date": "2026-04-03T14:30:00Z",
        "vegetation_fraction": 0.58,
    }


def get_soil_profile(field_id: str) -> dict:
    """Get USDA soil profile. Static data for hackathon demo."""
    return {
        "field_id": field_id,
        "soil_type": "Casa Grande sandy loam",
        "ph": 7.8,
        "organic_matter_pct": 1.2,
        "drainage_class": "well-drained",
        "water_holding_capacity": "low",
        "available_water_in_per_ft": 1.1,
    }


def _static_weather() -> dict:
    """Fallback static weather data for Casa Grande, AZ."""
    return {
        "temp_f": 105,
        "temp_c": 40.6,
        "humidity_pct": 12,
        "wind_mph": 8,
        "conditions": "clear sky",
        "uv_index": 11,
        "precipitation_forecast": [
            {"date": "2026-04-04", "precip_in": 0.0, "prob_pct": 0},
            {"date": "2026-04-05", "precip_in": 0.0, "prob_pct": 5},
            {"date": "2026-04-06", "precip_in": 0.0, "prob_pct": 0},
            {"date": "2026-04-07", "precip_in": 0.0, "prob_pct": 0},
            {"date": "2026-04-08", "precip_in": 0.0, "prob_pct": 0},
            {"date": "2026-04-09", "precip_in": 0.0, "prob_pct": 10},
            {"date": "2026-04-10", "precip_in": 0.0, "prob_pct": 0},
        ],
    }

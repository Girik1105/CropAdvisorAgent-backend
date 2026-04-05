import requests
from django.conf import settings
from django.utils import timezone


def get_weather(lat: float, lng: float, field=None, session=None) -> dict:
    """
    Get current weather and 7-day precipitation forecast from OpenWeatherMap.
    Saves a WeatherSnapshot if field is provided.
    """
    api_key = settings.OPENWEATHERMAP_API_KEY
    if not api_key:
        data = _static_weather()
    else:
        try:
            current_url = "https://api.openweathermap.org/data/2.5/weather"
            current_resp = requests.get(current_url, params={
                "lat": lat, "lon": lng, "appid": api_key, "units": "imperial"
            }, timeout=10)
            current_resp.raise_for_status()
            current = current_resp.json()

            forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
            forecast_resp = requests.get(forecast_url, params={
                "lat": lat, "lon": lng, "appid": api_key, "units": "imperial"
            }, timeout=10)
            forecast_resp.raise_for_status()
            forecast = forecast_resp.json()

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

            data = {
                "temp_f": current["main"]["temp"],
                "temp_c": round((current["main"]["temp"] - 32) * 5 / 9, 1),
                "humidity_pct": current["main"]["humidity"],
                "wind_mph": current["wind"]["speed"],
                "conditions": current["weather"][0]["description"],
                "uv_index": current.get("uvi", None),
                "precipitation_forecast": precip_forecast[:7],
            }
        except Exception:
            data = _static_weather()

    # Save snapshot to DB
    if field:
        from agent.models import WeatherSnapshot
        WeatherSnapshot.objects.create(
            field=field,
            session=session,
            temp_f=data["temp_f"],
            temp_c=data["temp_c"],
            humidity_pct=data["humidity_pct"],
            wind_mph=data["wind_mph"],
            conditions=data["conditions"],
            uv_index=data.get("uv_index"),
            precipitation_forecast=data["precipitation_forecast"],
        )

    return data


def get_crop_health(field_id: str, field=None) -> dict:
    """
    Get NDVI vegetation health score.
    Reads latest CropHealthRecord from DB if one exists for this field,
    otherwise returns default values and saves a record.
    """
    from agent.models import CropHealthRecord

    if field:
        record = CropHealthRecord.objects.filter(field=field).first()
        if record:
            return {
                "field_id": field_id,
                "ndvi_score": record.ndvi_score,
                "stress_level": record.stress_level,
                "vegetation_trend": record.vegetation_trend,
                "last_satellite_date": record.last_satellite_date.isoformat() if record.last_satellite_date else None,
                "vegetation_fraction": record.vegetation_fraction,
            }

    # Default data — save to DB if field provided
    data = {
        "field_id": field_id,
        "ndvi_score": 0.42,
        "stress_level": "moderate",
        "vegetation_trend": "declining",
        "last_satellite_date": "2026-04-03T14:30:00Z",
        "vegetation_fraction": 0.58,
    }

    if field:
        CropHealthRecord.objects.create(
            field=field,
            ndvi_score=data["ndvi_score"],
            stress_level=data["stress_level"],
            vegetation_trend=data["vegetation_trend"],
            vegetation_fraction=data["vegetation_fraction"],
            last_satellite_date=timezone.datetime(2026, 4, 3, 14, 30, tzinfo=timezone.utc),
        )

    return data


def get_soil_profile(field_id: str, field=None) -> dict:
    """
    Get USDA soil profile.
    Reads SoilProfile from DB if one exists for this field,
    otherwise returns default values and saves a record.
    """
    from agent.models import SoilProfile

    if field:
        try:
            profile = field.soil_profile
            return {
                "field_id": field_id,
                "soil_type": profile.soil_type,
                "ph": profile.ph,
                "organic_matter_pct": profile.organic_matter_pct,
                "drainage_class": profile.drainage_class,
                "water_holding_capacity": profile.water_holding_capacity,
                "available_water_in_per_ft": profile.available_water_in_per_ft,
            }
        except SoilProfile.DoesNotExist:
            pass

    # Default data — save to DB if field provided
    data = {
        "field_id": field_id,
        "soil_type": "Casa Grande sandy loam",
        "ph": 7.8,
        "organic_matter_pct": 1.2,
        "drainage_class": "well-drained",
        "water_holding_capacity": "low",
        "available_water_in_per_ft": 1.1,
    }

    if field:
        SoilProfile.objects.create(
            field=field,
            soil_type=data["soil_type"],
            ph=data["ph"],
            organic_matter_pct=data["organic_matter_pct"],
            drainage_class=data["drainage_class"],
            water_holding_capacity=data["water_holding_capacity"],
            available_water_in_per_ft=data["available_water_in_per_ft"],
        )

    return data


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

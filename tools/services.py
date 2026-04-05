import requests
from django.conf import settings
from django.utils import timezone
from datetime import datetime


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


# ──────────────────────────────────────────────────────────
# NEW TOOLS
# ──────────────────────────────────────────────────────────


MARKET_DATA = {
    "cotton": {"price": 0.82, "unit": "lb", "trend_30d": "stable", "outlook": "Prices expected to hold through summer. Upland cotton futures steady around 80-85 cents."},
    "citrus": {"price": 28.50, "unit": "box", "trend_30d": "up_5pct", "outlook": "Strong demand driven by juice market. Prices rising due to limited Florida supply."},
    "alfalfa": {"price": 225.0, "unit": "ton", "trend_30d": "down_3pct", "outlook": "Oversupply in the Southwest. Expect continued softness through Q2."},
    "corn": {"price": 4.45, "unit": "bushel", "trend_30d": "up_2pct", "outlook": "Drought concerns in the Midwest supporting prices. Export demand steady."},
    "wheat": {"price": 5.80, "unit": "bushel", "trend_30d": "down_1pct", "outlook": "Large global stocks keeping downward pressure. Winter wheat crop in good condition."},
    "soybean": {"price": 11.20, "unit": "bushel", "trend_30d": "up_3pct", "outlook": "South American crop shortfall boosting prices. Strong crush margins."},
    "vegetables": {"price": 18.00, "unit": "cwt", "trend_30d": "stable", "outlook": "Seasonal produce prices normal for spring. Desert growing season winding down."},
    "other": {"price": 0.0, "unit": "unit", "trend_30d": "unknown", "outlook": "No market data available for this crop type."},
}


def get_market_prices(crop_type: str, field=None, session=None) -> dict:
    """
    Get current commodity market prices and outlook for a crop type.
    Uses static data representing realistic USDA/commodity exchange prices.
    """
    from agent.models import MarketSnapshot

    key = crop_type.lower().strip()
    info = MARKET_DATA.get(key, MARKET_DATA["other"])

    data = {
        "crop_type": crop_type,
        "price_per_unit": info["price"],
        "unit": info["unit"],
        "trend_30d": info["trend_30d"],
        "seasonal_outlook": info["outlook"],
    }

    if field and session:
        MarketSnapshot.objects.create(
            field=field,
            session=session,
            crop_type=crop_type,
            price_per_unit=info["price"],
            unit=info["unit"],
            trend_30d=info["trend_30d"],
            seasonal_outlook=info["outlook"],
        )

    return data


# Pest/disease rules keyed by conditions
PEST_RULES = [
    {
        "condition": lambda t, h, crop: h > 60 and t > 75,
        "risk_level": "high",
        "threats": ["Fungal diseases (powdery mildew, downy mildew)", "Root rot", "Bacterial leaf blight"],
        "actions": ["Apply preventive fungicide", "Improve air circulation between rows", "Avoid overhead irrigation"],
    },
    {
        "condition": lambda t, h, crop: h < 20 and t > 95,
        "risk_level": "high",
        "threats": ["Spider mites", "Thrips", "Heat stress damage"],
        "actions": ["Scout for mite webbing on leaf undersides", "Consider miticide if >20% leaf damage", "Increase irrigation frequency"],
    },
    {
        "condition": lambda t, h, crop: 60 <= t <= 85 and 30 <= h <= 60,
        "risk_level": "moderate",
        "threats": ["Aphids (spring migration)", "Whiteflies", "Leafhopper damage"],
        "actions": ["Monitor sticky traps weekly", "Release beneficial insects (lacewings, ladybugs)", "Spot-treat if threshold exceeded"],
    },
    {
        "condition": lambda t, h, crop: crop.lower() == "cotton" and t > 90,
        "risk_level": "moderate",
        "threats": ["Cotton bollworm (Helicoverpa)", "Lygus bug", "Aphid colonies"],
        "actions": ["Scout bolls for entry holes", "Check for square shedding", "Consider BT spray if >8% boll damage"],
    },
    {
        "condition": lambda t, h, crop: crop.lower() == "citrus",
        "risk_level": "moderate",
        "threats": ["Citrus leafminer", "Asian citrus psyllid", "Citrus canker"],
        "actions": ["Inspect new growth flushes", "Apply systemic insecticide if psyllid detected", "Remove infected material"],
    },
]


def get_pest_risk(crop_type: str, temp_f: float, humidity_pct: float, field=None, session=None) -> dict:
    """
    Calculate pest and disease risk based on crop type and current weather conditions.
    Uses rule-based assessment logic.
    """
    from agent.models import PestRiskAssessment

    threats = []
    actions = []
    risk_level = "low"

    for rule in PEST_RULES:
        try:
            if rule["condition"](temp_f, humidity_pct, crop_type):
                if rule["risk_level"] == "high":
                    risk_level = "high"
                elif rule["risk_level"] == "moderate" and risk_level != "high":
                    risk_level = "moderate"
                threats.extend(rule["threats"])
                actions.extend(rule["actions"])
        except Exception:
            continue

    # Deduplicate
    threats = list(dict.fromkeys(threats))
    actions = list(dict.fromkeys(actions))

    if not threats:
        threats = ["No significant pest pressure detected at current conditions"]
        actions = ["Continue routine scouting on weekly schedule"]

    data = {
        "crop_type": crop_type,
        "risk_level": risk_level,
        "primary_threats": threats,
        "preventive_actions": actions,
        "conditions_assessed": {"temp_f": temp_f, "humidity_pct": humidity_pct},
    }

    if field and session:
        PestRiskAssessment.objects.create(
            field=field,
            session=session,
            risk_level=risk_level,
            primary_threats=threats,
            preventive_actions=actions,
        )

    return data


# Water usage factors by crop type (gallons per acre per day at peak demand)
WATER_USAGE_FACTORS = {
    "cotton": {"peak_gal_per_acre_day": 5400, "kc": 1.15},
    "citrus": {"peak_gal_per_acre_day": 4800, "kc": 0.85},
    "alfalfa": {"peak_gal_per_acre_day": 7200, "kc": 1.20},
    "corn": {"peak_gal_per_acre_day": 6000, "kc": 1.20},
    "wheat": {"peak_gal_per_acre_day": 3600, "kc": 0.95},
    "soybean": {"peak_gal_per_acre_day": 5000, "kc": 1.10},
    "vegetables": {"peak_gal_per_acre_day": 4200, "kc": 1.00},
}


def get_water_usage(field_id: str, field=None, session=None, weather_data=None, soil_data=None) -> dict:
    """
    Calculate irrigation water needs based on crop, area, weather, and soil.
    Returns daily water budget with deficit and cost estimate.
    """
    from agent.models import WaterUsageEstimate

    crop_type = field.crop_type.lower() if field else "cotton"
    area = field.area_acres if field else 40
    factors = WATER_USAGE_FACTORS.get(crop_type, WATER_USAGE_FACTORS["cotton"])

    # Adjust for temperature (higher demand in heat)
    temp_f = weather_data.get("temp_f", 90) if weather_data else 90
    temp_multiplier = 1.0
    if temp_f > 100:
        temp_multiplier = 1.25
    elif temp_f > 90:
        temp_multiplier = 1.10
    elif temp_f < 70:
        temp_multiplier = 0.80

    daily_need_per_acre = factors["peak_gal_per_acre_day"] * temp_multiplier
    daily_need_total = daily_need_per_acre * area

    # Soil water holding affects deficit
    whc = "low"
    if soil_data:
        whc = soil_data.get("water_holding_capacity", "low")
    deficit_pct = {"low": 65, "moderate": 40, "high": 20}.get(whc.lower(), 50)

    # Adjust deficit for recent precipitation
    if weather_data and weather_data.get("precipitation_forecast"):
        upcoming_rain = sum(
            d.get("precip_in", 0) for d in weather_data["precipitation_forecast"][:3]
        )
        if upcoming_rain > 0.5:
            deficit_pct = max(10, deficit_pct - 25)

    # Cost estimate (Arizona water prices ~$80 per acre-foot)
    acre_feet_needed = (daily_need_total * deficit_pct / 100) / 325851  # gallons to acre-feet
    cost_per_acre_foot = 85
    est_daily_cost = round(acre_feet_needed * cost_per_acre_foot, 2)

    if deficit_pct > 50:
        recommendation = f"Irrigate within 24 hours. Apply {daily_need_per_acre * deficit_pct / 100 / 27154:.1f} acre-inches."
    elif deficit_pct > 30:
        recommendation = "Monitor soil moisture. Irrigation may be needed within 2-3 days."
    else:
        recommendation = "Soil moisture adequate. Continue current irrigation schedule."

    data = {
        "field_id": field_id,
        "crop_type": crop_type,
        "area_acres": area,
        "daily_water_need_gal": round(daily_need_total),
        "current_deficit_pct": deficit_pct,
        "irrigation_recommendation": recommendation,
        "estimated_daily_cost": est_daily_cost,
        "temp_adjustment": f"{temp_multiplier:.2f}x (temp={temp_f}°F)",
    }

    if field and session:
        WaterUsageEstimate.objects.create(
            field=field,
            session=session,
            daily_need_gal=round(daily_need_total),
            deficit_pct=deficit_pct,
            recommendation=recommendation,
            est_cost=est_daily_cost,
        )

    return data


# Growth stages by crop and month
GROWTH_STAGES = {
    "cotton": {
        1: {"stage": "Dormant", "tips": "Plan seed orders and equipment maintenance.", "watch_for": "Nothing active."},
        2: {"stage": "Pre-planting", "tips": "Soil preparation, pre-irrigation if needed.", "watch_for": "Soil temperature — need 65°F+ for planting."},
        3: {"stage": "Pre-planting", "tips": "Final field prep, herbicide application.", "watch_for": "Soil moisture levels for planting."},
        4: {"stage": "Planting / Emergence", "tips": "Plant when soil temp stable above 65°F. Ensure good seed-to-soil contact.", "watch_for": "Seedling diseases, thrips damage on cotyledons."},
        5: {"stage": "Seedling / Squaring", "tips": "First irrigation 3-4 weeks after emergence. Scout weekly.", "watch_for": "Aphids, thrips, early square set."},
        6: {"stage": "Squaring / Early Bloom", "tips": "Peak water demand begins. Maintain 4-day irrigation cycle.", "watch_for": "Lygus bug, bollworm eggs, square retention rate."},
        7: {"stage": "Peak Bloom", "tips": "Maximum water and nutrient demand. Apply final nitrogen.", "watch_for": "Bollworm, heat stress above 110°F, boll rot."},
        8: {"stage": "Boll Development", "tips": "Maintain irrigation but prepare to cut off.", "watch_for": "Boll rot, stink bugs, premature opening."},
        9: {"stage": "Boll Opening / Defoliation", "tips": "Apply defoliant when 60%+ bolls open. Schedule harvest.", "watch_for": "Regrowth, weather delays for defoliation."},
        10: {"stage": "Harvest", "tips": "Harvest when 80%+ bolls open. Gin within 30 days.", "watch_for": "Rain damage, bark contamination."},
        11: {"stage": "Post-harvest", "tips": "Stalk destruction, soil sampling.", "watch_for": "Overwintering pest sites."},
        12: {"stage": "Dormant", "tips": "Equipment maintenance, record keeping.", "watch_for": "Plan next season."},
    },
    "citrus": {
        1: {"stage": "Winter dormancy", "tips": "Minimal irrigation. Prune dead wood.", "watch_for": "Frost damage below 28°F."},
        2: {"stage": "Pre-bloom", "tips": "Apply pre-bloom fertilizer (nitrogen + micronutrients).", "watch_for": "Scale insects, begin psyllid monitoring."},
        3: {"stage": "Bloom", "tips": "Ensure adequate irrigation. Avoid disturbing pollinators.", "watch_for": "Citrus flower moth, frost risk on blossoms."},
        4: {"stage": "Fruit set / Early development", "tips": "Post-bloom irrigation critical. Apply micronutrients.", "watch_for": "June drop, leafminer on new flush."},
        5: {"stage": "Fruit development", "tips": "Consistent irrigation schedule. Monitor fruit size.", "watch_for": "Mites, scale, fruit splitting from irregular watering."},
        6: {"stage": "Fruit development", "tips": "Peak water demand. Mulch to conserve moisture.", "watch_for": "Heat stress, sunburn on fruit."},
        7: {"stage": "Summer growth flush", "tips": "Monitor for Asian citrus psyllid on new growth.", "watch_for": "Psyllid, leafminer, summer mites."},
        8: {"stage": "Fruit sizing", "tips": "Maintain irrigation. Apply potassium for fruit quality.", "watch_for": "Fruit fly, Alternaria brown spot."},
        9: {"stage": "Color break", "tips": "Reduce irrigation slightly to improve sugar content.", "watch_for": "Split fruit, Mediterranean fruit fly."},
        10: {"stage": "Maturation", "tips": "Begin harvest when Brix:acid ratio is optimal.", "watch_for": "Post-harvest decay, cold front timing."},
        11: {"stage": "Harvest", "tips": "Pick carefully to avoid rind damage.", "watch_for": "Decay pressure, frost risk."},
        12: {"stage": "Post-harvest / Dormancy", "tips": "Apply post-harvest fungicide. Light pruning.", "watch_for": "Freeze protection below 28°F."},
    },
    "alfalfa": {
        1: {"stage": "Winter dormancy", "tips": "Minimal activity. Plan spring fertilization.", "watch_for": "Weevil overwintering sites."},
        2: {"stage": "Early green-up", "tips": "Apply early-season irrigation if soil dry.", "watch_for": "Alfalfa weevil larvae in stem tips."},
        3: {"stage": "Active growth — Cut 1 approaching", "tips": "Scout for weevils. Irrigate to support rapid growth.", "watch_for": "Weevil feeding >30% damage = treat before cut."},
        4: {"stage": "First cutting", "tips": "Cut at 10% bloom or 28-day intervals. Irrigate immediately after.", "watch_for": "Rain delays, windrow drying time."},
        5: {"stage": "Regrowth / Cut 2", "tips": "Irrigate 3-5 days after cutting. Scout for aphids.", "watch_for": "Blue alfalfa aphid, pea aphid."},
        6: {"stage": "Peak production — Cut 3", "tips": "Maximum water demand. 4-day irrigation cycle.", "watch_for": "Leafhopper, spider mites in hot weather."},
        7: {"stage": "Summer cuts (4-5)", "tips": "Cut every 25-28 days. Monitor for heat stress.", "watch_for": "Armyworm, webworm, summer slump."},
        8: {"stage": "Late summer cutting", "tips": "Continue 28-day cycle. Quality may decline in heat.", "watch_for": "Spider mites, whitefly."},
        9: {"stage": "Fall cuts", "tips": "Last cut by mid-September to allow winter hardening.", "watch_for": "Stand thinning, crown health."},
        10: {"stage": "Final harvest window", "tips": "Stop cutting 4-6 weeks before first frost.", "watch_for": "Fall armyworm, late-season weeds."},
        11: {"stage": "Fall dormancy", "tips": "Light irrigation to maintain root reserves.", "watch_for": "Winter weed establishment."},
        12: {"stage": "Dormant", "tips": "Evaluate stand density. Plan renovations if needed.", "watch_for": "Gopher damage, crown rot."},
    },
}

# Default for crops without specific calendar
DEFAULT_GROWTH_STAGE = {
    "stage": "Active growth",
    "tips": "Follow standard agronomic practices for your crop and region.",
    "watch_for": "Monitor for pests, diseases, and nutrient deficiencies.",
}


def get_growth_stage(crop_type: str) -> dict:
    """
    Get current growth stage and care tips for a crop based on time of year.
    Pure computation — no database persistence.
    """
    month = datetime.now().month
    key = crop_type.lower().strip()
    stages = GROWTH_STAGES.get(key, {})
    info = stages.get(month, DEFAULT_GROWTH_STAGE)

    return {
        "crop_type": crop_type,
        "month": month,
        "growth_stage": info["stage"],
        "care_tips": info["tips"],
        "watch_for": info["watch_for"],
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

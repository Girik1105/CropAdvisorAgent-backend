import requests
from django.conf import settings
from django.utils import timezone
from datetime import datetime

from .constants import (
    STATIC_WEATHER,
    DEFAULT_SOIL,
    DEFAULT_CROP_HEALTH,
    MARKET_DATA,
    PEST_RULES,
    WATER_USAGE_FACTORS,
    GROWTH_STAGES,
    DEFAULT_GROWTH_STAGE,
)


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
    data = {"field_id": field_id, **DEFAULT_CROP_HEALTH}

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
    Get real USDA SSURGO soil profile by coordinates.
    Falls back to DB cache, then static defaults.
    """
    from agent.models import SoilProfile

    # Check DB cache first
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
                "data_source": "cached",
            }
        except SoilProfile.DoesNotExist:
            pass

    # Try USDA SSURGO API
    if field:
        usda_data = _fetch_usda_soil(field.lat, field.lng)
        if usda_data:
            data = {
                "field_id": field_id,
                "soil_type": usda_data["soil_type"],
                "ph": usda_data["ph"],
                "organic_matter_pct": usda_data["organic_matter_pct"],
                "drainage_class": usda_data["drainage_class"],
                "water_holding_capacity": usda_data["water_holding_capacity"],
                "available_water_in_per_ft": usda_data["available_water_in_per_ft"],
                "data_source": "USDA SSURGO",
                "component_name": usda_data.get("component_name", ""),
                "component_pct": usda_data.get("component_pct", 0),
            }

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

    # Fallback static data
    data = {"field_id": field_id, **DEFAULT_SOIL, "data_source": "default"}

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


def _fetch_usda_soil(lat: float, lng: float) -> dict | None:
    """
    Query USDA Soil Data Access (SSURGO) for real soil properties at coordinates.
    Two-step: find mukey from coords, then query soil properties.
    Returns None on failure.
    """
    buf = 0.005  # ~500m buffer around point
    wkt = (
        f"polygon(("
        f"{lng - buf} {lat - buf}, "
        f"{lng - buf} {lat + buf}, "
        f"{lng + buf} {lat + buf}, "
        f"{lng + buf} {lat - buf}, "
        f"{lng - buf} {lat - buf}"
        f"))"
    )
    sda_url = "https://SDMDataAccess.sc.egov.usda.gov/Tabular/post.rest"

    try:
        # Step 1: Get mukey from coordinates
        q1 = f"SELECT TOP 1 mukey FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('{wkt}')"
        r1 = requests.post(sda_url, data={"query": q1, "format": "json"}, timeout=15)
        r1.raise_for_status()
        mukeys = r1.json().get("Table", [])
        if not mukeys:
            return None
        mukey = mukeys[0][0]

        # Step 2: Get soil properties
        # Columns: muname, compname, comppct_r, drainagecl, hzdept_r, ph, om, awc, wthirdbar
        q2 = f"""
        SELECT TOP 1
            mu.muname, c.compname, c.comppct_r, c.drainagecl,
            ch.hzdept_r, ch.ph1to1h2o_r, ch.om_r, ch.awc_r, ch.wthirdbar_r
        FROM mapunit AS mu
        INNER JOIN component AS c ON c.mukey = mu.mukey
        INNER JOIN chorizon AS ch ON ch.cokey = c.cokey
        WHERE mu.mukey = '{mukey}'
          AND c.comppct_r IS NOT NULL
          AND ch.hzdept_r = 0
        ORDER BY c.comppct_r DESC
        """
        r2 = requests.post(sda_url, data={"query": q2, "format": "json"}, timeout=15)
        r2.raise_for_status()
        rows = r2.json().get("Table", [])
        if not rows:
            return None

        # Response is array: [muname, compname, comppct_r, drainagecl, hzdept_r, ph, om, awc, wthirdbar]
        row = rows[0]
        soil_name = row[0] or row[1] or "Unknown"
        comp_name = row[1] or ""
        comp_pct = _safe_float(row[2], 0)
        drainage = row[3] or "Unknown"
        ph = _safe_float(row[5], 7.0)
        om = _safe_float(row[6], 1.0)
        awc = _safe_float(row[7], 0.1)
        whc_raw = _safe_float(row[8], 15)

        # wthirdbar is water content at 1/3 bar (percent by weight)
        if whc_raw >= 25:
            whc_label = "high"
        elif whc_raw >= 15:
            whc_label = "moderate"
        else:
            whc_label = "low"

        # Available water in inches per foot
        awc_in_per_ft = round(awc * 12, 1)

        return {
            "soil_type": soil_name,
            "ph": round(ph, 1),
            "organic_matter_pct": round(om, 1),
            "drainage_class": drainage,
            "water_holding_capacity": whc_label,
            "available_water_in_per_ft": awc_in_per_ft,
            "component_name": comp_name,
            "component_pct": comp_pct,
        }

    except Exception:
        return None


def _safe_float(val, default: float) -> float:
    """Safely parse a value to float."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# ──────────────────────────────────────────────────────────
# NEW TOOLS
# ──────────────────────────────────────────────────────────


def get_market_prices(crop_type: str, field=None, session=None) -> dict:
    """
    Get current commodity market prices from USDA NASS QuickStats API.
    Falls back to static data if API is unavailable.
    """
    from agent.models import MarketSnapshot

    # Try live USDA NASS data first
    nass_data = _fetch_nass_price(crop_type)

    if nass_data:
        data = {
            "crop_type": crop_type,
            "price_per_unit": nass_data["price"],
            "unit": nass_data["unit"],
            "trend_30d": nass_data["trend_30d"],
            "seasonal_outlook": nass_data["outlook"],
            "data_source": "USDA NASS",
            "period": nass_data.get("period", ""),
        }
    else:
        key = crop_type.lower().strip()
        info = MARKET_DATA.get(key, MARKET_DATA["other"])
        data = {
            "crop_type": crop_type,
            "price_per_unit": info["price"],
            "unit": info["unit"],
            "trend_30d": info["trend_30d"],
            "seasonal_outlook": info["outlook"],
            "data_source": "estimated",
        }

    if field and session:
        MarketSnapshot.objects.create(
            field=field,
            session=session,
            crop_type=crop_type,
            price_per_unit=data["price_per_unit"],
            unit=data["unit"],
            trend_30d=data["trend_30d"],
            seasonal_outlook=data["seasonal_outlook"],
        )

    return data


# NASS API crop mapping: our crop_type → NASS commodity + description filter
NASS_CROP_MAP = {
    "cotton":     {"commodity": "COTTON",  "filter": "COTTON - PRICE RECEIVED, MEASURED IN $ / LB"},
    "citrus":     {"commodity": "ORANGES", "filter": "ORANGES - PRICE RECEIVED"},
    "alfalfa":    {"commodity": "HAY",     "filter": "HAY, ALFALFA - PRICE RECEIVED"},
    "corn":       {"commodity": "CORN",    "filter": "CORN, GRAIN - PRICE RECEIVED, MEASURED IN $ / BU"},
    "wheat":      {"commodity": "WHEAT",   "filter": "WHEAT - PRICE RECEIVED, MEASURED IN $ / BU"},
    "soybean":    {"commodity": "SOYBEANS","filter": "SOYBEANS - PRICE RECEIVED, MEASURED IN $ / BU"},
}


def _fetch_nass_price(crop_type: str) -> dict | None:
    """Fetch latest commodity price from USDA NASS QuickStats API."""
    api_key = settings.USDA_NASS_API_KEY
    if not api_key:
        return None

    key = crop_type.lower().strip()
    mapping = NASS_CROP_MAP.get(key)
    if not mapping:
        return None

    try:
        resp = requests.get(
            "https://quickstats.nass.usda.gov/api/api_GET/",
            params={
                "key": api_key,
                "commodity_desc": mapping["commodity"],
                "statisticcat_desc": "PRICE RECEIVED",
                "agg_level_desc": "NATIONAL",
                "year__GE": "2025",
                "format": "json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        rows = resp.json().get("data", [])
        if not rows:
            return None

        # Find rows matching our filter
        matching = [r for r in rows if mapping["filter"] in r.get("short_desc", "")]
        if not matching:
            matching = rows

        # Sort by year descending, pick latest
        matching.sort(key=lambda r: (r.get("year", ""), r.get("reference_period_desc", "")), reverse=True)
        latest = matching[0]

        price = _safe_float(latest.get("Value", "").replace(",", ""), 0)
        if price <= 0:
            return None

        # Parse unit from unit_desc (e.g., "$ / LB" → "lb")
        unit_raw = latest.get("unit_desc", "")
        unit = unit_raw.replace("$ / ", "").replace("$", "").strip().lower()
        if "bu" in unit:
            unit = "bushel"
        elif "ton" in unit:
            unit = "ton"
        elif "lb" in unit:
            unit = "lb"
        elif "box" in unit:
            unit = "box"
        elif "cwt" in unit:
            unit = "cwt"

        period = f"{latest.get('year', '')} {latest.get('reference_period_desc', '')}".strip()

        # Try to compute trend from two most recent data points
        trend = "stable"
        if len(matching) >= 2:
            prev_price = _safe_float(matching[1].get("Value", "").replace(",", ""), 0)
            if prev_price > 0:
                change_pct = ((price - prev_price) / prev_price) * 100
                if change_pct > 2:
                    trend = f"up_{abs(change_pct):.0f}pct"
                elif change_pct < -2:
                    trend = f"down_{abs(change_pct):.0f}pct"

        # Build outlook from NASS data
        outlook = f"USDA reported price: ${price:.2f}/{unit} for {period}."

        return {
            "price": price,
            "unit": unit,
            "trend_30d": trend,
            "outlook": outlook,
            "period": period,
        }

    except Exception:
        return None


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


def get_water_usage(field_id: str, field=None, session=None, weather_data=None, soil_data=None) -> dict:
    """
    Calculate irrigation water needs using NASA POWER evapotranspiration data.
    Uses FAO Penman-Monteith reference ET₀ with crop coefficients.
    Falls back to temperature-based estimation if NASA POWER is unavailable.
    """
    from agent.models import WaterUsageEstimate
    import math

    crop_type = field.crop_type.lower() if field else "cotton"
    area = field.area_acres if field else 40
    factors = WATER_USAGE_FACTORS.get(crop_type, WATER_USAGE_FACTORS["cotton"])

    # Try NASA POWER for real ET₀ data
    nasa_data = None
    et0_mm = None
    data_source = "estimated"
    if field:
        nasa_data = _fetch_nasa_power(field.lat, field.lng)

    if nasa_data:
        data_source = "NASA POWER"
        # Calculate ET₀ using simplified Penman-Monteith from NASA POWER data
        et0_mm = _calc_et0(nasa_data)
        if et0_mm:
            # Crop water need = ET₀ × crop coefficient
            etc_mm = et0_mm * factors["kc"]
            # Convert mm/day to gallons/acre/day (1 mm/acre = 27,154 gal)
            daily_need_per_acre = etc_mm * 27154 / 25.4  # mm → inches → gal/acre
            daily_need_total = daily_need_per_acre * area
        else:
            data_source = "estimated"

    if not et0_mm:
        # Fallback: temperature-based estimation
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

    # Adjust deficit for recent precipitation (from weather data or NASA)
    recent_precip_mm = 0
    if nasa_data and "precip_7d_mm" in nasa_data:
        recent_precip_mm = nasa_data["precip_7d_mm"]
    elif weather_data and weather_data.get("precipitation_forecast"):
        upcoming_rain_in = sum(
            d.get("precip_in", 0) for d in weather_data["precipitation_forecast"][:3]
        )
        recent_precip_mm = upcoming_rain_in * 25.4

    if recent_precip_mm > 10:
        deficit_pct = max(10, deficit_pct - 30)
    elif recent_precip_mm > 5:
        deficit_pct = max(15, deficit_pct - 15)

    # Cost estimate (Arizona water prices ~$85 per acre-foot)
    acre_feet_needed = (daily_need_total * deficit_pct / 100) / 325851
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
        "data_source": data_source,
    }

    # Add NASA POWER specifics if available
    if nasa_data and et0_mm:
        data["et0_mm_per_day"] = round(et0_mm, 2)
        data["etc_mm_per_day"] = round(et0_mm * factors["kc"], 2)
        data["crop_coefficient"] = factors["kc"]
        data["solar_radiation_mj"] = nasa_data.get("solar_avg", 0)
        data["recent_precip_mm"] = round(recent_precip_mm, 1)

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


def _fetch_nasa_power(lat: float, lng: float) -> dict | None:
    """
    Fetch recent agro-climate data from NASA POWER API.
    Returns temperature, solar radiation, precipitation, wind, humidity for ET₀ calculation.
    """
    from datetime import timedelta

    today = datetime.now()
    # NASA POWER data has ~2 day lag, fetch last 10 days
    end_date = (today - timedelta(days=2)).strftime("%Y%m%d")
    start_date = (today - timedelta(days=9)).strftime("%Y%m%d")

    params = {
        "start": start_date,
        "end": end_date,
        "latitude": lat,
        "longitude": lng,
        "community": "ag",
        "parameters": "T2M,T2M_MAX,T2M_MIN,ALLSKY_SFC_SW_DWN,PRECTOTCORR,WS2M,RH2M",
        "format": "json",
    }

    try:
        resp = requests.get(
            "https://power.larc.nasa.gov/api/temporal/daily/point",
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()

        props = result.get("properties", {}).get("parameter", {})
        if not props:
            return None

        # Get averages of recent data (skip -999 fill values)
        def avg(param_data):
            vals = [v for v in param_data.values() if v is not None and v > -900]
            return sum(vals) / len(vals) if vals else None

        def total(param_data):
            vals = [v for v in param_data.values() if v is not None and v > -900]
            return sum(vals) if vals else 0

        t_mean = avg(props.get("T2M", {}))
        t_max = avg(props.get("T2M_MAX", {}))
        t_min = avg(props.get("T2M_MIN", {}))
        solar = avg(props.get("ALLSKY_SFC_SW_DWN", {}))
        wind = avg(props.get("WS2M", {}))
        rh = avg(props.get("RH2M", {}))
        precip_7d = total(props.get("PRECTOTCORR", {}))

        if t_mean is None or solar is None:
            return None

        return {
            "t_mean_c": round(t_mean, 1),
            "t_max_c": round(t_max, 1) if t_max else None,
            "t_min_c": round(t_min, 1) if t_min else None,
            "solar_avg": round(solar, 2),
            "wind_ms": round(wind, 1) if wind else 2.0,
            "rh_pct": round(rh, 0) if rh else 40,
            "precip_7d_mm": round(precip_7d, 1),
        }

    except Exception:
        return None


def _calc_et0(nasa: dict) -> float | None:
    """
    Simplified FAO Penman-Monteith ET₀ calculation.
    Uses NASA POWER data: solar radiation, temperature, wind, humidity.
    Returns reference evapotranspiration in mm/day.
    """
    import math

    t_mean = nasa.get("t_mean_c")
    t_max = nasa.get("t_max_c")
    t_min = nasa.get("t_min_c")
    rs = nasa.get("solar_avg")  # MJ/m²/day
    wind = nasa.get("wind_ms", 2.0)
    rh = nasa.get("rh_pct", 40)

    if t_mean is None or rs is None:
        return None

    if t_max is None:
        t_max = t_mean + 5
    if t_min is None:
        t_min = t_mean - 5

    # Saturation vapor pressure (kPa)
    e_tmax = 0.6108 * math.exp(17.27 * t_max / (t_max + 237.3))
    e_tmin = 0.6108 * math.exp(17.27 * t_min / (t_min + 237.3))
    es = (e_tmax + e_tmin) / 2

    # Actual vapor pressure from relative humidity
    ea = es * rh / 100

    # Slope of vapor pressure curve
    delta = 4098 * 0.6108 * math.exp(17.27 * t_mean / (t_mean + 237.3)) / (t_mean + 237.3) ** 2

    # Psychrometric constant (assume ~101.3 kPa atmospheric pressure)
    gamma = 0.0665

    # Net radiation (simplified: assume Rn ≈ 0.77 * Rs for arid regions)
    rn = 0.77 * rs

    # FAO Penman-Monteith (simplified daily)
    numerator = 0.408 * delta * rn + gamma * (900 / (t_mean + 273)) * wind * (es - ea)
    denominator = delta + gamma * (1 + 0.34 * wind)

    et0 = numerator / denominator

    return max(0, round(et0, 2))

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
    return dict(STATIC_WEATHER)

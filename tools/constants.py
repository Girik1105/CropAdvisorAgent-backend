"""
Static reference data for CropAdvisor tools.

All hard-coded agricultural data lives here so services.py
stays focused on logic and API calls.
"""

# ──────────────────────────────────────────────────────────
# Fallback weather (Casa Grande, AZ — used when OpenWeatherMap is unavailable)
# ──────────────────────────────────────────────────────────

STATIC_WEATHER = {
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

# ──────────────────────────────────────────────────────────
# Default soil profile (used when USDA SSURGO API is unavailable)
# ──────────────────────────────────────────────────────────

DEFAULT_SOIL = {
    "soil_type": "Casa Grande sandy loam",
    "ph": 7.8,
    "organic_matter_pct": 1.2,
    "drainage_class": "well-drained",
    "water_holding_capacity": "low",
    "available_water_in_per_ft": 1.1,
}

# ──────────────────────────────────────────────────────────
# Default crop health (used when no CropHealthRecord exists)
# ──────────────────────────────────────────────────────────

DEFAULT_CROP_HEALTH = {
    "ndvi_score": 0.42,
    "stress_level": "moderate",
    "vegetation_trend": "declining",
    "last_satellite_date": "2026-04-03T14:30:00Z",
    "vegetation_fraction": 0.58,
}

# ──────────────────────────────────────────────────────────
# Commodity market prices (USDA/exchange representative values)
# ──────────────────────────────────────────────────────────

MARKET_DATA = {
    "cotton": {
        "price": 0.82, "unit": "lb", "trend_30d": "stable",
        "outlook": "Prices expected to hold through summer. Upland cotton futures steady around 80-85 cents.",
    },
    "citrus": {
        "price": 28.50, "unit": "box", "trend_30d": "up_5pct",
        "outlook": "Strong demand driven by juice market. Prices rising due to limited Florida supply.",
    },
    "alfalfa": {
        "price": 225.0, "unit": "ton", "trend_30d": "down_3pct",
        "outlook": "Oversupply in the Southwest. Expect continued softness through Q2.",
    },
    "corn": {
        "price": 4.45, "unit": "bushel", "trend_30d": "up_2pct",
        "outlook": "Drought concerns in the Midwest supporting prices. Export demand steady.",
    },
    "wheat": {
        "price": 5.80, "unit": "bushel", "trend_30d": "down_1pct",
        "outlook": "Large global stocks keeping downward pressure. Winter wheat crop in good condition.",
    },
    "soybean": {
        "price": 11.20, "unit": "bushel", "trend_30d": "up_3pct",
        "outlook": "South American crop shortfall boosting prices. Strong crush margins.",
    },
    "vegetables": {
        "price": 18.00, "unit": "cwt", "trend_30d": "stable",
        "outlook": "Seasonal produce prices normal for spring. Desert growing season winding down.",
    },
    "other": {
        "price": 0.0, "unit": "unit", "trend_30d": "unknown",
        "outlook": "No market data available for this crop type.",
    },
}

# ──────────────────────────────────────────────────────────
# Pest & disease rule definitions
# Each rule has a condition lambda(temp_f, humidity_pct, crop_type),
# a risk level, threat list, and action list.
# ──────────────────────────────────────────────────────────

PEST_RULES = [
    {
        "condition": lambda t, h, crop: h > 60 and t > 75,
        "risk_level": "high",
        "threats": [
            "Fungal diseases (powdery mildew, downy mildew)",
            "Root rot",
            "Bacterial leaf blight",
        ],
        "actions": [
            "Apply preventive fungicide",
            "Improve air circulation between rows",
            "Avoid overhead irrigation",
        ],
    },
    {
        "condition": lambda t, h, crop: h < 20 and t > 95,
        "risk_level": "high",
        "threats": ["Spider mites", "Thrips", "Heat stress damage"],
        "actions": [
            "Scout for mite webbing on leaf undersides",
            "Consider miticide if >20% leaf damage",
            "Increase irrigation frequency",
        ],
    },
    {
        "condition": lambda t, h, crop: 60 <= t <= 85 and 30 <= h <= 60,
        "risk_level": "moderate",
        "threats": [
            "Aphids (spring migration)",
            "Whiteflies",
            "Leafhopper damage",
        ],
        "actions": [
            "Monitor sticky traps weekly",
            "Release beneficial insects (lacewings, ladybugs)",
            "Spot-treat if threshold exceeded",
        ],
    },
    {
        "condition": lambda t, h, crop: crop.lower() == "cotton" and t > 90,
        "risk_level": "moderate",
        "threats": [
            "Cotton bollworm (Helicoverpa)",
            "Lygus bug",
            "Aphid colonies",
        ],
        "actions": [
            "Scout bolls for entry holes",
            "Check for square shedding",
            "Consider BT spray if >8% boll damage",
        ],
    },
    {
        "condition": lambda t, h, crop: crop.lower() == "citrus",
        "risk_level": "moderate",
        "threats": [
            "Citrus leafminer",
            "Asian citrus psyllid",
            "Citrus canker",
        ],
        "actions": [
            "Inspect new growth flushes",
            "Apply systemic insecticide if psyllid detected",
            "Remove infected material",
        ],
    },
]

# ──────────────────────────────────────────────────────────
# FAO crop coefficients & peak water demand
# kc = crop coefficient for ET₀ → ETc conversion
# peak_gal_per_acre_day = fallback when NASA POWER is unavailable
# ──────────────────────────────────────────────────────────

WATER_USAGE_FACTORS = {
    "cotton":     {"peak_gal_per_acre_day": 5400, "kc": 1.15},
    "citrus":     {"peak_gal_per_acre_day": 4800, "kc": 0.85},
    "alfalfa":    {"peak_gal_per_acre_day": 7200, "kc": 1.20},
    "corn":       {"peak_gal_per_acre_day": 6000, "kc": 1.20},
    "wheat":      {"peak_gal_per_acre_day": 3600, "kc": 0.95},
    "soybean":    {"peak_gal_per_acre_day": 5000, "kc": 1.10},
    "vegetables": {"peak_gal_per_acre_day": 4200, "kc": 1.00},
}

# ──────────────────────────────────────────────────────────
# Growth stage calendars by crop and month (1-12)
# ──────────────────────────────────────────────────────────

GROWTH_STAGES = {
    "cotton": {
        1:  {"stage": "Dormant",                    "tips": "Plan seed orders and equipment maintenance.",                                           "watch_for": "Nothing active."},
        2:  {"stage": "Pre-planting",               "tips": "Soil preparation, pre-irrigation if needed.",                                           "watch_for": "Soil temperature — need 65°F+ for planting."},
        3:  {"stage": "Pre-planting",               "tips": "Final field prep, herbicide application.",                                              "watch_for": "Soil moisture levels for planting."},
        4:  {"stage": "Planting / Emergence",       "tips": "Plant when soil temp stable above 65°F. Ensure good seed-to-soil contact.",             "watch_for": "Seedling diseases, thrips damage on cotyledons."},
        5:  {"stage": "Seedling / Squaring",        "tips": "First irrigation 3-4 weeks after emergence. Scout weekly.",                             "watch_for": "Aphids, thrips, early square set."},
        6:  {"stage": "Squaring / Early Bloom",     "tips": "Peak water demand begins. Maintain 4-day irrigation cycle.",                            "watch_for": "Lygus bug, bollworm eggs, square retention rate."},
        7:  {"stage": "Peak Bloom",                 "tips": "Maximum water and nutrient demand. Apply final nitrogen.",                              "watch_for": "Bollworm, heat stress above 110°F, boll rot."},
        8:  {"stage": "Boll Development",           "tips": "Maintain irrigation but prepare to cut off.",                                           "watch_for": "Boll rot, stink bugs, premature opening."},
        9:  {"stage": "Boll Opening / Defoliation", "tips": "Apply defoliant when 60%+ bolls open. Schedule harvest.",                               "watch_for": "Regrowth, weather delays for defoliation."},
        10: {"stage": "Harvest",                    "tips": "Harvest when 80%+ bolls open. Gin within 30 days.",                                     "watch_for": "Rain damage, bark contamination."},
        11: {"stage": "Post-harvest",               "tips": "Stalk destruction, soil sampling.",                                                     "watch_for": "Overwintering pest sites."},
        12: {"stage": "Dormant",                    "tips": "Equipment maintenance, record keeping.",                                                "watch_for": "Plan next season."},
    },
    "citrus": {
        1:  {"stage": "Winter dormancy",                "tips": "Minimal irrigation. Prune dead wood.",                                   "watch_for": "Frost damage below 28°F."},
        2:  {"stage": "Pre-bloom",                      "tips": "Apply pre-bloom fertilizer (nitrogen + micronutrients).",                "watch_for": "Scale insects, begin psyllid monitoring."},
        3:  {"stage": "Bloom",                          "tips": "Ensure adequate irrigation. Avoid disturbing pollinators.",              "watch_for": "Citrus flower moth, frost risk on blossoms."},
        4:  {"stage": "Fruit set / Early development",  "tips": "Post-bloom irrigation critical. Apply micronutrients.",                 "watch_for": "June drop, leafminer on new flush."},
        5:  {"stage": "Fruit development",              "tips": "Consistent irrigation schedule. Monitor fruit size.",                   "watch_for": "Mites, scale, fruit splitting from irregular watering."},
        6:  {"stage": "Fruit development",              "tips": "Peak water demand. Mulch to conserve moisture.",                        "watch_for": "Heat stress, sunburn on fruit."},
        7:  {"stage": "Summer growth flush",            "tips": "Monitor for Asian citrus psyllid on new growth.",                       "watch_for": "Psyllid, leafminer, summer mites."},
        8:  {"stage": "Fruit sizing",                   "tips": "Maintain irrigation. Apply potassium for fruit quality.",               "watch_for": "Fruit fly, Alternaria brown spot."},
        9:  {"stage": "Color break",                    "tips": "Reduce irrigation slightly to improve sugar content.",                  "watch_for": "Split fruit, Mediterranean fruit fly."},
        10: {"stage": "Maturation",                     "tips": "Begin harvest when Brix:acid ratio is optimal.",                        "watch_for": "Post-harvest decay, cold front timing."},
        11: {"stage": "Harvest",                        "tips": "Pick carefully to avoid rind damage.",                                  "watch_for": "Decay pressure, frost risk."},
        12: {"stage": "Post-harvest / Dormancy",        "tips": "Apply post-harvest fungicide. Light pruning.",                          "watch_for": "Freeze protection below 28°F."},
    },
    "alfalfa": {
        1:  {"stage": "Winter dormancy",                  "tips": "Minimal activity. Plan spring fertilization.",                                  "watch_for": "Weevil overwintering sites."},
        2:  {"stage": "Early green-up",                   "tips": "Apply early-season irrigation if soil dry.",                                    "watch_for": "Alfalfa weevil larvae in stem tips."},
        3:  {"stage": "Active growth — Cut 1 approaching","tips": "Scout for weevils. Irrigate to support rapid growth.",                          "watch_for": "Weevil feeding >30% damage = treat before cut."},
        4:  {"stage": "First cutting",                    "tips": "Cut at 10% bloom or 28-day intervals. Irrigate immediately after.",             "watch_for": "Rain delays, windrow drying time."},
        5:  {"stage": "Regrowth / Cut 2",                 "tips": "Irrigate 3-5 days after cutting. Scout for aphids.",                            "watch_for": "Blue alfalfa aphid, pea aphid."},
        6:  {"stage": "Peak production — Cut 3",          "tips": "Maximum water demand. 4-day irrigation cycle.",                                 "watch_for": "Leafhopper, spider mites in hot weather."},
        7:  {"stage": "Summer cuts (4-5)",                "tips": "Cut every 25-28 days. Monitor for heat stress.",                                "watch_for": "Armyworm, webworm, summer slump."},
        8:  {"stage": "Late summer cutting",              "tips": "Continue 28-day cycle. Quality may decline in heat.",                            "watch_for": "Spider mites, whitefly."},
        9:  {"stage": "Fall cuts",                        "tips": "Last cut by mid-September to allow winter hardening.",                           "watch_for": "Stand thinning, crown health."},
        10: {"stage": "Final harvest window",             "tips": "Stop cutting 4-6 weeks before first frost.",                                    "watch_for": "Fall armyworm, late-season weeds."},
        11: {"stage": "Fall dormancy",                    "tips": "Light irrigation to maintain root reserves.",                                   "watch_for": "Winter weed establishment."},
        12: {"stage": "Dormant",                          "tips": "Evaluate stand density. Plan renovations if needed.",                            "watch_for": "Gopher damage, crown rot."},
    },
}

DEFAULT_GROWTH_STAGE = {
    "stage": "Active growth",
    "tips": "Follow standard agronomic practices for your crop and region.",
    "watch_for": "Monitor for pests, diseases, and nutrient deficiencies.",
}

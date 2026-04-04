"""
Soil data tool - USDA soil profile information.

For hackathon: Uses static soil data based on field coordinates.
Production: Would integrate with USDA Web Soil Survey API.
"""

from datetime import datetime
from typing import Dict, Any
from agent.models import Field


def get_soil_data(field_id: str) -> Dict[str, Any]:
    """
    Get USDA soil profile data for a field.

    Args:
        field_id: UUID of the registered field

    Returns:
        Soil profile data formatted for agent consumption
    """
    try:
        field = Field.objects.get(id=field_id)
    except Field.DoesNotExist:
        raise Exception(f"Field {field_id} not found")

    # Get soil profile based on field location
    soil_profile = _get_soil_profile_for_location(field.lat, field.lng)

    return {
        'field_id': field_id,
        'soil_type': soil_profile['soil_type'],
        'ph': soil_profile['ph'],
        'organic_matter_pct': soil_profile['organic_matter_pct'],
        'drainage_class': soil_profile['drainage_class'],
        'water_holding_capacity': soil_profile['water_holding_capacity'],
        'available_water_in_per_ft': soil_profile['available_water_in_per_ft'],
        'source': 'usda_web_soil_survey',
        'fetched_at': datetime.utcnow().isoformat() + 'Z'
    }


def _get_soil_profile_for_location(lat: float, lng: float) -> Dict[str, Any]:
    """
    Get soil profile data based on geographic coordinates.

    Uses regional soil type mapping for Arizona agricultural areas.
    """

    # Casa Grande, AZ area (32.87, -111.75) - cotton demo scenario
    if _is_casa_grande_area(lat, lng):
        return {
            'soil_type': 'sandy_loam',
            'ph': 7.8,
            'organic_matter_pct': 1.2,
            'drainage_class': 'well_drained',
            'water_holding_capacity': 'low',
            'available_water_in_per_ft': 1.4
        }

    # Phoenix/Salt River Valley area (irrigated agriculture)
    elif _is_phoenix_valley(lat, lng):
        return {
            'soil_type': 'clay_loam',
            'ph': 7.5,
            'organic_matter_pct': 1.8,
            'drainage_class': 'moderately_well_drained',
            'water_holding_capacity': 'moderate',
            'available_water_in_per_ft': 2.1
        }

    # Yuma area (intensive irrigation, citrus/vegetables)
    elif _is_yuma_area(lat, lng):
        return {
            'soil_type': 'silty_clay',
            'ph': 8.1,
            'organic_matter_pct': 0.9,
            'drainage_class': 'poorly_drained',
            'water_holding_capacity': 'high',
            'available_water_in_per_ft': 2.8
        }

    # Default Arizona desert agricultural soil
    else:
        return {
            'soil_type': 'sandy_loam',
            'ph': 7.9,
            'organic_matter_pct': 1.0,
            'drainage_class': 'well_drained',
            'water_holding_capacity': 'low',
            'available_water_in_per_ft': 1.3
        }


def _is_casa_grande_area(lat: float, lng: float) -> bool:
    """Check if coordinates are in Casa Grande area."""
    # Casa Grande: ~32.87°N, 111.75°W
    return (32.7 <= lat <= 33.0) and (-112.0 <= lng <= -111.5)


def _is_phoenix_valley(lat: float, lng: float) -> bool:
    """Check if coordinates are in Phoenix/Salt River Valley."""
    # Phoenix metro agricultural areas
    return (33.2 <= lat <= 33.8) and (-112.5 <= lng <= -111.5)


def _is_yuma_area(lat: float, lng: float) -> bool:
    """Check if coordinates are in Yuma agricultural area."""
    # Yuma County agricultural region
    return (32.4 <= lat <= 32.9) and (-114.8 <= lng <= -114.0)


def get_soil_irrigation_characteristics(soil_type: str) -> Dict[str, Any]:
    """
    Get irrigation-specific characteristics for soil types.
    Used by cost estimation algorithms.
    """

    characteristics = {
        'sandy_loam': {
            'infiltration_rate': 'high',  # Water soaks in quickly
            'retention': 'low',           # Doesn't hold water long
            'irrigation_frequency': 'frequent',  # Need to water more often
            'application_rate': 'moderate'       # Medium application amounts
        },
        'clay_loam': {
            'infiltration_rate': 'moderate',
            'retention': 'high',
            'irrigation_frequency': 'moderate',
            'application_rate': 'high'
        },
        'silty_clay': {
            'infiltration_rate': 'slow',
            'retention': 'very_high',
            'irrigation_frequency': 'infrequent',
            'application_rate': 'low'
        }
    }

    return characteristics.get(soil_type, characteristics['sandy_loam'])
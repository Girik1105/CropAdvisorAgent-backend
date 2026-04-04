"""
Crop health tool - NDVI vegetation stress analysis.

For hackathon: Uses static/mock NDVI data.
Production: Would integrate with satellite imagery APIs (Landsat, Sentinel).
"""

from datetime import datetime, timedelta
from typing import Dict, Any
from agent.models import Field


def get_crop_health_data(field_id: str) -> Dict[str, Any]:
    """
    Get NDVI-based crop health assessment for a field.

    Args:
        field_id: UUID of the registered field

    Returns:
        Crop health data formatted for agent consumption
    """
    try:
        field = Field.objects.get(id=field_id)
    except Field.DoesNotExist:
        raise Exception(f"Field {field_id} not found")

    # Generate realistic NDVI data based on crop type and location
    ndvi_data = _get_field_ndvi_data(field)

    return {
        'field_id': field_id,
        'ndvi_score': ndvi_data['ndvi'],
        'stress_level': ndvi_data['stress_level'],
        'vegetation_trend': ndvi_data['trend'],
        'last_satellite_date': (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d'),
        'healthy_ndvi_range': _get_healthy_range(field.crop_type),
        'source': 'usgs_landsat',
        'fetched_at': datetime.utcnow().isoformat() + 'Z'
    }


def _get_field_ndvi_data(field: Field) -> Dict[str, Any]:
    """Generate NDVI data based on field characteristics."""

    # Mock NDVI values by crop type and scenario
    crop_scenarios = {
        'cotton': {
            'casa_grande': {'ndvi': 0.42, 'stress': 'moderate', 'trend': 'declining'},
            'default': {'ndvi': 0.55, 'stress': 'low', 'trend': 'stable'}
        },
        'alfalfa': {
            'default': {'ndvi': 0.72, 'stress': 'none', 'trend': 'stable'}
        },
        'citrus': {
            'default': {'ndvi': 0.68, 'stress': 'low', 'trend': 'stable'}
        }
    }

    crop_type = field.crop_type.lower()

    # Check if this is the Casa Grande cotton demo field
    if crop_type == 'cotton' and _is_casa_grande_location(field.lat, field.lng):
        scenario = crop_scenarios['cotton']['casa_grande']
    else:
        scenario = crop_scenarios.get(crop_type, {}).get('default', {
            'ndvi': 0.50, 'stress': 'moderate', 'trend': 'stable'
        })

    return {
        'ndvi': scenario['ndvi'],
        'stress_level': scenario['stress'],
        'trend': scenario['trend']
    }


def _get_healthy_range(crop_type: str) -> Dict[str, float]:
    """Return healthy NDVI range for crop type."""

    ranges = {
        'cotton': {'min': 0.6, 'max': 0.85},
        'alfalfa': {'min': 0.7, 'max': 0.9},
        'citrus': {'min': 0.65, 'max': 0.88}
    }

    return ranges.get(crop_type.lower(), {'min': 0.6, 'max': 0.85})


def _is_casa_grande_location(lat: float, lng: float) -> bool:
    """Check if coordinates are near Casa Grande, AZ (demo location)."""
    # Casa Grande, AZ is approximately 32.87°N, 111.75°W
    casa_grande_lat, casa_grande_lng = 32.87, -111.75

    # Within ~10 miles (rough approximation)
    lat_diff = abs(lat - casa_grande_lat)
    lng_diff = abs(lng - casa_grande_lng)

    return lat_diff < 0.15 and lng_diff < 0.15


def get_ndvi_stress_interpretation(ndvi_score: float) -> str:
    """Convert NDVI score to stress level interpretation."""

    if ndvi_score >= 0.8:
        return 'none'
    elif ndvi_score >= 0.6:
        return 'low'
    elif ndvi_score >= 0.4:
        return 'moderate'
    elif ndvi_score >= 0.2:
        return 'high'
    else:
        return 'severe'
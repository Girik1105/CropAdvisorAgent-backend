"""
Weather data tool - OpenWeatherMap integration for real-time weather.
"""

import os
import requests
from datetime import datetime
from typing import Dict, Any


def get_weather_data(lat: float, lng: float) -> Dict[str, Any]:
    """
    Fetch current weather and 7-day forecast from OpenWeatherMap.

    Args:
        lat: Latitude
        lng: Longitude

    Returns:
        Weather data formatted for agent consumption
    """
    api_key = os.environ.get('OPENWEATHERMAP_API_KEY')

    if not api_key:
        # Return mock data for development/testing
        return _get_mock_weather_data(lat, lng)

    try:
        # Current weather
        current_url = f"https://api.openweathermap.org/data/2.5/weather"
        current_params = {
            'lat': lat,
            'lon': lng,
            'appid': api_key,
            'units': 'imperial'  # Fahrenheit for US farmers
        }

        current_response = requests.get(current_url, params=current_params)
        current_response.raise_for_status()
        current_data = current_response.json()

        # 7-day forecast
        forecast_url = f"https://api.openweathermap.org/data/2.5/forecast"
        forecast_params = {
            'lat': lat,
            'lon': lng,
            'appid': api_key,
            'units': 'imperial'
        }

        forecast_response = requests.get(forecast_url, params=forecast_params)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()

        return _format_weather_response(current_data, forecast_data)

    except requests.RequestException as e:
        raise Exception(f"OpenWeatherMap API error: {str(e)}")


def _format_weather_response(current_data: Dict, forecast_data: Dict) -> Dict[str, Any]:
    """Format OpenWeatherMap response for agent consumption."""

    # Extract precipitation forecast (next 7 days)
    precipitation_forecast = []
    seen_dates = set()

    for item in forecast_data.get('list', [])[:28]:  # 7 days * 4 forecasts per day
        dt = datetime.fromtimestamp(item['dt'])
        date_str = dt.strftime('%Y-%m-%d')

        if date_str not in seen_dates:
            precip_in = item.get('rain', {}).get('3h', 0) * 0.0393701  # mm to inches
            precip_prob = item.get('pop', 0) * 100  # decimal to percentage

            precipitation_forecast.append({
                'date': date_str,
                'precip_in': round(precip_in, 2),
                'prob_pct': int(precip_prob)
            })
            seen_dates.add(date_str)

        if len(precipitation_forecast) >= 7:
            break

    return {
        'temp_f': int(current_data['main']['temp']),
        'temp_c': round((current_data['main']['temp'] - 32) * 5/9, 1),
        'humidity_pct': current_data['main']['humidity'],
        'wind_mph': round(current_data['wind']['speed'], 1),
        'conditions': current_data['weather'][0]['description'].title(),
        'uv_index': current_data.get('uvi', 0),  # May not be available
        'precipitation_forecast': precipitation_forecast,
        'source': 'openweathermap',
        'fetched_at': datetime.utcnow().isoformat() + 'Z'
    }


def _get_mock_weather_data(lat: float, lng: float) -> Dict[str, Any]:
    """Return mock weather data for Casa Grande, AZ (demo scenario)."""

    return {
        'temp_f': 105,
        'temp_c': 40.6,
        'humidity_pct': 12,
        'wind_mph': 8.2,
        'conditions': 'Clear',
        'uv_index': 11,
        'precipitation_forecast': [
            {'date': '2026-04-04', 'precip_in': 0.0, 'prob_pct': 5},
            {'date': '2026-04-05', 'precip_in': 0.0, 'prob_pct': 3},
            {'date': '2026-04-06', 'precip_in': 0.0, 'prob_pct': 8},
            {'date': '2026-04-07', 'precip_in': 0.0, 'prob_pct': 2},
            {'date': '2026-04-08', 'precip_in': 0.0, 'prob_pct': 4},
            {'date': '2026-04-09', 'precip_in': 0.0, 'prob_pct': 6},
            {'date': '2026-04-10', 'precip_in': 0.0, 'prob_pct': 3}
        ],
        'source': 'mock_data',
        'fetched_at': datetime.utcnow().isoformat() + 'Z'
    }
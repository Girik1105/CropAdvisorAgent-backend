"""
Management command to seed the database with demo data and optionally run the agent.

Usage:
    python manage.py seed_demo                # Seed data only
    python manage.py seed_demo --run-agent    # Seed data + run agent pipeline
    python manage.py seed_demo --reset        # Wipe all agent data and re-seed
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from agent.models import (
    ActionRecommendation, AgentMessage, AgentSession,
    CropHealthRecord, Field, SoilProfile, WeatherSnapshot,
)

User = get_user_model()

DEMO_USER = {
    "username": "demo_farmer",
    "email": "farmer@cropadvisor.demo",
    "password": "demo1234!",
}

DEMO_FIELDS = [
    {
        "name": "North 40",
        "crop_type": "cotton",
        "lat": 32.8795,
        "lng": -111.7574,
        "area_acres": 40.0,
        "soil_type": "sandy loam",
        "owner_phone": "+16025551234",
    },
    {
        "name": "South Orchard",
        "crop_type": "citrus",
        "lat": 32.8650,
        "lng": -111.7400,
        "area_acres": 15.0,
        "soil_type": "clay loam",
        "owner_phone": "+16025551234",
    },
    {
        "name": "West Pasture",
        "crop_type": "alfalfa",
        "lat": 32.8900,
        "lng": -111.7700,
        "area_acres": 60.0,
        "soil_type": "silty clay",
        "owner_phone": "+16025551234",
    },
]

SOIL_PROFILES = {
    "North 40": {
        "soil_type": "Casa Grande sandy loam",
        "ph": 7.8,
        "organic_matter_pct": 1.2,
        "drainage_class": "well-drained",
        "water_holding_capacity": "low",
        "available_water_in_per_ft": 1.1,
    },
    "South Orchard": {
        "soil_type": "Mohall clay loam",
        "ph": 7.2,
        "organic_matter_pct": 2.4,
        "drainage_class": "moderately well-drained",
        "water_holding_capacity": "moderate",
        "available_water_in_per_ft": 1.8,
    },
    "West Pasture": {
        "soil_type": "Laveen silty clay",
        "ph": 7.5,
        "organic_matter_pct": 1.8,
        "drainage_class": "somewhat poorly drained",
        "water_holding_capacity": "high",
        "available_water_in_per_ft": 2.2,
    },
}

CROP_HEALTH_DATA = {
    "North 40": {
        "ndvi_score": 0.42,
        "stress_level": "moderate",
        "vegetation_trend": "declining",
        "vegetation_fraction": 0.58,
    },
    "South Orchard": {
        "ndvi_score": 0.71,
        "stress_level": "low",
        "vegetation_trend": "stable",
        "vegetation_fraction": 0.82,
    },
    "West Pasture": {
        "ndvi_score": 0.65,
        "stress_level": "low",
        "vegetation_trend": "improving",
        "vegetation_fraction": 0.74,
    },
}

WEATHER_SNAPSHOTS = {
    "North 40": {
        "temp_f": 105, "temp_c": 40.6, "humidity_pct": 12,
        "wind_mph": 8, "conditions": "clear sky", "uv_index": 11,
        "precipitation_forecast": [
            {"date": "2026-04-04", "precip_in": 0.0, "prob_pct": 0},
            {"date": "2026-04-05", "precip_in": 0.0, "prob_pct": 5},
            {"date": "2026-04-06", "precip_in": 0.0, "prob_pct": 0},
        ],
    },
    "South Orchard": {
        "temp_f": 98, "temp_c": 36.7, "humidity_pct": 18,
        "wind_mph": 5, "conditions": "few clouds", "uv_index": 9,
        "precipitation_forecast": [
            {"date": "2026-04-04", "precip_in": 0.0, "prob_pct": 10},
            {"date": "2026-04-05", "precip_in": 0.1, "prob_pct": 25},
            {"date": "2026-04-06", "precip_in": 0.0, "prob_pct": 5},
        ],
    },
    "West Pasture": {
        "temp_f": 102, "temp_c": 38.9, "humidity_pct": 15,
        "wind_mph": 12, "conditions": "scattered clouds", "uv_index": 10,
        "precipitation_forecast": [
            {"date": "2026-04-04", "precip_in": 0.0, "prob_pct": 0},
            {"date": "2026-04-05", "precip_in": 0.0, "prob_pct": 0},
            {"date": "2026-04-06", "precip_in": 0.2, "prob_pct": 35},
        ],
    },
}

DEMO_MESSAGES = [
    "How's my field looking?",
    "Should I irrigate this week?",
    "Any pest concerns I should know about?",
]


class Command(BaseCommand):
    help = "Seed the database with demo user, fields, and tool data. Optionally run the agent."

    def add_arguments(self, parser):
        parser.add_argument(
            "--run-agent", action="store_true",
            help="Run the agent pipeline on the first field after seeding",
        )
        parser.add_argument(
            "--reset", action="store_true",
            help="Delete all existing agent data before seeding",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self._reset()

        user = self._create_user()
        fields = self._create_fields(user)
        self._create_soil_profiles(fields)
        self._create_crop_health(fields)
        self._create_weather_snapshots(fields)

        if options["run_agent"]:
            self._run_agent(user, fields)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("--- Demo data ready ---"))
        self.stdout.write(f"  Login: username={DEMO_USER['username']} password={DEMO_USER['password']}")
        self.stdout.write(f"  Fields: {len(fields)}")
        self.stdout.write(f"  Phone: {DEMO_FIELDS[0]['owner_phone']}")

    def _reset(self):
        self.stdout.write("Resetting all agent data...")
        ActionRecommendation.objects.all().delete()
        AgentMessage.objects.all().delete()
        AgentSession.objects.all().delete()
        WeatherSnapshot.objects.all().delete()
        CropHealthRecord.objects.all().delete()
        SoilProfile.objects.all().delete()
        Field.objects.all().delete()
        User.objects.filter(username=DEMO_USER["username"]).delete()
        self.stdout.write(self.style.WARNING("  All agent data deleted."))

    def _create_user(self):
        user, created = User.objects.get_or_create(
            username=DEMO_USER["username"],
            defaults={"email": DEMO_USER["email"]},
        )
        if created:
            user.set_password(DEMO_USER["password"])
            user.save()
            self.stdout.write(self.style.SUCCESS(f"  Created user: {user.username}"))
        else:
            self.stdout.write(f"  User already exists: {user.username}")
        return user

    def _create_fields(self, user):
        fields = []
        for field_data in DEMO_FIELDS:
            field, created = Field.objects.get_or_create(
                owner=user,
                name=field_data["name"],
                defaults=field_data,
            )
            fields.append(field)
            status = "Created" if created else "Exists"
            self.stdout.write(f"  {status} field: {field.name} ({field.crop_type}, {field.area_acres} acres)")
        return fields

    def _create_soil_profiles(self, fields):
        for field in fields:
            if not SoilProfile.objects.filter(field=field).exists():
                profile_data = SOIL_PROFILES.get(field.name, SOIL_PROFILES["North 40"])
                SoilProfile.objects.create(field=field, **profile_data)
                self.stdout.write(f"  Created soil profile: {field.name} ({profile_data['soil_type']})")
            else:
                self.stdout.write(f"  Soil profile exists: {field.name}")

    def _create_crop_health(self, fields):
        for field in fields:
            if not CropHealthRecord.objects.filter(field=field).exists():
                health_data = CROP_HEALTH_DATA.get(field.name, CROP_HEALTH_DATA["North 40"])
                CropHealthRecord.objects.create(
                    field=field,
                    last_satellite_date=timezone.now(),
                    **health_data,
                )
                self.stdout.write(f"  Created crop health: {field.name} (NDVI {health_data['ndvi_score']})")
            else:
                self.stdout.write(f"  Crop health exists: {field.name}")

    def _create_weather_snapshots(self, fields):
        for field in fields:
            if not WeatherSnapshot.objects.filter(field=field).exists():
                weather_data = WEATHER_SNAPSHOTS.get(field.name, WEATHER_SNAPSHOTS["North 40"])
                WeatherSnapshot.objects.create(field=field, **weather_data)
                self.stdout.write(f"  Created weather: {field.name} ({weather_data['temp_f']}F, {weather_data['conditions']})")
            else:
                self.stdout.write(f"  Weather exists: {field.name}")

    def _run_agent(self, user, fields):
        self.stdout.write("")
        self.stdout.write("Running agent pipeline on first field...")
        field = fields[0]
        message = DEMO_MESSAGES[0]

        session = AgentSession.objects.create(
            user=user,
            field=field,
            channel="dashboard",
        )

        try:
            from agent.engine import CropAdvisorEngine
            engine = CropAdvisorEngine()
            result = engine.run(
                field_id=str(field.id),
                user_message=message,
                session_id=str(session.id),
            )
            self.stdout.write(self.style.SUCCESS(f"  Agent response: {result['response'][:120]}..."))
            self.stdout.write(f"  Action: {result['recommendation']['action_type']} ({result['recommendation']['urgency']})")
            self.stdout.write(f"  Cost: ${result['recommendation']['estimated_cost']}")
            self.stdout.write(f"  Duration: {result['total_duration_ms']}ms")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Agent failed: {e}"))
            self.stdout.write("  (This is expected if GEMINI_API_KEY is not set)")

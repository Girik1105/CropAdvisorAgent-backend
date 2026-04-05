"""
Full demo script that showcases CropAdvisor's agentic capabilities.

Runs real scenarios through the Gemini-powered agent engine to demonstrate:
- 7-tool autonomous data gathering (weather, NDVI, soil, market, pest, water, growth)
- Intent classification (action vs general Q&A)
- Multi-agent pipeline (Field Agent → Orchestrator → Recommender)
- SMS + Dashboard channels
- Cost estimation and risk quantification

Usage:
    python manage.py run_demo                  # Run all 5 scenarios
    python manage.py run_demo --scenario 1     # Run just one scenario
    python manage.py run_demo --skip-seed      # Skip seeding, use existing data
    python manage.py run_demo --reset          # Wipe + re-seed + run
"""
import time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from agent.models import (
    ActionRecommendation, AgentMessage, AgentSession,
    CropHealthRecord, Field, MarketSnapshot, PestRiskAssessment,
    SoilProfile, WaterUsageEstimate, WeatherSnapshot,
)

User = get_user_model()

# ─── Demo Data ──────────────────────────────────────────────────────

DEMO_USER = {
    "username": "demo_farmer",
    "email": "farmer@cropadvisor.demo",
    "password": "demo1234!",
    "phone": "+16025551234",
}

FIELDS = [
    {
        "name": "North 40 Cotton",
        "crop_type": "cotton",
        "lat": 32.8795,
        "lng": -111.7574,
        "area_acres": 40.0,
        "soil_type": "sandy loam",
        "owner_phone": "+16025551234",
        "ndvi": 0.38,
        "stress": "high",
        "trend": "declining",
        "fraction": 0.48,
        "soil_profile": {
            "soil_type": "Casa Grande sandy loam",
            "ph": 7.8,
            "organic_matter_pct": 1.2,
            "drainage_class": "well-drained",
            "water_holding_capacity": "low",
            "available_water_in_per_ft": 1.1,
        },
    },
    {
        "name": "Mesa Citrus Grove",
        "crop_type": "citrus",
        "lat": 32.8650,
        "lng": -111.7400,
        "area_acres": 15.0,
        "soil_type": "clay loam",
        "owner_phone": "+16025559876",
        "ndvi": 0.72,
        "stress": "low",
        "trend": "stable",
        "fraction": 0.84,
        "soil_profile": {
            "soil_type": "Mohall clay loam",
            "ph": 7.2,
            "organic_matter_pct": 2.4,
            "drainage_class": "moderately well-drained",
            "water_holding_capacity": "moderate",
            "available_water_in_per_ft": 1.8,
        },
    },
    {
        "name": "Chandler Alfalfa",
        "crop_type": "alfalfa",
        "lat": 32.8900,
        "lng": -111.7700,
        "area_acres": 60.0,
        "soil_type": "silty clay",
        "owner_phone": "+16025551234",
        "ndvi": 0.29,
        "stress": "severe",
        "trend": "declining",
        "fraction": 0.35,
        "soil_profile": {
            "soil_type": "Laveen silty clay",
            "ph": 7.5,
            "organic_matter_pct": 1.8,
            "drainage_class": "somewhat poorly drained",
            "water_holding_capacity": "high",
            "available_water_in_per_ft": 2.2,
        },
    },
]

SCENARIOS = [
    {
        "id": 1,
        "title": "Cotton Drought Emergency",
        "description": "Farmer checks on cotton field during Arizona heat wave. NDVI is dropping, no rain in forecast, soil moisture critically low.",
        "field_index": 0,
        "message": "How's my field looking? We haven't had rain in weeks and it's been over 100 degrees.",
        "channel": "dashboard",
        "expected_action": "irrigate",
    },
    {
        "id": 2,
        "title": "Citrus Grove Check-in",
        "description": "Routine check on healthy citrus grove. NDVI is good, moderate weather. Agent should confirm health and recommend monitoring.",
        "field_index": 1,
        "message": "Check on my citrus trees please. Any issues I should know about?",
        "channel": "dashboard",
        "expected_action": "no_action or monitor",
    },
    {
        "id": 3,
        "title": "Alfalfa Nitrogen Deficiency",
        "description": "Farmer notices yellowing alfalfa. Severe NDVI decline. Agent should identify nitrogen deficiency and recommend fertilization.",
        "field_index": 2,
        "message": "My alfalfa looks yellow and thin. The last cutting was weak. What should I do?",
        "channel": "dashboard",
        "expected_action": "fertilize",
    },
    {
        "id": 4,
        "title": "General Agricultural Question",
        "description": "Farmer asks a general knowledge question. Agent should route to QA path without running the full tool pipeline.",
        "field_index": 0,
        "message": "What's the best time of year to plant cotton in Arizona? And what variety do you recommend for sandy loam soil?",
        "channel": "dashboard",
        "expected_action": "general_qa (no recommendation)",
    },
    {
        "id": 5,
        "title": "SMS Water Cost Estimate",
        "description": "Farmer texts via SMS asking about irrigation costs. Simulates the Twilio webhook path. Full pipeline with cost focus.",
        "field_index": 0,
        "message": "Need a water cost estimate for my cotton. How much will it cost to irrigate this week?",
        "channel": "sms",
        "expected_action": "irrigate with cost",
    },
]

# ─── Command ────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = "Run a full CropAdvisor demo with real Gemini agent calls across 5 scenarios."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scenario", type=int, default=0,
            help="Run only this scenario number (1-5). Default: run all.",
        )
        parser.add_argument(
            "--skip-seed", action="store_true",
            help="Skip seeding data, use existing fields/user.",
        )
        parser.add_argument(
            "--reset", action="store_true",
            help="Wipe all data and re-seed before running.",
        )

    def handle(self, *args, **options):
        self._print_banner()

        if options["reset"]:
            self._reset()

        if not options["skip_seed"]:
            user, fields = self._seed()
        else:
            user = User.objects.get(username=DEMO_USER["username"])
            fields = list(Field.objects.filter(owner=user).order_by('name'))

        # Determine which scenarios to run
        scenarios = SCENARIOS
        if options["scenario"]:
            scenarios = [s for s in SCENARIOS if s["id"] == options["scenario"]]
            if not scenarios:
                self.stderr.write(f"Scenario {options['scenario']} not found (valid: 1-5)")
                return

        self.stdout.write("")
        self.stdout.write(self._divider())
        self.stdout.write(self.style.SUCCESS(f"  Running {len(scenarios)} scenario(s) through the Gemini agent engine"))
        self.stdout.write(self._divider())

        results = []
        for scenario in scenarios:
            result = self._run_scenario(user, fields, scenario)
            results.append(result)

        self._print_summary(results)

    # ─── Seed ───

    def _seed(self):
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("  Seeding demo data..."))

        user, created = User.objects.get_or_create(
            username=DEMO_USER["username"],
            defaults={"email": DEMO_USER["email"]},
        )
        if created:
            user.set_password(DEMO_USER["password"])
            user.save()
            self.stdout.write(f"    Created user: {user.username}")
        else:
            self.stdout.write(f"    User exists: {user.username}")

        fields = []
        for fd in FIELDS:
            field, created = Field.objects.get_or_create(
                owner=user,
                name=fd["name"],
                defaults={
                    "crop_type": fd["crop_type"],
                    "lat": fd["lat"],
                    "lng": fd["lng"],
                    "area_acres": fd["area_acres"],
                    "soil_type": fd["soil_type"],
                    "owner_phone": fd["owner_phone"],
                },
            )
            fields.append(field)

            # Soil profile
            if not SoilProfile.objects.filter(field=field).exists():
                SoilProfile.objects.create(field=field, **fd["soil_profile"])

            # Crop health record (realistic per-field data)
            if not CropHealthRecord.objects.filter(field=field).exists():
                CropHealthRecord.objects.create(
                    field=field,
                    ndvi_score=fd["ndvi"],
                    stress_level=fd["stress"],
                    vegetation_trend=fd["trend"],
                    vegetation_fraction=fd["fraction"],
                    last_satellite_date=timezone.now(),
                )

            status = "Created" if created else "Exists"
            self.stdout.write(
                f"    {status}: {field.name} | {field.crop_type} | "
                f"{field.area_acres}ac | NDVI {fd['ndvi']} ({fd['stress']})"
            )

        return user, fields

    def _reset(self):
        self.stdout.write(self.style.WARNING("  Resetting all data..."))
        for model in [
            ActionRecommendation, AgentMessage, AgentSession,
            WaterUsageEstimate, PestRiskAssessment, MarketSnapshot,
            WeatherSnapshot, CropHealthRecord, SoilProfile, Field,
        ]:
            model.objects.all().delete()
        User.objects.filter(username=DEMO_USER["username"]).delete()
        self.stdout.write("    Done.")

    # ─── Run Scenario ───

    def _run_scenario(self, user, fields, scenario):
        field = fields[scenario["field_index"]]
        self.stdout.write("")
        self.stdout.write(self._divider())
        self.stdout.write(self.style.SUCCESS(
            f"  SCENARIO {scenario['id']}: {scenario['title']}"
        ))
        self.stdout.write(f"  {scenario['description']}")
        self.stdout.write(f"  Field: {field.name} ({field.crop_type}, {field.area_acres} acres)")
        self.stdout.write(f"  Channel: {scenario['channel'].upper()}")
        self.stdout.write(f"  Expected: {scenario['expected_action']}")
        self.stdout.write(self._divider())
        self.stdout.write("")
        self.stdout.write(f'  Farmer: "{scenario["message"]}"')
        self.stdout.write("")
        self.stdout.write("  Agent is thinking...")

        # Create session
        session = AgentSession.objects.create(
            user=user,
            field=field,
            channel=scenario["channel"],
            phone_number=DEMO_USER["phone"] if scenario["channel"] == "sms" else "",
        )

        # Run engine
        start = time.time()
        try:
            from agent.engine import CropAdvisorEngine
            engine = CropAdvisorEngine()
            result = engine.run(
                field_id=str(field.id),
                user_message=scenario["message"],
                session_id=str(session.id),
            )
            elapsed = time.time() - start

            # Count tool calls
            tool_calls = AgentMessage.objects.filter(
                session=session, role='tool_call'
            ).count()

            rec = result.get("recommendation")

            self.stdout.write("")
            if rec:
                action = rec.get("action_type", "—")
                urgency = rec.get("urgency", "—")
                cost = rec.get("estimated_cost", 0)
                risk = rec.get("risk_if_delayed", "")

                action_color = {
                    "irrigate": self.style.HTTP_INFO,
                    "fertilize": self.style.SUCCESS,
                    "pest_alert": self.style.ERROR,
                    "harvest": self.style.WARNING,
                    "no_action": self.style.HTTP_NOT_MODIFIED,
                }.get(action, self.style.HTTP_NOT_MODIFIED)

                self.stdout.write(f"  {action_color(f'ACTION: {action.upper()}')}  |  Urgency: {urgency}  |  Cost: ${cost:.0f}")
                self.stdout.write("")
                self.stdout.write(f"  Agent: {result['response'][:200]}{'...' if len(result['response']) > 200 else ''}")
                if risk:
                    self.stdout.write(f"  Risk: {risk[:150]}{'...' if len(risk) > 150 else ''}")
            else:
                self.stdout.write(self.style.HTTP_NOT_MODIFIED("  GENERAL Q&A (no structured recommendation)"))
                self.stdout.write("")
                self.stdout.write(f"  Agent: {result['response'][:300]}{'...' if len(result['response']) > 300 else ''}")

            self.stdout.write("")
            self.stdout.write(f"  Tools called: {tool_calls}  |  Duration: {elapsed:.1f}s  |  Session: {session.id}")

            return {
                "scenario": scenario,
                "success": True,
                "action": rec.get("action_type") if rec else "general_qa",
                "urgency": rec.get("urgency") if rec else "—",
                "cost": rec.get("estimated_cost", 0) if rec else 0,
                "tool_calls": tool_calls,
                "duration": elapsed,
                "response_preview": result["response"][:100],
            }

        except Exception as e:
            elapsed = time.time() - start
            self.stdout.write(self.style.ERROR(f"  FAILED: {e}"))
            return {
                "scenario": scenario,
                "success": False,
                "action": "error",
                "urgency": "—",
                "cost": 0,
                "tool_calls": 0,
                "duration": elapsed,
                "response_preview": str(e)[:100],
            }

    # ─── Summary ───

    def _print_summary(self, results):
        self.stdout.write("")
        self.stdout.write(self._divider("="))
        self.stdout.write(self.style.SUCCESS("  DEMO SUMMARY"))
        self.stdout.write(self._divider("="))
        self.stdout.write("")

        # Table header
        self.stdout.write(
            f"  {'#':<3} {'Scenario':<28} {'Status':<8} {'Action':<14} {'Urgency':<12} "
            f"{'Cost':<10} {'Tools':<7} {'Time':<7}"
        )
        self.stdout.write(f"  {'─' * 95}")

        total_time = 0
        total_tools = 0
        success_count = 0

        for r in results:
            s = r["scenario"]
            status = self.style.SUCCESS("OK") if r["success"] else self.style.ERROR("FAIL")
            cost_str = f"${r['cost']:.0f}" if r["cost"] else "—"
            action = r["action"].upper() if r["action"] else "—"

            self.stdout.write(
                f"  {s['id']:<3} {s['title']:<28} {status:<17} {action:<14} {r['urgency']:<12} "
                f"{cost_str:<10} {r['tool_calls']:<7} {r['duration']:.1f}s"
            )

            total_time += r["duration"]
            total_tools += r["tool_calls"]
            if r["success"]:
                success_count += 1

        self.stdout.write(f"  {'─' * 95}")
        self.stdout.write(
            f"  {'TOTAL':<3} {'':<28} {success_count}/{len(results):<8} {'':<14} {'':<12} "
            f"{'':<10} {total_tools:<7} {total_time:.1f}s"
        )

        self.stdout.write("")
        self.stdout.write(self._divider())
        self.stdout.write(f"  Login:  username={DEMO_USER['username']}  password={DEMO_USER['password']}")
        self.stdout.write(f"  Phone:  {DEMO_USER['phone']} (for SMS/Twilio testing)")
        self.stdout.write(self._divider())
        self.stdout.write("")

    # ─── Helpers ───

    def _print_banner(self):
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("  ╔══════════════════════════════════════════════════╗"))
        self.stdout.write(self.style.SUCCESS("  ║          CROPADVISOR — FULL DEMO SCRIPT          ║"))
        self.stdout.write(self.style.SUCCESS("  ║     Gemini-Powered Agricultural AI Agent         ║"))
        self.stdout.write(self.style.SUCCESS("  ║                    SUCCESS                       ║"))
        self.stdout.write(self.style.SUCCESS("  ╚══════════════════════════════════════════════════╝"))

    def _divider(self, char="─"):
        return f"  {char * 60}"

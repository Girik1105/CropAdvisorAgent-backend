"""
Full demo script that showcases CropAdvisor's agentic capabilities with REAL data.

Data sources hit during the demo:
- OpenWeatherMap API — live weather for Casa Grande, AZ
- USDA SSURGO API — real soil profiles by GPS coordinates
- NASA POWER API — satellite evapotranspiration (FAO Penman-Monteith ET₀)
- Rule-based pest risk engine — uses live weather conditions
- Market commodity prices — realistic USDA/exchange data
- Growth stage calendar — month-specific guidance per crop

Usage:
    python manage.py run_demo                  # Run all scenarios
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

# Real coordinates in Pinal County, AZ — actual farmland
FIELDS = [
    {
        "name": "North 40 Cotton",
        "crop_type": "cotton",
        "lat": 32.8795,
        "lng": -111.7574,
        "area_acres": 40.0,
        "soil_type": "sandy loam",
        "owner_phone": "+16025551234",
        # NDVI simulates drought-stressed cotton
        "ndvi": 0.38,
        "stress": "high",
        "trend": "declining",
        "fraction": 0.48,
        # NO soil_profile — agent will fetch from USDA SSURGO API
    },
    {
        "name": "Mesa Citrus Grove",
        "crop_type": "citrus",
        "lat": 32.8650,
        "lng": -111.7400,
        "area_acres": 15.0,
        "soil_type": "clay loam",
        "owner_phone": "+16025559876",
        # NDVI simulates healthy citrus
        "ndvi": 0.72,
        "stress": "low",
        "trend": "stable",
        "fraction": 0.84,
    },
    {
        "name": "Chandler Alfalfa",
        "crop_type": "alfalfa",
        "lat": 32.8900,
        "lng": -111.7700,
        "area_acres": 60.0,
        "soil_type": "silty clay",
        "owner_phone": "+16025551234",
        # NDVI simulates severe nitrogen deficiency
        "ndvi": 0.29,
        "stress": "severe",
        "trend": "declining",
        "fraction": 0.35,
    },
]

SCENARIOS = [
    {
        "id": 1,
        "title": "Cotton Drought Emergency",
        "description": (
            "Arizona heat wave — 100°F+, no rain in weeks. Agent gathers LIVE weather "
            "(OpenWeatherMap), REAL soil data (USDA SSURGO), NASA POWER evapotranspiration, "
            "pest risk assessment, market prices, and growth stage. Should recommend immediate irrigation."
        ),
        "field_index": 0,
        "message": "How's my field looking? We haven't had rain in weeks and it's been over 100 degrees.",
        "channel": "dashboard",
        "expected_action": "irrigate",
    },
    {
        "id": 2,
        "title": "Citrus Grove Check-in",
        "description": (
            "Routine check on healthy citrus grove (NDVI 0.72). Agent should confirm health, "
            "note any pest concerns from weather conditions, and recommend monitoring."
        ),
        "field_index": 1,
        "message": "Check on my citrus trees please. Any issues I should know about?",
        "channel": "dashboard",
        "expected_action": "no_action or monitor",
    },
    {
        "id": 3,
        "title": "Alfalfa Nitrogen Crisis",
        "description": (
            "Farmer notices yellowing alfalfa (NDVI 0.29 — severe). Agent should identify "
            "nitrogen deficiency, calculate fertilizer cost for 60 acres, and factor in "
            "alfalfa market prices ($225/ton) for ROI analysis."
        ),
        "field_index": 2,
        "message": "My alfalfa looks yellow and thin. The last cutting was really weak. What should I do?",
        "channel": "dashboard",
        "expected_action": "fertilize",
    },
    {
        "id": 4,
        "title": "General Question (Intent Routing)",
        "description": (
            "Tests the intent classifier. Farmer asks a general knowledge question — agent "
            "should route to the QA path WITHOUT calling the 7-tool pipeline. Proves the "
            "agent reasons about what tools to use, not just runs everything blindly."
        ),
        "field_index": 0,
        "message": "What's the best time of year to plant cotton in Arizona? And what variety do you recommend for sandy loam soil?",
        "channel": "dashboard",
        "expected_action": "general_qa (no recommendation)",
    },
    {
        "id": 5,
        "title": "SMS Water Cost Estimate",
        "description": (
            "Simulates Twilio SMS path. Farmer texts asking about irrigation costs. Agent "
            "uses NASA POWER ET₀ data + crop Kc coefficient + field acreage to calculate "
            "precise daily water needs and cost at $85/acre-foot (Arizona rates)."
        ),
        "field_index": 0,
        "message": "Need a water cost estimate for my cotton. How much will it cost to irrigate this week?",
        "channel": "sms",
        "expected_action": "irrigate with cost",
    },
    {
        "id": 6,
        "title": "Pest Alert After Weather Check",
        "description": (
            "Farmer asks specifically about pests. Agent should cross-reference live weather "
            "(temperature + humidity) with crop-specific pest rules. In Arizona April heat "
            "with low humidity → spider mites and thrips are the primary threats for cotton."
        ),
        "field_index": 0,
        "message": "I'm seeing some damage on my cotton leaves. Could it be pests? What should I spray?",
        "channel": "dashboard",
        "expected_action": "pest_alert",
    },
]

# ─── Command ────────────────────────────────────────────────────────


class Command(BaseCommand):
    help = "Run a full CropAdvisor demo with real Gemini agent calls and live data APIs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--scenario", type=int, default=0,
            help="Run only this scenario number (1-6). Default: run all.",
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

        scenarios = SCENARIOS
        if options["scenario"]:
            scenarios = [s for s in SCENARIOS if s["id"] == options["scenario"]]
            if not scenarios:
                self.stderr.write(f"Scenario {options['scenario']} not found (valid: 1-6)")
                return

        self.stdout.write("")
        self.stdout.write(self._divider())
        self.stdout.write(self.style.SUCCESS(
            f"  Running {len(scenarios)} scenario(s) through the Gemini agent engine"
        ))
        self.stdout.write(f"  Data sources: OpenWeatherMap (live), USDA SSURGO (real), NASA POWER (satellite)")
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
        self.stdout.write("  (Soil profiles NOT pre-seeded — agent will fetch from USDA SSURGO API)")

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

            # Crop health (NDVI) — seed this so the agent has vegetation stress data
            if not CropHealthRecord.objects.filter(field=field).exists():
                CropHealthRecord.objects.create(
                    field=field,
                    ndvi_score=fd["ndvi"],
                    stress_level=fd["stress"],
                    vegetation_trend=fd["trend"],
                    vegetation_fraction=fd["fraction"],
                    last_satellite_date=timezone.now(),
                )

            # NO soil profile seeding — let agent fetch from USDA SSURGO
            # NO weather seeding — let agent fetch live from OpenWeatherMap

            status = "Created" if created else "Exists"
            self.stdout.write(
                f"    {status}: {field.name} | {field.crop_type} | "
                f"{field.area_acres}ac | NDVI {fd['ndvi']} ({fd['stress']}) | "
                f"({field.lat}, {field.lng})"
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
        self.stdout.write(f"  Coordinates: {field.lat}°N, {abs(field.lng)}°W")
        self.stdout.write(f"  Channel: {scenario['channel'].upper()}")
        self.stdout.write(f"  Expected: {scenario['expected_action']}")
        self.stdout.write(self._divider())
        self.stdout.write("")
        self.stdout.write(f'  Farmer: "{scenario["message"]}"')
        self.stdout.write("")
        self.stdout.write("  Agent is thinking...")

        session = AgentSession.objects.create(
            user=user,
            field=field,
            channel=scenario["channel"],
            phone_number=DEMO_USER["phone"] if scenario["channel"] == "sms" else "",
        )

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

            # Count tool calls and extract data sources
            tool_msgs = AgentMessage.objects.filter(session=session, role='tool_call')
            tool_calls = tool_msgs.count()

            # Check for real data sources in tool outputs
            data_sources = []
            for msg in tool_msgs:
                if msg.tool_output:
                    src = msg.tool_output.get("data_source")
                    if src and src not in data_sources:
                        data_sources.append(src)
                    # Check for NASA POWER in water usage
                    if msg.tool_output.get("et0_mm_per_day"):
                        if "NASA POWER" not in data_sources:
                            data_sources.append("NASA POWER")
                    # Check for USDA in soil
                    if msg.tool_output.get("component_name"):
                        if "USDA SSURGO" not in data_sources:
                            data_sources.append("USDA SSURGO")

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

                self.stdout.write(
                    f"  {action_color(f'ACTION: {action.upper()}')}  |  "
                    f"Urgency: {urgency}  |  Cost: ${cost:.0f}"
                )
                self.stdout.write("")
                self.stdout.write(f"  Agent: {result['response'][:250]}{'...' if len(result['response']) > 250 else ''}")
                if risk:
                    self.stdout.write(f"  Risk:  {risk[:200]}{'...' if len(risk) > 200 else ''}")
            else:
                self.stdout.write(self.style.HTTP_NOT_MODIFIED(
                    "  GENERAL Q&A (no structured recommendation)"
                ))
                self.stdout.write("")
                self.stdout.write(f"  Agent: {result['response'][:350]}{'...' if len(result['response']) > 350 else ''}")

            self.stdout.write("")
            sources_str = ", ".join(data_sources) if data_sources else "cached/static"
            self.stdout.write(
                f"  Tools: {tool_calls}  |  Duration: {elapsed:.1f}s  |  "
                f"Data: {sources_str}"
            )

            return {
                "scenario": scenario,
                "success": True,
                "action": rec.get("action_type") if rec else "general_qa",
                "urgency": rec.get("urgency") if rec else "—",
                "cost": rec.get("estimated_cost", 0) if rec else 0,
                "tool_calls": tool_calls,
                "duration": elapsed,
                "data_sources": data_sources,
                "response_preview": result["response"][:100],
            }

        except Exception as e:
            elapsed = time.time() - start
            self.stdout.write(self.style.ERROR(f"  FAILED: {e}"))
            import traceback
            traceback.print_exc()
            return {
                "scenario": scenario,
                "success": False,
                "action": "error",
                "urgency": "—",
                "cost": 0,
                "tool_calls": 0,
                "duration": elapsed,
                "data_sources": [],
                "response_preview": str(e)[:100],
            }

    # ─── Summary ───

    def _print_summary(self, results):
        self.stdout.write("")
        self.stdout.write(self._divider("="))
        self.stdout.write(self.style.SUCCESS("  DEMO SUMMARY"))
        self.stdout.write(self._divider("="))
        self.stdout.write("")

        self.stdout.write(
            f"  {'#':<3} {'Scenario':<30} {'Status':<8} {'Action':<14} "
            f"{'Urgency':<12} {'Cost':<8} {'Tools':<6} {'Time':<7} {'Data Sources'}"
        )
        self.stdout.write(f"  {'─' * 110}")

        total_time = 0
        total_tools = 0
        success_count = 0
        all_sources = set()

        for r in results:
            s = r["scenario"]
            status = self.style.SUCCESS("OK") if r["success"] else self.style.ERROR("FAIL")
            cost_str = f"${r['cost']:.0f}" if r["cost"] else "—"
            action = r["action"].upper() if r["action"] else "—"
            sources = ", ".join(r.get("data_sources", [])) or "—"
            all_sources.update(r.get("data_sources", []))

            self.stdout.write(
                f"  {s['id']:<3} {s['title']:<30} {status:<17} {action:<14} "
                f"{r['urgency']:<12} {cost_str:<8} {r['tool_calls']:<6} "
                f"{r['duration']:.1f}s   {sources}"
            )

            total_time += r["duration"]
            total_tools += r["tool_calls"]
            if r["success"]:
                success_count += 1

        self.stdout.write(f"  {'─' * 110}")
        self.stdout.write(
            f"  {'ALL':<3} {'':<30} {success_count}/{len(results):<8} "
            f"{'':<14} {'':<12} {'':<8} {total_tools:<6} {total_time:.1f}s"
        )

        self.stdout.write("")
        self.stdout.write(self._divider())
        self.stdout.write(f"  Real data sources used: {', '.join(sorted(all_sources)) or 'none'}")
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

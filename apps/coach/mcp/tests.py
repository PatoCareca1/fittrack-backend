import json

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.body.models import BodyMetric
from apps.diet.models import Food, FoodSource, MealPlan
from apps.professional.models import DietAssignment, LinkStatus, ProfessionalLink
from apps.users.models import AccountType, User
from apps.workouts.models import Exercise, MuscleGroup


def _auth_header(user) -> dict:
    token = RefreshToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token.access_token}"}


def _rpc(client, method, params=None, headers=None, request_id=1):
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
    return client.post("/mcp/", payload, format="json", **(headers or {}))


class MCPServerTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.nutritionist = User.objects.create_user(
            email="nutri@test.dev", password="x", account_type=AccountType.NUTRITIONIST
        )
        self.personal = User.objects.create_user(
            email="personal@test.dev", password="x", account_type=AccountType.PERSONAL
        )
        self.student = User.objects.create_user(email="aluno@test.dev", password="x")
        self.other_student = User.objects.create_user(email="outro-aluno@test.dev", password="x")

        ProfessionalLink.objects.create(
            professional=self.nutritionist,
            student=self.student,
            invite_code="AAA111",
            status=LinkStatus.ACTIVE,
        )
        ProfessionalLink.objects.create(
            professional=self.personal,
            student=self.student,
            invite_code="BBB222",
            status=LinkStatus.ACTIVE,
        )
        # other_student não tem vínculo com nenhum dos dois profissionais.

        self.metric = BodyMetric.objects.create(
            user=self.student,
            weight_kg=80,
            bmr_calculated=1600,
            tdee=2000,
            calorie_goal=1500,
            protein_g=80,
            carbs_g=140,
            fat_g=50,
        )

        self.protein_food = Food.objects.create(
            name="Frango grelhado", source=FoodSource.TACO,
            kcal=200, protein_g=40, carbs_g=0, fat_g=0,
        )
        self.carb_food = Food.objects.create(
            name="Arroz branco", source=FoodSource.TACO,
            kcal=130, protein_g=0, carbs_g=28, fat_g=0,
        )
        self.fat_food = Food.objects.create(
            name="Azeite", source=FoodSource.TACO,
            kcal=900, protein_g=0, carbs_g=0, fat_g=100,
        )

    def _valid_meals(self):
        return [
            {
                "name": "Café", "time": "08:00", "order": 1,
                "items": [{"food_id": self.protein_food.id, "quantity_g": 200}],
            },
            {
                "name": "Almoço", "time": "12:00", "order": 2,
                "items": [{"food_id": self.carb_food.id, "quantity_g": 500}],
            },
            {
                "name": "Jantar", "time": "19:00", "order": 3,
                "items": [{"food_id": self.fat_food.id, "quantity_g": 50}],
            },
        ]

    def test_initialize_and_tools_list_do_not_require_auth(self):
        res = _rpc(self.client, "initialize")
        self.assertEqual(res.status_code, 200)
        self.assertIn("result", res.data)
        self.assertEqual(res.data["result"]["serverInfo"]["name"], "fittrack-mcp")

        res = _rpc(self.client, "tools/list")
        self.assertEqual(res.status_code, 200)
        tool_names = {tool["name"] for tool in res.data["result"]["tools"]}
        self.assertEqual(
            tool_names,
            {
                "listar_alunos",
                "obter_metricas",
                "buscar_alimento",
                "listar_exercicios",
                "criar_plano_alimentar",
            },
        )

    def test_missing_jwt_returns_authentication_error(self):
        res = _rpc(self.client, "tools/call", {"name": "listar_alunos", "arguments": {}})
        self.assertEqual(res.status_code, 200)
        self.assertIn("error", res.data)
        self.assertEqual(res.data["error"]["code"], -32001)
        self.assertNotIn("result", res.data)

    def test_listar_alunos_returns_only_own_linked_students(self):
        res = _rpc(
            self.client,
            "tools/call",
            {"name": "listar_alunos", "arguments": {}},
            headers=_auth_header(self.nutritionist),
        )
        self.assertEqual(res.status_code, 200)
        content = json.loads(res.data["result"]["content"][0]["text"])
        self.assertEqual([row["id"] for row in content], [self.student.id])
        self.assertEqual(content[0]["email"], self.student.email)

    def test_obter_metricas_without_link_raises_explicit_permission_error(self):
        res = _rpc(
            self.client,
            "tools/call",
            {"name": "obter_metricas", "arguments": {"student_id": self.other_student.id}},
            headers=_auth_header(self.nutritionist),
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("error", res.data)
        self.assertEqual(res.data["error"]["code"], -32002)
        self.assertNotIn("result", res.data)

    def test_obter_metricas_with_link_returns_history(self):
        res = _rpc(
            self.client,
            "tools/call",
            {"name": "obter_metricas", "arguments": {"student_id": self.student.id}},
            headers=_auth_header(self.nutritionist),
        )
        self.assertEqual(res.status_code, 200)
        content = json.loads(res.data["result"]["content"][0]["text"])
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["calorie_goal"], 1500)

    def test_personal_cannot_create_meal_plan(self):
        res = _rpc(
            self.client,
            "tools/call",
            {
                "name": "criar_plano_alimentar",
                "arguments": {"student_id": self.student.id, "meals": self._valid_meals()},
            },
            headers=_auth_header(self.personal),
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("error", res.data)
        self.assertEqual(res.data["error"]["code"], -32002)
        self.assertEqual(MealPlan.objects.count(), 0)

    def test_create_meal_plan_out_of_targets_is_rejected_with_validate_meal_plan_errors(self):
        meals = self._valid_meals()
        meals[0]["items"][0]["quantity_g"] = 2000  # dispara kcal bem acima do alvo

        res = _rpc(
            self.client,
            "tools/call",
            {
                "name": "criar_plano_alimentar",
                "arguments": {"student_id": self.student.id, "meals": meals},
            },
            headers=_auth_header(self.nutritionist),
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("error", res.data)
        self.assertEqual(res.data["error"]["code"], -32602)
        errors = res.data["error"]["data"]["meals"]
        self.assertTrue(any("calorias" in str(error) for error in errors))
        self.assertEqual(MealPlan.objects.count(), 0)

    def test_valid_meal_plan_persists_and_is_visible_to_student(self):
        res = _rpc(
            self.client,
            "tools/call",
            {
                "name": "criar_plano_alimentar",
                "arguments": {"student_id": self.student.id, "meals": self._valid_meals()},
            },
            headers=_auth_header(self.nutritionist),
        )
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("error", res.data)
        content = json.loads(res.data["result"]["content"][0]["text"])
        meal_plan_id = content["meal_plan_id"]

        self.assertTrue(
            DietAssignment.objects.filter(
                meal_plan_id=meal_plan_id, link__student=self.student
            ).exists()
        )

        self.client.force_authenticate(self.student)
        student_res = self.client.get("/api/v1/professional/diet-assignments/")
        self.assertEqual(student_res.status_code, 200)
        plan_ids = [row["meal_plan"]["id"] for row in student_res.data]
        self.assertIn(meal_plan_id, plan_ids)

    def test_buscar_alimento_and_listar_exercicios_work_without_link(self):
        Exercise.objects.get_or_create(
            icon_slug="supino-reto-mcp-test",
            defaults={"name": "Supino reto (MCP test)", "muscle_group": MuscleGroup.CHEST},
        )

        res = _rpc(
            self.client,
            "tools/call",
            {"name": "buscar_alimento", "arguments": {"query": "frango"}},
            headers=_auth_header(self.nutritionist),
        )
        self.assertEqual(res.status_code, 200)
        content = json.loads(res.data["result"]["content"][0]["text"])
        self.assertTrue(any(item["name"] == "Frango grelhado" for item in content))

        res = _rpc(
            self.client,
            "tools/call",
            {"name": "listar_exercicios", "arguments": {}},
            headers=_auth_header(self.nutritionist),
        )
        self.assertEqual(res.status_code, 200)
        content = json.loads(res.data["result"]["content"][0]["text"])
        self.assertTrue(any(item["name"] == "Supino reto (MCP test)" for item in content))

    def test_resources_read_requires_link(self):
        res = _rpc(
            self.client,
            "resources/read",
            {"uri": f"fittrack://aluno/{self.other_student.id}/perfil"},
            headers=_auth_header(self.nutritionist),
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["error"]["code"], -32002)

    def test_resources_read_profile_with_link(self):
        res = _rpc(
            self.client,
            "resources/read",
            {"uri": f"fittrack://aluno/{self.student.id}/perfil"},
            headers=_auth_header(self.nutritionist),
        )
        self.assertEqual(res.status_code, 200)
        payload = json.loads(res.data["result"]["contents"][0]["text"])
        self.assertEqual(payload["id"], self.student.id)
        self.assertEqual(payload["email"], self.student.email)

from django.test import TestCase
from rest_framework.test import APIClient

from apps.diet.models import Food, FoodSource, MealLog
from apps.users.models import User


class DietApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="aluno@test.dev", password="x")
        self.other = User.objects.create_user(email="outro@test.dev", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.rice = Food.objects.create(
            name="Arroz branco cozido", source=FoodSource.TACO,
            kcal=128, protein_g=2.5, carbs_g=28.1, fat_g=0.2,
        )
        self.chicken = Food.objects.create(
            name="Peito de frango grelhado", source=FoodSource.TACO,
            kcal=159, protein_g=32, carbs_g=0, fat_g=2.5,
        )

    def _create_plan(self):
        return self.client.post(
            "/api/v1/diet/meal-plans/",
            {
                "name": "Plano Hipertrofia",
                "meals": [
                    {
                        "name": "Almoço",
                        "time": "12:30",
                        "items": [
                            {"food": self.rice.id, "quantity_g": 150},
                            {"food": self.chicken.id, "quantity_g": 120},
                        ],
                    },
                    {"name": "Jantar", "time": "20:00", "items": []},
                ],
            },
            format="json",
        )

    def test_food_search_by_query(self):
        res = self.client.get("/api/v1/diet/foods/?q=frango")
        self.assertEqual(res.status_code, 200)
        names = [f["name"] for f in res.data]
        self.assertIn("Peito de frango grelhado", names)
        self.assertNotIn("Arroz branco cozido", names)

    def test_custom_food_is_private(self):
        res = self.client.post(
            "/api/v1/diet/foods/",
            {"name": "Marmita da mãe", "kcal": 350, "protein_g": 25,
             "carbs_g": 40, "fat_g": 9},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["source"], FoodSource.CUSTOM)
        # outro usuário não vê o alimento privado
        self.client.force_authenticate(self.other)
        res = self.client.get("/api/v1/diet/foods/?q=marmita")
        self.assertEqual(len(res.data), 0)

    def test_create_plan_with_nested_meals_and_totals(self):
        res = self._create_plan()
        self.assertEqual(res.status_code, 201)
        lunch = res.data["meals"][0]
        self.assertEqual(len(lunch["items"]), 2)
        # 150g arroz (128/100g) + 120g frango (159/100g) = 192 + 190.8
        self.assertAlmostEqual(float(lunch["totals"]["kcal"]), 382.8, places=1)
        self.assertAlmostEqual(float(lunch["totals"]["protein_g"]), 42.2, places=1)

    def test_plans_are_scoped_to_owner(self):
        self._create_plan()
        self.client.force_authenticate(self.other)
        res = self.client.get("/api/v1/diet/meal-plans/")
        self.assertEqual(len(res.data), 0)

    def test_mark_done_is_idempotent_per_day(self):
        plan = self._create_plan().data
        meal_id = plan["meals"][0]["id"]
        res = self.client.post(
            f"/api/v1/diet/meals/{meal_id}/mark-done/", {"comment": "boa"}
        )
        self.assertEqual(res.status_code, 201)
        res = self.client.post(
            f"/api/v1/diet/meals/{meal_id}/mark-done/", {"comment": "editado"}
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(MealLog.objects.count(), 1)
        self.assertEqual(MealLog.objects.get().comment, "editado")

    def test_cannot_mark_someone_elses_meal(self):
        plan = self._create_plan().data
        meal_id = plan["meals"][0]["id"]
        self.client.force_authenticate(self.other)
        res = self.client.post(f"/api/v1/diet/meals/{meal_id}/mark-done/")
        self.assertEqual(res.status_code, 403)

    def test_unmark_removes_log(self):
        plan = self._create_plan().data
        meal_id = plan["meals"][0]["id"]
        self.client.post(f"/api/v1/diet/meals/{meal_id}/mark-done/")
        res = self.client.post(f"/api/v1/diet/meals/{meal_id}/unmark/")
        self.assertEqual(res.status_code, 204)
        self.assertEqual(MealLog.objects.count(), 0)

    def test_granular_meal_crud_preserves_logs(self):
        plan = self._create_plan().data
        lunch_id = plan["meals"][0]["id"]
        self.client.post(f"/api/v1/diet/meals/{lunch_id}/mark-done/")
        # adicionar refeição nova não recria as existentes
        res = self.client.post(
            "/api/v1/diet/meals/", {"plan": plan["id"], "name": "Lanche", "time": "16:00"}
        )
        self.assertEqual(res.status_code, 201)
        # adicionar item à refeição existente
        res = self.client.post(
            f"/api/v1/diet/meals/{lunch_id}/items/",
            {"food": self.chicken.id, "quantity_g": 50},
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(len(res.data["items"]), 3)
        # log do dia continua lá
        self.assertEqual(MealLog.objects.count(), 1)
        # remover item
        item_id = res.data["items"][-1]["id"]
        res = self.client.delete(f"/api/v1/diet/meal-items/{item_id}/")
        self.assertEqual(res.status_code, 204)
        # excluir refeição de outro usuário falha
        self.client.force_authenticate(self.other)
        res = self.client.delete(f"/api/v1/diet/meals/{lunch_id}/")
        self.assertEqual(res.status_code, 400)

    def test_meal_log_list_filters_by_date(self):
        plan = self._create_plan().data
        meal_id = plan["meals"][0]["id"]
        self.client.post(
            f"/api/v1/diet/meals/{meal_id}/mark-done/", {"date": "2026-07-01"}
        )
        res = self.client.get("/api/v1/diet/meal-logs/?date=2026-07-01")
        self.assertEqual(len(res.data), 1)
        res = self.client.get("/api/v1/diet/meal-logs/?date=2026-06-30")
        self.assertEqual(len(res.data), 0)

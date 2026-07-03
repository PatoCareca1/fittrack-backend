from django.test import TestCase
from rest_framework.test import APIClient

from apps.professional.models import LinkStatus, ProfessionalLink
from apps.users.models import AccountType, User
from apps.workouts.models import Workout


class ProfessionalFlowTests(TestCase):
    def setUp(self):
        self.personal = User.objects.create_user(
            email="personal@test.dev", password="x", account_type=AccountType.PERSONAL
        )
        self.nutritionist = User.objects.create_user(
            email="nutri@test.dev", password="x", account_type=AccountType.NUTRITIONIST
        )
        self.student = User.objects.create_user(email="aluno@test.dev", password="x")
        self.client = APIClient()

    def _as(self, user):
        self.client.force_authenticate(user)
        return self.client

    def _invite(self, professional):
        res = self._as(professional).post("/api/v1/professional/links/invite/")
        self.assertEqual(res.status_code, 201)
        return res.data["invite_code"]

    def _accept(self, code):
        return self._as(self.student).post(
            "/api/v1/professional/links/accept/", {"invite_code": code}
        )

    def test_invite_and_accept_creates_active_link(self):
        code = self._invite(self.personal)
        res = self._accept(code)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], LinkStatus.ACTIVE)
        self.assertEqual(res.data["student"]["id"], self.student.id)

    def test_common_user_cannot_invite(self):
        res = self._as(self.student).post("/api/v1/professional/links/invite/")
        self.assertEqual(res.status_code, 403)

    def test_invalid_code_returns_400(self):
        res = self._accept("XXXXXX")
        self.assertEqual(res.status_code, 400)

    def test_rn05_max_one_professional_per_type(self):
        self._accept(self._invite(self.personal))
        # segundo personal: bloqueado
        res = self._accept(self._invite(self.personal))
        self.assertEqual(res.status_code, 400)
        # nutricionista: permitido (tipo diferente)
        res = self._accept(self._invite(self.nutritionist))
        self.assertEqual(res.status_code, 200)

    def test_students_list_only_for_professionals(self):
        self._accept(self._invite(self.personal))
        res = self._as(self.personal).get("/api/v1/professional/students/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        res = self._as(self.student).get("/api/v1/professional/students/")
        self.assertEqual(res.status_code, 403)

    def test_assign_workout_and_student_sees_it(self):
        self._accept(self._invite(self.personal))
        link = ProfessionalLink.objects.get(status=LinkStatus.ACTIVE)
        workout = Workout.objects.create(user=self.personal, name="Treino B")
        res = self._as(self.personal).post(
            "/api/v1/professional/assignments/",
            {"link": link.id, "workout": workout.id, "notes": "12 semanas"},
        )
        self.assertEqual(res.status_code, 201)
        res = self._as(self.student).get("/api/v1/professional/assignments/")
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["workout"]["name"], "Treino B")

    def test_cannot_assign_someone_elses_workout(self):
        self._accept(self._invite(self.personal))
        link = ProfessionalLink.objects.get(status=LinkStatus.ACTIVE)
        others = Workout.objects.create(user=self.student, name="Meu treino")
        res = self._as(self.personal).post(
            "/api/v1/professional/assignments/",
            {"link": link.id, "workout": others.id},
        )
        self.assertEqual(res.status_code, 400)

    def test_revoke_deactivates_assignments(self):
        self._accept(self._invite(self.personal))
        link = ProfessionalLink.objects.get(status=LinkStatus.ACTIVE)
        workout = Workout.objects.create(user=self.personal, name="Treino B")
        self._as(self.personal).post(
            "/api/v1/professional/assignments/",
            {"link": link.id, "workout": workout.id},
        )
        res = self._as(self.student).post(
            f"/api/v1/professional/links/{link.id}/revoke/"
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], LinkStatus.REVOKED)
        res = self._as(self.student).get("/api/v1/professional/assignments/")
        self.assertEqual(len(res.data), 0)

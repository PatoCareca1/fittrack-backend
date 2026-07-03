from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from apps.diet import services
from apps.diet.models import Food, MealLog, MealPlan
from apps.diet.serializers import (
    FoodSerializer,
    MealLogSerializer,
    MealPlanSerializer,
)


class FoodViewSet(ModelViewSet):
    """Busca no catálogo (`?q=`) e cadastro de alimentos personalizados."""

    permission_classes = [IsAuthenticated]
    serializer_class = FoodSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = Food.objects.filter(is_active=True).filter(
            Q(owner__isnull=True) | Q(owner=self.request.user)
        )
        query = self.request.query_params.get("q")
        if query:
            qs = qs.filter(name__icontains=query)
        source = self.request.query_params.get("source")
        if source:
            qs = qs.filter(source=source)
        return qs[:50]

    def create(self, request, *args, **kwargs):
        food = services.create_custom_food(request.user, request.data)
        return Response(FoodSerializer(food).data, status=status.HTTP_201_CREATED)


class MealPlanViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = MealPlanSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return MealPlan.objects.filter(user=self.request.user).prefetch_related(
            "meals__items__food"
        )

    def create(self, request, *args, **kwargs):
        plan = services.create_meal_plan(request.user, request.data)
        return Response(MealPlanSerializer(plan).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        plan = services.update_meal_plan(self.get_object(), request.user, request.data)
        return Response(MealPlanSerializer(plan).data)

    def destroy(self, request, *args, **kwargs):
        services.delete_meal_plan(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MealViewSet(GenericViewSet):
    """Ações sobre refeições individuais (marcação diária — RN09)."""

    permission_classes = [IsAuthenticated]
    serializer_class = MealLogSerializer

    @action(detail=True, methods=["post"], url_path="mark-done")
    def mark_done(self, request, pk=None):
        log = services.mark_meal_done(
            request.user,
            meal_id=pk,
            log_date=request.data.get("date"),
            comment=request.data.get("comment", ""),
        )
        return Response(MealLogSerializer(log).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="unmark")
    def unmark(self, request, pk=None):
        services.unmark_meal(request.user, meal_id=pk, log_date=request.data.get("date"))
        return Response(status=status.HTTP_204_NO_CONTENT)


class MealLogViewSet(GenericViewSet):
    """Histórico de refeições concluídas (`?date=YYYY-MM-DD`)."""

    permission_classes = [IsAuthenticated]
    serializer_class = MealLogSerializer

    def list(self, request):
        qs = MealLog.objects.filter(user=request.user).select_related("meal")
        log_date = request.query_params.get("date")
        if log_date:
            qs = qs.filter(date=log_date)
        return Response(MealLogSerializer(qs[:100], many=True).data)

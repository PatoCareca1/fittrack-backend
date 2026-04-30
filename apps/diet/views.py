from datetime import date as date_type

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.diet import services
from apps.diet.models import Food, MealLog, MealPlan
from apps.diet.serializers import FoodSerializer, MealLogSerializer, MealPlanSerializer


class FoodViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = FoodSerializer
    http_method_names = ["get", "head", "options"]

    def get_queryset(self):
        qs = Food.objects.filter(is_verified=True)
        if q := self.request.query_params.get("q"):
            qs = qs.filter(name__icontains=q)
        if source := self.request.query_params.get("source"):
            qs = qs.filter(source=source)
        return qs


class MealPlanViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = MealPlanSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return (
            MealPlan.objects.filter(user=self.request.user)
            .prefetch_related("meals__items__food")
        )

    def create(self, request, *args, **kwargs):
        plan = services.create_plan(request.user, request.data)
        return Response(MealPlanSerializer(plan).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        plan = services.update_plan(self.get_object(), request.user, request.data)
        return Response(MealPlanSerializer(plan).data)

    def destroy(self, request, *args, **kwargs):
        services.delete_plan(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MealLogViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = MealLogSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        qs = MealLog.objects.filter(user=self.request.user).select_related("meal__plan")
        if date := self.request.query_params.get("date"):
            qs = qs.filter(date=date)
        return qs

    def create(self, request, *args, **kwargs):
        log = services.log_meal(request.user, request.data)
        return Response(MealLogSerializer(log).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        services.delete_meal_log(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DailySummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get("date")
        try:
            target_date = date_type.fromisoformat(date_str) if date_str else date_type.today()
        except ValueError:
            return Response(
                {"date": "Formato inválido. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(services.get_daily_summary(request.user, target_date))
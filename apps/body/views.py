from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.body import services
from apps.body.models import BodyMetric
from apps.body.serializers import BodyMetricSerializer


class BodyMetricViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = BodyMetricSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return BodyMetric.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        metric = services.create_body_metric(request.user, request.data)
        return Response(BodyMetricSerializer(metric).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        metric = services.update_body_metric(self.get_object(), request.user, request.data)
        return Response(BodyMetricSerializer(metric).data)
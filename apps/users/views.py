from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users import services
from apps.users.serializers import MeSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        data = services.register_user(request.data)
        return Response(data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        email = request.data.get("email", "")
        password = request.data.get("password", "")
        tokens = services.login_user(email, password)
        return Response(tokens, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        services.logout_user(request.data.get("refresh", ""))
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(MeSerializer(request.user).data)

    def patch(self, request: Request) -> Response:
        user = services.update_me(request.user, request.data)
        return Response(MeSerializer(user).data)
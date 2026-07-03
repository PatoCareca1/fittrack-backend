from rest_framework.permissions import BasePermission

from apps.users.models import AccountType


class IsProfessional(BasePermission):
    message = "Disponível apenas para personal trainers e nutricionistas."

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.account_type != AccountType.USER
        )

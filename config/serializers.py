from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.users.models import AccountType, User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    account_type = serializers.ChoiceField(choices=AccountType.choices, default=AccountType.USER)

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "password", "account_type")

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "account_type")
        read_only_fields = fields
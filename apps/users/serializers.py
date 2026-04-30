from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.users.models import AccountType, Profile, User


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
        read_only_fields = ("id", "email", "account_type")


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = (
            "birth_date",
            "sex",
            "height_cm",
            "goal",
            "activity_level",
            "avatar",
            "professional_verified",
        )
        read_only_fields = ("professional_verified",)


class MeSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "account_type", "profile")
        read_only_fields = ("id", "email", "account_type")

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if profile_data:
            profile = instance.profile
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()
        return instance
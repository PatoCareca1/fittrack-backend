from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class AccountType(models.TextChoices):
    USER = "user", "Usuário"
    PERSONAL = "personal", "Personal Trainer"
    NUTRITIONIST = "nutritionist", "Nutricionista"


class Sex(models.TextChoices):
    MALE = "M", "Masculino"
    FEMALE = "F", "Feminino"


class Goal(models.TextChoices):
    WEIGHT_LOSS = "weight_loss", "Emagrecimento"
    HYPERTROPHY = "hypertrophy", "Hipertrofia"
    MAINTENANCE = "maintenance", "Manutenção"
    GENERAL_HEALTH = "general_health", "Saúde geral"


class ActivityLevel(models.TextChoices):
    SEDENTARY = "sedentary", "Sedentário"
    LIGHT = "light", "Levemente ativo"
    MODERATE = "moderate", "Moderadamente ativo"
    INTENSE = "intense", "Muito ativo"
    VERY_INTENSE = "very_intense", "Extremamente ativo"


ACTIVITY_FACTORS = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.LIGHT: 1.375,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.INTENSE: 1.725,
    ActivityLevel.VERY_INTENSE: 1.9,
}


class FitTrackUserManager(UserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("E-mail é obrigatório.")
        email = self.normalize_email(email)
        extra_fields.setdefault("username", email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    email = models.EmailField(unique=True)
    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        default=AccountType.USER,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = FitTrackUserManager()

    def __str__(self):
        return self.email


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    birth_date = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=1, choices=Sex.choices, null=True, blank=True)
    height_cm = models.PositiveSmallIntegerField(null=True, blank=True)
    goal = models.CharField(max_length=20, choices=Goal.choices, default=Goal.GENERAL_HEALTH)
    activity_level = models.CharField(
        max_length=20,
        choices=ActivityLevel.choices,
        default=ActivityLevel.SEDENTARY,
    )
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True)
    professional_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user.email}"

    @property
    def activity_factor(self) -> float:
        return ACTIVITY_FACTORS.get(self.activity_level, 1.2)
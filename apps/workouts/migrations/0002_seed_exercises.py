# Base de exercícios pré-cadastrada (Bloco 2 do roadmap). icon_slug referencia
# o ícone SVG de grupo muscular no app — nunca fotos (README raiz, seção 6.6).
from django.db import migrations

EXERCISES = [
    # (nome, muscle_group)
    ("Supino Reto", "chest"),
    ("Supino Inclinado", "chest"),
    ("Supino Declinado", "chest"),
    ("Supino com Halteres", "chest"),
    ("Crucifixo", "chest"),
    ("Crossover", "chest"),
    ("Flexão de Braço", "chest"),
    ("Puxada Frontal", "back"),
    ("Barra Fixa", "back"),
    ("Remada Curvada", "back"),
    ("Remada Baixa", "back"),
    ("Remada Unilateral", "back"),
    ("Levantamento Terra", "back"),
    ("Pulldown", "back"),
    ("Desenvolvimento Militar", "shoulders"),
    ("Desenvolvimento com Halteres", "shoulders"),
    ("Elevação Lateral", "shoulders"),
    ("Elevação Frontal", "shoulders"),
    ("Crucifixo Inverso", "shoulders"),
    ("Encolhimento", "shoulders"),
    ("Rosca Direta", "biceps"),
    ("Rosca Alternada", "biceps"),
    ("Rosca Martelo", "biceps"),
    ("Rosca Scott", "biceps"),
    ("Rosca Concentrada", "biceps"),
    ("Tríceps Pulley", "triceps"),
    ("Tríceps Testa", "triceps"),
    ("Tríceps Corda", "triceps"),
    ("Tríceps Francês", "triceps"),
    ("Mergulho", "triceps"),
    ("Rosca de Punho", "forearms"),
    ("Prancha", "core"),
    ("Abdominal Supra", "core"),
    ("Abdominal Infra", "core"),
    ("Abdominal Oblíquo", "core"),
    ("Elevação de Pernas", "core"),
    ("Elevação Pélvica", "glutes"),
    ("Cadeira Abdutora", "glutes"),
    ("Coice no Cabo", "glutes"),
    ("Agachamento Livre", "quads"),
    ("Agachamento no Smith", "quads"),
    ("Leg Press", "quads"),
    ("Cadeira Extensora", "quads"),
    ("Afundo", "quads"),
    ("Agachamento Búlgaro", "quads"),
    ("Mesa Flexora", "hamstrings"),
    ("Cadeira Flexora", "hamstrings"),
    ("Stiff", "hamstrings"),
    ("Panturrilha em Pé", "calves"),
    ("Panturrilha Sentado", "calves"),
    ("Esteira", "cardio"),
    ("Bicicleta Ergométrica", "cardio"),
    ("Escada", "cardio"),
    ("Corda", "cardio"),
    ("Burpee", "full_body"),
    ("Clean and Press", "full_body"),
]


def _slugify(name: str) -> str:
    table = str.maketrans("áàãâéêíóôõúüç", "aaaaeeiooouuc")
    return name.lower().translate(table).replace(" ", "-")


def seed(apps, schema_editor):
    Exercise = apps.get_model("workouts", "Exercise")
    existing = set(Exercise.objects.values_list("icon_slug", flat=True))
    Exercise.objects.bulk_create(
        Exercise(name=name, muscle_group=group, icon_slug=_slugify(name))
        for name, group in EXERCISES
        if _slugify(name) not in existing
    )


def unseed(apps, schema_editor):
    Exercise = apps.get_model("workouts", "Exercise")
    Exercise.objects.filter(icon_slug__in=[_slugify(n) for n, _ in EXERCISES]).delete()


class Migration(migrations.Migration):
    dependencies = [("workouts", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]

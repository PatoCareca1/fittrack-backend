# Seed inicial com alimentos comuns da tabela TACO (4ª ed., valores por 100g).
# O sync incremental completo TACO + Open Food Facts via Celery (README raiz,
# seção 4.6) substituirá/complementará esta base.
from django.db import migrations

TACO_FOODS = [
    # (nome, kcal, proteína, carboidrato, gordura)
    ("Arroz branco cozido", 128, 2.5, 28.1, 0.2),
    ("Arroz integral cozido", 124, 2.6, 25.8, 1.0),
    ("Feijão carioca cozido", 76, 4.8, 13.6, 0.5),
    ("Feijão preto cozido", 77, 4.5, 14.0, 0.5),
    ("Peito de frango grelhado", 159, 32.0, 0.0, 2.5),
    ("Frango sobrecoxa assada", 211, 26.0, 0.0, 11.0),
    ("Carne bovina patinho grelhado", 219, 35.9, 0.0, 7.3),
    ("Carne bovina acém moído cozido", 212, 26.7, 0.0, 10.9),
    ("Tilápia grelhada", 96, 20.1, 0.0, 1.7),
    ("Ovo de galinha cozido", 146, 13.3, 0.6, 9.5),
    ("Ovo mexido", 208, 13.3, 1.4, 16.5),
    ("Batata doce cozida", 77, 0.6, 18.4, 0.1),
    ("Batata inglesa cozida", 52, 1.2, 11.9, 0.0),
    ("Mandioca cozida", 125, 0.6, 30.1, 0.3),
    ("Macarrão cozido", 111, 3.7, 23.0, 0.6),
    ("Pão francês", 300, 8.0, 58.6, 3.1),
    ("Pão de forma integral", 253, 9.4, 49.9, 3.7),
    ("Tapioca (goma hidratada)", 240, 0.0, 60.0, 0.0),
    ("Aveia em flocos", 394, 13.9, 66.6, 8.5),
    ("Banana prata", 98, 1.3, 26.0, 0.1),
    ("Maçã", 56, 0.3, 15.2, 0.0),
    ("Mamão papaia", 40, 0.5, 10.4, 0.1),
    ("Laranja", 37, 1.0, 8.9, 0.1),
    ("Abacate", 96, 1.2, 6.0, 8.4),
    ("Leite integral", 61, 3.2, 4.5, 3.3),
    ("Leite desnatado", 35, 3.4, 5.0, 0.2),
    ("Iogurte natural", 51, 4.1, 1.9, 3.0),
    ("Queijo minas frescal", 264, 17.4, 3.2, 20.2),
    ("Queijo muçarela", 330, 22.6, 3.0, 25.2),
    ("Requeijão cremoso", 257, 9.6, 2.4, 23.4),
    ("Brócolis cozido", 25, 2.1, 4.4, 0.5),
    ("Alface", 11, 1.3, 1.7, 0.2),
    ("Tomate", 15, 1.1, 3.1, 0.2),
    ("Cenoura crua", 34, 1.3, 7.7, 0.2),
    ("Azeite de oliva", 884, 0.0, 0.0, 100.0),
    ("Castanha de caju torrada", 570, 18.5, 29.1, 46.3),
    ("Amendoim torrado", 606, 22.5, 18.7, 54.0),
    ("Whey protein (média)", 400, 80.0, 8.0, 6.0),
]


def seed(apps, schema_editor):
    Food = apps.get_model("diet", "Food")
    Food.objects.bulk_create(
        Food(
            name=name,
            source="taco",
            kcal=kcal,
            protein_g=protein,
            carbs_g=carbs,
            fat_g=fat,
        )
        for name, kcal, protein, carbs, fat in TACO_FOODS
    )


def unseed(apps, schema_editor):
    Food = apps.get_model("diet", "Food")
    Food.objects.filter(source="taco", owner__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("diet", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]

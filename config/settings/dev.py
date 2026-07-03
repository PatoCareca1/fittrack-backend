from .base import *

DEBUG = True

# "*" apenas em dev: permite acesso do emulador (10.0.2.2) e do celular físico
# pelo IP do notebook na rede local (runserver 0.0.0.0:8000).
ALLOWED_HOSTS = ["*"]

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
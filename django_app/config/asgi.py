"""ASGI entrypoint — the production process model (decision OV2=B).

Dockerfile Stage 2 boots ``gunicorn config.asgi:application -k
uvicorn.workers.UvicornWorker`` (gunicorn retained over Codex's objection;
uvicorn ASGI worker swap). NinjaAPI is fully async-capable on ASGI.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()

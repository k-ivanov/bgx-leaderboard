"""WSGI entrypoint (kept for completeness; the prod process model is ASGI).

Decision OV2=B: gunicorn is retained. The Dockerfile boots gunicorn with the
uvicorn ASGI worker against ``config.asgi:application`` — NOT this WSGI app.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

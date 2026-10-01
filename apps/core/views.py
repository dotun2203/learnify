from django.core.cache import cache
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


@extend_schema(exclude=True)
class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        checks = {}
        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1")
            checks["database"] = "ok"
        except Exception:  # noqa: BLE001
            checks["database"] = "error"
        try:
            cache.set("health:ping", "1", 5)
            checks["cache"] = "ok" if cache.get("health:ping") == "1" else "error"
        except Exception:  # noqa: BLE001
            checks["cache"] = "error"
        healthy = all(v == "ok" for v in checks.values())
        return Response({"status": "ok" if healthy else "degraded", **checks},
                        status=200 if healthy else 503)

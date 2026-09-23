from fastapi import APIRouter, Response
from app.services.metrics import prometheus_metrics

router = APIRouter(tags=["operations"])


@router.get("/actuator/health")
def health():
    return {"status": "UP", "service": "DEALTHEWHEELS"}


@router.get("/actuator/metrics")
def metrics():
    body, content_type = prometheus_metrics()
    return Response(content=body, media_type=content_type)

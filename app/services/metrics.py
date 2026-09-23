from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

ALLOCATIONS = Counter("dealthewheels_allocations_total", "Trips allocated", ["trip_type"])
REJECTIONS = Counter("dealthewheels_rejections_total", "Trip rejections")
DRIFT = Gauge("dealthewheels_vendor_shortfall", "Current vendor shortfall", ["vendor_id", "zone_id", "trip_type"])


def prometheus_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST

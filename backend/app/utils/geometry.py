from __future__ import annotations

# Ngưỡng giản lược hình học theo mức zoom, đơn vị độ (EPSG:4326).
# 0.00001 độ ~ 1,1 m. Zoom càng xa càng giản lược mạnh vì màn hình
# không thể hiện nổi chi tiết ở mức đó.
SIMPLIFY_BY_ZOOM = (
    (17, 0.0),
    (15, 0.000008),
    (13, 0.000030),
    (11, 0.000080),
    (0, 0.000200),
)


def simplify_for_zoom(zoom: int) -> float:
    """Trả về ngưỡng giản lược hình học ứng với mức zoom."""
    for min_zoom, tolerance in SIMPLIFY_BY_ZOOM:
        if zoom >= min_zoom:
            return tolerance
    return 0.0

from __future__ import annotations

from ..repositories import ranh_thon_repository


def get_ranh_gioi_thon(ma_xa: str):
    ma_xa = ma_xa.strip() or None
    return ranh_thon_repository.get_ranh_gioi_thon(ma_xa)

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

MPLIS_URL = (
    "https://dla.mplis.gov.vn/dc/LamSachDuLieuAjax/"
    "GetThongKePhanLoaiThuaDatChiTiet"
)

# Thử length lớn dần giảm dần khi bắt đầu job quét cả xã, dùng giá trị lớn
# nhất mà server chấp nhận (trả JSON hợp lệ) để giảm số request — không giả
# định cứng rằng subLength=3000 nghĩa là length=3000 luôn được hỗ trợ.
PAGE_LENGTH_CANDIDATES = (1000, 500, 100, 10)

# Lỗi mạng tạm thời: thử lại tối đa 4 lần, delay tăng dần. Lỗi phiên đăng
# nhập (401/403/redirect/HTML thay vì JSON) KHÔNG retry — dừng ngay.
RETRY_DELAYS = (1, 2, 4, 8)

SESSION_ERROR_MESSAGE = (
    "Cookie hoặc Request Verification Token không hợp lệ hoặc đã hết hạn."
)

BATCH_UPSERT_RPC = "batch_upsert_dong_bo_du_lieu"
UPSERT_BATCH_SIZE = 500

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class MplisSessionError(Exception):
    """Cookie/token MPLIS không hợp lệ hoặc đã hết hạn — dừng job ngay,
    không retry."""


class MplisRequestError(Exception):
    """Lỗi khác khi gọi MPLIS (mạng, HTTP lỗi...) — đã hết số lần thử lại."""


# =========================================================
# GỌI MPLIS
# =========================================================


def _headers(token: str, cookie: str) -> dict[str, str]:
    return {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://dla.mplis.gov.vn",
        "Referer": "https://dla.mplis.gov.vn/dc/",
        "__requestverificationtoken": token,
        "Cookie": cookie,
        "User-Agent": _USER_AGENT,
    }


def _payload(ma_xa: str, so_to: str, so_thua: str, start: int, length: int) -> dict[str, str]:
    return {
        "traCuu[soThuTuThua]": so_thua or "",
        "traCuu[soHieuToBanDo]": so_to or "",
        "traCuu[soPhatHanh]": "",
        "traCuu[hoTenChu]": "",
        "traCuu[phanLoai]": "-1",
        "traCuu[type]": "-1",
        "traCuu[loaiChu]": "-1",
        "traCuu[tuNgay]": "",
        "traCuu[denNgay]": "",
        "traCuu[query]": "",
        "traCuu[xaId]": ma_xa,
        "traCuu[huyenId]": "0",
        "traCuu[tinhId]": "66",
        "start": str(start),
        "length": str(length),
        "exportWard": "false",
        "subLength": "3000",
        "sort[Field]": "_id",
        "sort[Direction]": "1",
    }


def _request_once(
    ma_xa: str, so_to: str, so_thua: str, start: int, length: int, token: str, cookie: str
) -> dict[str, Any]:
    """1 lần gọi MPLIS, không retry. Ném MplisSessionError nếu phát hiện
    phiên đăng nhập hết hạn (401/403/redirect/HTML thay vì JSON), ném
    MplisRequestError cho các lỗi HTTP/mạng khác (caller quyết định retry)."""
    try:
        response = requests.post(
            MPLIS_URL,
            headers=_headers(token, cookie),
            data=_payload(ma_xa, so_to, so_thua, start, length),
            timeout=30,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise MplisRequestError(str(exc)) from exc

    if response.status_code in (401, 403) or 300 <= response.status_code < 400:
        raise MplisSessionError(SESSION_ERROR_MESSAGE)

    if not response.ok:
        raise MplisRequestError(f"MPLIS trả về HTTP {response.status_code}")

    content_type = response.headers.get("Content-Type", "")
    if "json" not in content_type.lower():
        # MPLIS trả trang HTML (thường là trang đăng nhập) thay vì JSON khi
        # cookie/token sai hoặc hết hạn.
        raise MplisSessionError(SESSION_ERROR_MESSAGE)

    try:
        body = response.json()
    except ValueError as exc:
        raise MplisSessionError(SESSION_ERROR_MESSAGE) from exc

    if not isinstance(body, dict) or body.get("success") is False:
        raise MplisRequestError("MPLIS từ chối yêu cầu (success=false).")

    return body


def fetch_page(
    ma_xa: str, so_to: str, so_thua: str, start: int, length: int, token: str, cookie: str
) -> dict[str, Any]:
    """Gọi 1 trang MPLIS, tự retry lỗi mạng/HTTP tạm thời (tối đa 4 lần,
    delay tăng dần). Lỗi phiên đăng nhập không retry, ném ngay."""
    last_error: Exception | None = None

    for delay in (0, *RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        try:
            return _request_once(ma_xa, so_to, so_thua, start, length, token, cookie)
        except MplisSessionError:
            raise
        except MplisRequestError as exc:
            last_error = exc
            continue

    raise MplisRequestError(f"Không kết nối được MPLIS sau nhiều lần thử: {last_error}")


def probe_page_length(
    ma_xa: str, so_to: str, so_thua: str, token: str, cookie: str
) -> tuple[dict[str, Any], int]:
    """Thử length giảm dần trong PAGE_LENGTH_CANDIDATES, trả về (response
    trang đầu tiên, length đã dùng). Dùng luôn kết quả này làm trang đầu —
    không tốn thêm request."""
    last_error: Exception | None = None

    for length in PAGE_LENGTH_CANDIDATES:
        try:
            body = fetch_page(ma_xa, so_to, so_thua, 0, length, token, cookie)
        except MplisSessionError:
            raise
        except MplisRequestError as exc:
            last_error = exc
            continue

        data = body.get("data")
        if isinstance(data, list):
            return body, length

        last_error = MplisRequestError(f"length={length}: response không có mảng 'data' hợp lệ")

    raise MplisRequestError(f"Không tìm được page length MPLIS chấp nhận: {last_error}")


# =========================================================
# MAPPING MPLIS -> public.dong_bo_du_lieu
# =========================================================


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def map_record(row: dict[str, Any]) -> dict[str, Any] | None:
    """Map 1 record MPLIS sang object dùng để UPSERT dong_bo_du_lieu.
    Trả None nếu thiếu khóa (xaId/soHieuToBanDo/soThuTuThua) hoặc không ép
    được kiểu số — record đó tính là lỗi, không ghi."""
    xa_id = row.get("xaId")
    so_to = _safe_int(row.get("soHieuToBanDo"))
    so_thua = _safe_int(row.get("soThuTuThua"))

    if xa_id is None or so_to is None or so_thua is None:
        return None

    da_xuat = row.get("daXuatSoDiaChinhDienTu")
    dong_bo_3_khoi = row.get("daDongBoBaKhoiThongTin")
    trang_thai_xac_thuc = row.get("trangThaiXacThucChu")
    van_hanh = row.get("duLieuDangVanHanh247")
    nhom_1 = row.get("thongTinDangKyDapUngNhom1")

    return {
        "ma_xa": str(xa_id),
        "so_to": so_to,
        "so_thua": so_thua,
        "da_xuat_so_dia_chinh_dien_tu": da_xuat is True,
        "chua_xuat_so_dia_chinh_dien_tu": da_xuat is False,
        "dong_bo_3_khoi": dong_bo_3_khoi is True,
        "khong_dong_bo_3_khoi": dong_bo_3_khoi is False,
        "chi_co_du_lieu_thuoc_tinh": row.get("chiCoDuLieuThuocTinh") is True,
        "khop_csdlqg_dan_cu": trang_thai_xac_thuc == 1,
        "chua_khop_csdlqg_dan_cu": trang_thai_xac_thuc == 0,
        "khong_xac_dinh_csdlqg_dan_cu": trang_thai_xac_thuc not in (0, 1),
        "van_hanh_24_7": van_hanh is True,
        "khong_van_hanh_24_7": van_hanh is False,
        "phan_loai_ke_hoach_2959": "Nhóm 1" if nhom_1 is True else "Nhóm 2",
    }


# =========================================================
# GHI SUPABASE (batch UPSERT — có thì UPDATE, chưa có thì INSERT)
# =========================================================


def batch_upsert_supabase(
    base_url: str, headers: dict[str, str], rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Gọi RPC batch_upsert_dong_bo_du_lieu, trả về danh sách
    {ma_xa, so_to, so_thua, was_insert} đã ghi được. `rows` không được
    chứa khóa (ma_xa, so_to, so_thua) trùng nhau — insert...on conflict
    không update được cùng 1 dòng 2 lần trong 1 câu lệnh, cả batch sẽ
    lỗi nếu trùng (caller phải tự loại trùng trước, xem _process_page)."""
    if not rows:
        return []

    response = requests.post(
        f"{base_url}/rest/v1/rpc/{BATCH_UPSERT_RPC}",
        headers={**headers, "Content-Type": "application/json"},
        json={"p_rows": rows},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def update_single_parcel(
    ma_xa: str,
    so_to: str,
    so_thua: str,
    token: str,
    cookie: str,
    base_url: str,
    headers: dict[str, str],
) -> dict[str, Any]:
    """Chế độ 1 thửa — chạy đồng bộ trong 1 request, không qua job."""
    body = fetch_page(ma_xa, so_to, so_thua, 0, 10, token, cookie)
    data = body.get("data") or []
    if not data:
        return {"status": "not_found_mplis"}

    so_to_int = _safe_int(so_to)
    so_thua_int = _safe_int(so_thua)

    match = next(
        (
            row
            for row in data
            if str(row.get("xaId")) == str(ma_xa)
            and _safe_int(row.get("soHieuToBanDo")) == so_to_int
            and _safe_int(row.get("soThuTuThua")) == so_thua_int
        ),
        data[0],
    )

    mapped = map_record(match)
    if mapped is None:
        return {"status": "not_found_mplis"}

    written = batch_upsert_supabase(base_url, headers, [mapped])
    if not written:
        # Không lẽ xảy ra (upsert luôn ghi được 1 dòng), nhưng vẫn xử lý
        # rõ ràng thay vì để lỗi mơ hồ.
        return {"status": "error", "mapped": mapped}

    was_insert = bool(written[0].get("was_insert"))
    return {"status": "inserted" if was_insert else "updated", "mapped": mapped}


# =========================================================
# JOB NỀN — CẬP NHẬT CẢ XÃ
#
# Lưu ý: JobState KHÔNG BAO GIỜ giữ Cookie/token — chỉ nhận qua tham số
# hàm, sống trong local scope của thread nền, không thoát ra registry
# _JOBS (registry chỉ để polling tiến độ). Giả định backend chạy 1
# worker process (xem render.yaml: `gunicorn run:app` không có
# --workers) — nếu sau này tăng số worker, job in-memory này sẽ không
# còn thấy được từ worker khác, cần đổi sang lưu trạng thái ngoài
# (Redis/DB) trước khi tăng worker.
# =========================================================


@dataclass
class JobState:
    job_id: str
    ma_xa: str
    status: str = "running"  # running | done | error | session_expired
    total: int = 0
    processed: int = 0
    updated: int = 0
    inserted: int = 0
    duplicates: int = 0
    errors: int = 0
    message: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            percent = round((self.processed / self.total * 100), 2) if self.total else 0.0
            return {
                "job_id": self.job_id,
                "ma_xa": self.ma_xa,
                "status": self.status,
                "total": self.total,
                "processed": self.processed,
                "updated": self.updated,
                "inserted": self.inserted,
                "duplicates": self.duplicates,
                "errors": self.errors,
                "percent": percent,
                "message": self.message,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
            }


_JOBS: dict[str, JobState] = {}
_JOBS_LOCK = threading.Lock()
_ACTIVE_JOB_ID: str | None = None


def get_job(job_id: str) -> JobState | None:
    with _JOBS_LOCK:
        return _JOBS.get(job_id)


def _finish_job(job: JobState, status: str, message: str) -> None:
    global _ACTIVE_JOB_ID
    with job._lock:  # noqa: SLF001 - cùng module, JobState là dataclass nội bộ
        job.status = status
        job.message = message
        job.finished_at = datetime.now(timezone.utc).isoformat()
    with _JOBS_LOCK:
        if _ACTIVE_JOB_ID == job.job_id:
            _ACTIVE_JOB_ID = None


def _process_page(
    job: JobState,
    data: list[dict[str, Any]],
    seen_keys: set[tuple[str, int, int]],
    base_url: str,
    headers: dict[str, str],
) -> None:
    batch: list[dict[str, Any]] = []
    batch_keys: list[tuple[str, int, int]] = []

    for row in data:
        mapped = map_record(row)
        if mapped is None:
            with job._lock:  # noqa: SLF001
                job.errors += 1
            continue

        key = (mapped["ma_xa"], mapped["so_to"], mapped["so_thua"])
        if key in seen_keys:
            with job._lock:  # noqa: SLF001
                job.duplicates += 1
            continue

        seen_keys.add(key)
        batch.append(mapped)
        batch_keys.append(key)

    for start in range(0, len(batch), UPSERT_BATCH_SIZE):
        sub_batch = batch[start : start + UPSERT_BATCH_SIZE]
        sub_keys = batch_keys[start : start + UPSERT_BATCH_SIZE]

        try:
            written = batch_upsert_supabase(base_url, headers, sub_batch)
        except requests.RequestException:
            logger.exception(
                "batch_upsert_dong_bo_du_lieu lỗi (ma_xa=%s, %d dòng)",
                job.ma_xa,
                len(sub_batch),
            )
            with job._lock:  # noqa: SLF001
                job.errors += len(sub_batch)
            continue

        insert_flags = {
            (str(w.get("ma_xa")), w.get("so_to"), w.get("so_thua")): bool(w.get("was_insert"))
            for w in written
        }
        with job._lock:  # noqa: SLF001
            for key in sub_keys:
                if key not in insert_flags:
                    # Không nên xảy ra (upsert luôn ghi được) — coi là lỗi
                    # thay vì âm thầm bỏ qua để không mất dấu vết.
                    job.errors += 1
                elif insert_flags[key]:
                    job.inserted += 1
                else:
                    job.updated += 1


def _run_ward_job(
    job: JobState,
    ma_xa: str,
    so_to: str,
    so_thua: str,
    token: str,
    cookie: str,
    base_url: str,
    headers: dict[str, str],
) -> None:
    try:
        body, length = probe_page_length(ma_xa, so_to, so_thua, token, cookie)
    except MplisSessionError as exc:
        _finish_job(job, "session_expired", str(exc))
        return
    except MplisRequestError as exc:
        _finish_job(job, "error", str(exc))
        return

    total = _safe_int(body.get("recordsFiltered")) or 0
    with job._lock:  # noqa: SLF001
        job.total = total

    seen_keys: set[tuple[str, int, int]] = set()
    start = 0

    try:
        while True:
            data = body.get("data") or []
            if not data:
                break

            _process_page(job, data, seen_keys, base_url, headers)

            received = len(data)
            next_start = start + received

            new_total = _safe_int(body.get("recordsFiltered"))
            with job._lock:  # noqa: SLF001
                job.processed += received
                if new_total is not None:
                    job.total = new_total
                    total = new_total

            if next_start >= total:
                break

            start = next_start
            body = fetch_page(ma_xa, so_to, so_thua, start, length, token, cookie)
    except MplisSessionError as exc:
        _finish_job(job, "session_expired", str(exc))
        return
    except MplisRequestError as exc:
        _finish_job(job, "error", str(exc))
        return
    except Exception as exc:  # noqa: BLE001 - job nền, phải luôn kết thúc rõ trạng thái
        logger.exception("Job MPLIS lỗi không xác định: ma_xa=%s", ma_xa)
        _finish_job(job, "error", f"Lỗi không xác định: {exc}")
        return

    _finish_job(job, "done", "")


def try_start_ward_job(
    ma_xa: str,
    so_to: str,
    so_thua: str,
    token: str,
    cookie: str,
    base_url: str,
    headers: dict[str, str],
) -> JobState | None:
    """Tạo job mới và chạy nền bằng thread. Trả None nếu đã có job khác
    đang chạy (chỉ cho phép 1 job cập nhật-cả-xã cùng lúc)."""
    global _ACTIVE_JOB_ID

    with _JOBS_LOCK:
        active = _JOBS.get(_ACTIVE_JOB_ID) if _ACTIVE_JOB_ID else None
        if active is not None and active.status == "running":
            return None

        job = JobState(job_id=uuid.uuid4().hex, ma_xa=ma_xa)
        _JOBS[job.job_id] = job
        _ACTIVE_JOB_ID = job.job_id

    thread = threading.Thread(
        target=_run_ward_job,
        args=(job, ma_xa, so_to, so_thua, token, cookie, base_url, headers),
        daemon=True,
    )
    thread.start()
    return job

from __future__ import annotations

import json
import re
import threading

import psycopg2
import psycopg2.errors
import psycopg2.extras
import psycopg2.pool
import requests
from flask import current_app, jsonify

# =========================================================
# LỚP REPOSITORY GỐC — MỌI TRUY VẤN POSTGRES ĐI QUA ĐÂY.
# Routes/services không tự mở connection/psycopg2 riêng.
#
# Trước đây file này gọi PostgREST/RPC của Supabase qua HTTP. Giờ backend
# nói chuyện thẳng với Postgres local bằng psycopg2, nhưng GIỮ NGUYÊN chữ
# ký + quy ước trả về của từng hàm public bên dưới (rest_request/call_rpc/
# upsert_to_supabase/upsert_thua_dat_diff) — nhờ vậy các repository khác
# (parcel/gcn/nhom4/ranh_thon/ban_do_nen) và import_service.py không phải
# sửa dòng nào. Toàn bộ logic không gian (ST_*, so sánh geom, cache...) vẫn
# nằm nguyên trong các hàm PL/pgSQL của supabase/schema.sql — file này chỉ
# đổi cách GỌI các hàm đó (SELECT trực tiếp thay vì HTTP RPC).
# =========================================================

_pool_lock = threading.Lock()
_pools: dict[str, "psycopg2.pool.ThreadedConnectionPool"] = {}

_SET_RETURNING_CACHE: dict[str, bool] = {}
_COLUMN_TYPE_CACHE: dict[tuple[str, str], str | None] = {}

_ORDER_RE = re.compile(r"^(?P<col>[a-zA-Z0-9_]+)\.(?P<dir>asc|desc)$")
_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def get_base_url() -> str:
    return current_app.config.get("DATABASE_URL", "")


def missing_base_url_response():
    return jsonify({"error": "Thiếu DATABASE_URL trong backend/.env"}), 500


def _get_pool():
    dsn = current_app.config.get("DATABASE_URL", "")
    if not dsn:
        raise RuntimeError("Thiếu DATABASE_URL trong backend/.env")

    with _pool_lock:
        pool = _pools.get(dsn)
        if pool is None:
            pool = psycopg2.pool.ThreadedConnectionPool(1, 20, dsn)
            _pools[dsn] = pool
        return pool


class _CursorCtx:
    """Lấy connection từ pool, tạo RealDictCursor (mô phỏng JSON object của
    PostgREST), đặt statement_timeout riêng cho transaction này, rồi
    commit/rollback + trả connection về pool khi thoát."""

    def __init__(self, timeout: float | None = None):
        self.timeout = timeout

    def __enter__(self):
        self.pool = _get_pool()
        self.conn = self.pool.getconn()
        self.conn.autocommit = False
        self.cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if self.timeout:
            self.cur.execute(
                "SET LOCAL statement_timeout = %s", (int(self.timeout * 1000),)
            )
        return self.cur

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
        finally:
            self.cur.close()
            self.pool.putconn(self.conn)
        return False


class _FakeResponse:
    """Mô phỏng đúng phần bề mặt của requests.Response mà các repository
    đang dùng (.ok/.status_code/.text/.json()/.raise_for_status()) — để
    _json_or_error() ở từng repository không phải sửa gì."""

    def __init__(self, status_code: int, data):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._data = data
        self.text = "" if data is None else json.dumps(data, ensure_ascii=False, default=str)

    def json(self):
        return self._data

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(self.text or "Lỗi cơ sở dữ liệu")


def _pg_error_response(exc: Exception):
    if isinstance(exc, psycopg2.errors.QueryCanceled):
        return (
            jsonify(
                {
                    "error": (
                        "Truy vấn vượt quá thời gian cho phép. "
                        "Hãy phóng to bản đồ hoặc giảm số thửa mỗi lô."
                    )
                }
            ),
            504,
        )

    message = str(exc).strip() or "Lỗi cơ sở dữ liệu không rõ nguyên nhân"
    current_app.logger.error("Lỗi Postgres: %s", message)
    return jsonify({"error": message}), 502


def _adapt_param(value):
    if isinstance(value, dict):
        return psycopg2.extras.Json(value)
    return value


def _is_set_returning(cur, function_name: str) -> bool:
    if function_name not in _SET_RETURNING_CACHE:
        cur.execute(
            "select proretset from pg_proc "
            "where proname = %s and pronamespace = 'public'::regnamespace "
            "limit 1",
            (function_name,),
        )
        row = cur.fetchone()
        _SET_RETURNING_CACHE[function_name] = bool(row and row["proretset"])
    return _SET_RETURNING_CACHE[function_name]


def _column_type(cur, table: str, column: str) -> str | None:
    key = (table, column)
    if key not in _COLUMN_TYPE_CACHE:
        cur.execute(
            "select data_type from information_schema.columns "
            "where table_schema = 'public' and table_name = %s and column_name = %s",
            (table, column),
        )
        row = cur.fetchone()
        _COLUMN_TYPE_CACHE[key] = row["data_type"] if row else None
    return _COLUMN_TYPE_CACHE[key]


def _coerce_value(raw: str, col_type: str | None):
    if col_type == "boolean":
        return raw.strip().lower() == "true"
    if col_type in ("integer", "bigint", "smallint"):
        return int(raw)
    if col_type in ("double precision", "real", "numeric"):
        return float(raw)
    return raw


def _check_ident(name: str, what: str) -> str:
    if not _IDENT_RE.match(name):
        raise ValueError(f"Tên {what} không hợp lệ: {name}")
    return name


def call_rpc(function_name: str, payload: dict, timeout: int = 30):
    """
    Gọi hàm Postgres (trước đây là RPC Supabase).

    Trả về (ket_qua, None) khi thành công, hoặc (None, response_loi).
    """
    try:
        with _CursorCtx(timeout=timeout) as cur:
            is_set = _is_set_returning(cur, function_name)
            args_sql = ", ".join(f"{k} => %({k})s" for k in payload)
            params = {k: _adapt_param(v) for k, v in payload.items()}
            cur.execute(f"select * from public.{function_name}({args_sql})", params)

            if is_set:
                rows = [dict(r) for r in cur.fetchall()]
                return rows, None

            row = cur.fetchone()
            if row is None:
                return None, None
            values = list(row.values())
            return (values[0] if len(values) == 1 else dict(row)), None
    except RuntimeError as exc:
        return None, (jsonify({"error": str(exc)}), 500)
    except psycopg2.Error as exc:
        return None, _pg_error_response(exc)


def rest_request(
    method: str,
    table: str,
    *,
    params: dict | None = None,
    json_body=None,
    extra_headers: dict | None = None,
    timeout: int = 15,
):
    """Mô phỏng đúng tập cú pháp lọc PostgREST đang dùng trong code (select/
    order/limit/eq./in.(...)) bằng SQL thuần trên Postgres local. Trả
    (response, None) nếu chạy được (kể cả lỗi ràng buộc dữ liệu — caller tự
    kiểm response.ok), hoặc (None, response_loi) nếu lỗi cấu hình/DB."""
    params = dict(params or {})
    extra_headers = extra_headers or {}
    prefer = extra_headers.get("Prefer", "")
    return_representation = "return=representation" in prefer

    try:
        _check_ident(table, "bảng")
        with _CursorCtx(timeout=timeout) as cur:
            select_cols = "*"
            order_clause = ""
            limit_clause = ""
            where_parts: list[str] = []
            where_values: dict = {}

            for key, value in params.items():
                if key == "select":
                    select_cols = (
                        "*"
                        if value == "*"
                        else ", ".join(
                            _check_ident(c.strip(), "cột") for c in value.split(",")
                        )
                    )
                elif key == "order":
                    order_cols = []
                    for part in value.split(","):
                        m = _ORDER_RE.match(part.strip())
                        if not m:
                            raise ValueError(f"order chưa hỗ trợ: {part}")
                        order_cols.append(f'{_check_ident(m["col"], "cột")} {m["dir"]}')
                    order_clause = " order by " + ", ".join(order_cols)
                elif key == "limit":
                    limit_clause = " limit %(_limit)s"
                    where_values["_limit"] = int(value)
                else:
                    _check_ident(key, "cột")
                    col_type = _column_type(cur, table, key)
                    param_name = f"_f_{key}"
                    if isinstance(value, str) and value.startswith("in.("):
                        items = [
                            v.strip().strip('"')
                            for v in value[4:-1].split(",")
                            if v.strip() != ""
                        ]
                        where_values[param_name] = [
                            _coerce_value(v, col_type) for v in items
                        ]
                        where_parts.append(f"{key} = any(%({param_name})s)")
                    elif isinstance(value, str) and value.startswith("eq."):
                        where_values[param_name] = _coerce_value(value[3:], col_type)
                        where_parts.append(f"{key} = %({param_name})s")
                    else:
                        raise ValueError(f"Toán tử lọc chưa hỗ trợ cho {key}: {value}")

            where_clause = (" where " + " and ".join(where_parts)) if where_parts else ""

            if method == "GET":
                sql = f"select {select_cols} from public.{table}{where_clause}{order_clause}{limit_clause}"
                cur.execute(sql, where_values)
                return _FakeResponse(200, [dict(r) for r in cur.fetchall()]), None

            if method == "POST":
                rows = json_body if isinstance(json_body, list) else [json_body]
                if not rows:
                    return _FakeResponse(201, []), None
                columns = [_check_ident(c, "cột") for c in rows[0].keys()]
                col_sql = ", ".join(columns)
                values = [[_adapt_param(row.get(c)) for c in columns] for row in rows]
                returning = " returning *" if return_representation else ""
                sql = f"insert into public.{table} ({col_sql}) values %s{returning}"
                if return_representation:
                    result = psycopg2.extras.execute_values(cur, sql, values, fetch=True)
                    return _FakeResponse(201, [dict(r) for r in result]), None
                psycopg2.extras.execute_values(cur, sql, values)
                return _FakeResponse(201, []), None

            if method == "PATCH":
                set_cols = [_check_ident(c, "cột") for c in (json_body or {}).keys()]
                set_sql = ", ".join(f"{c} = %(_s_{c})s" for c in set_cols)
                for c in set_cols:
                    where_values[f"_s_{c}"] = _adapt_param(json_body[c])
                returning = " returning *" if return_representation else ""
                sql = f"update public.{table} set {set_sql}{where_clause}{returning}"
                cur.execute(sql, where_values)
                data = [dict(r) for r in cur.fetchall()] if return_representation else []
                return _FakeResponse(200, data), None

            if method == "DELETE":
                returning = f" returning {select_cols}" if return_representation else ""
                sql = f"delete from public.{table}{where_clause}{returning}"
                cur.execute(sql, where_values)
                data = [dict(r) for r in cur.fetchall()] if return_representation else []
                return _FakeResponse(200, data), None

            raise ValueError(f"Phương thức chưa hỗ trợ: {method}")
    except RuntimeError as exc:
        return None, (jsonify({"error": str(exc)}), 500)
    except psycopg2.Error as exc:
        return None, _pg_error_response(exc)
    except ValueError as exc:
        return None, (jsonify({"error": str(exc)}), 400)


def upsert_thua_dat_diff(rows: list[dict], batch_size: int = 200):
    """Upsert thua_dat qua hàm Postgres upsert_thua_dat_diff (so sánh trước
    khi ghi ngay trong Postgres) — chỉ ghi thửa thật sự đổi thay vì ghi lại
    toàn bộ thửa có trong file như upsert_to_supabase. Trả (số_thửa_đã_ghi,
    None) khi thành công, hoặc (None, response_loi)."""
    key_fields = ("ma_xa", "so_to", "so_thua")
    deduped = {}
    for row in rows:
        key = tuple(row.get(field) for field in key_fields)
        deduped[key] = row
    rows = list(deduped.values())

    changed = 0
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        count, error_response = call_rpc(
            "upsert_thua_dat_diff", {"p_rows": psycopg2.extras.Json(batch)}, timeout=60
        )
        if error_response:
            return None, error_response
        changed += int(count or 0)
    return changed, None


def upsert_to_supabase(
    table: str,
    on_conflict: str,
    resolution: str,
    rows: list[dict],
    batch_size: int = 200,
) -> int:
    # "ON CONFLICT DO UPDATE" lỗi nếu cùng 1 câu lệnh có 2 dòng trùng khóa
    # xung đột, nên phải loại trùng trước khi ghi — giữ lại dòng xuất hiện
    # sau cùng trong file nguồn (giống hành vi cũ).
    key_fields = [_check_ident(f.strip(), "cột") for f in on_conflict.split(",")]
    deduped = {}
    for row in rows:
        key = tuple(row.get(field) for field in key_fields)
        deduped[key] = row
    rows = list(deduped.values())
    if not rows:
        return 0

    columns = sorted({_check_ident(c, "cột") for row in rows for c in row.keys()})
    conflict_cols = ", ".join(key_fields)
    update_cols = [c for c in columns if c not in key_fields]
    update_sql = ", ".join(f"{c} = excluded.{c}" for c in update_cols)
    col_sql = ", ".join(columns)

    imported = 0
    try:
        with _CursorCtx(timeout=120) as cur:
            for start in range(0, len(rows), batch_size):
                batch = rows[start : start + batch_size]
                values = [[_adapt_param(row.get(c)) for c in columns] for row in batch]
                sql = (
                    f"insert into public.{table} ({col_sql}) values %s "
                    f"on conflict ({conflict_cols}) do update set {update_sql}"
                )
                psycopg2.extras.execute_values(cur, sql, values)
                imported += len(batch)
    except psycopg2.Error as exc:
        raise requests.RequestException(str(exc)) from exc

    return imported

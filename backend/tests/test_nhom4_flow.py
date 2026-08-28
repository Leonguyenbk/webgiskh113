"""Kiểm thử flow nhập biểu Nhóm 4 sau khi bỏ cơ chế nhom4_thua_da_nop.

Chạy trực tiếp bằng stdlib unittest (không cần pytest):

    python -m unittest backend.tests.test_nhom4_flow      # từ thư mục gốc repo
    python -m unittest discover -s backend/tests           # hoặc discover

Chỉ cần Flask + requests (đã có trong backend/requirements.txt). Toàn bộ
lớp truy cập Supabase được thay bằng một "du_lieu_gcn" giả trong bộ nhớ —
không gọi mạng.
"""

from __future__ import annotations

import io
import os
import re
import sys
import unittest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_DIR = os.path.abspath(os.path.join(BACKEND_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from flask import Flask  # noqa: E402

from app.repositories import nhom4_repository  # noqa: E402
from app.services import nhom4_service  # noqa: E402
from app.utils import nhom4_validation  # noqa: E402


def _norm(soto, sothua) -> str:
    # Bản sao rút gọn của public.normalize_so_text cho đầu vào số nguyên.
    return f"{int(soto)}"


class FakeDuLieuGcn:
    """du_lieu_gcn giả: danh sách dòng, mỗi dòng là dict như payload gửi
    lên PostgREST. Tự suy cột generated madvhc_soto_sothua."""

    def __init__(self):
        self.rows: list[dict] = []

    def key_of(self, row: dict) -> str:
        return (
            f"{str(row.get('madvhc', '')).strip()}"
            f"_{_norm(row.get('soto'), None)}"
            f"_{_norm(row.get('sothua'), None)}"
        )

    # ---- các hàm thay cho nhom4_repository ----
    def filter_existing_keys(self, keys):
        wanted = {k for k in keys if k}
        present = {self.key_of(r) for r in self.rows}
        return (wanted & present), None

    def insert_rows(self, rows):
        self.rows.extend(rows)
        return True, None

    def exists_key(self, key):
        return any(self.key_of(r) == key for r in self.rows), None

    # ---- mô phỏng cờ co_gcn của get_parcels_in_view / search_parcels ----
    def has_gcn(self, ma_xa, so_to, so_thua) -> bool:
        target = f"{ma_xa}_{_norm(so_to, None)}_{_norm(so_thua, None)}"
        return any(self.key_of(r) == target for r in self.rows)


class FakePdf:
    def __init__(self, name="hoso.pdf"):
        self.filename = name
        self.mimetype = "application/pdf"
        self.stream = io.BytesIO(b"%PDF-1.4 fake")

    def read(self):
        return b"%PDF-1.4 fake body"


def build_payload(so_to="10", so_thua="200", owners=None, loai_dat="ONT", thoi_han="Lâu dài"):
    if owners is None:
        owners = [
            {
                "ho_ten": "Nguyen Van A",
                "ngay_sinh": "1990",
                "gioi_tinh": "Nam",
                "cccd": "123456789012",
                "dia_chi_thuong_tru": "Thon 1",
                "phap_nhan": "Chủ sử dụng",
                "vai_tro_phap_nhan": "Chủ sử dụng",
            }
        ]
    return {
        "ma_xa": "26317",
        "ten_xa": "Xa Test",
        "doi_tuong": "Hộ gia đình, cá nhân",
        "che_do": "Chưa được cấp GCN",
        "owners": owners,
        "thua_list": [
            {
                "thua": {
                    "so_to": so_to,
                    "so_thua": so_thua,
                    "dien_tich_thua_dat": "100",
                    "dia_chi_thua_dat": "Thon 1",
                },
                "dat1": {
                    "loai_dat": loai_dat,
                    "dien_tich": "100",
                    "nguon_goc_su_dung": "Nhà nước giao có thu tiền",
                    "hinh_thuc_su_dung": "Sử dụng riêng",
                    "thoi_han_su_dung": thoi_han,
                },
                "dat2": None,
            }
        ],
    }


class Nhom4FlowTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.ctx = self.app.app_context()
        self.ctx.push()

        self.store = FakeDuLieuGcn()

        # Thay toàn bộ lớp Supabase bằng store giả.
        self._orig = {}
        for name, fn in {
            "filter_existing_keys": self.store.filter_existing_keys,
            "insert_rows": self.store.insert_rows,
            "exists_key": self.store.exists_key,
        }.items():
            self._orig[name] = getattr(nhom4_repository, name)
            setattr(nhom4_repository, name, fn)

        self._orig["list_phan_loai_by_xa"] = nhom4_repository.list_phan_loai_by_xa
        nhom4_repository.list_phan_loai_by_xa = lambda ma_xa: ({}, None)

        self._orig["get_phan_loai"] = nhom4_repository.get_phan_loai
        nhom4_repository.get_phan_loai = lambda ma_xa, so_to, so_thua: (None, None)

        # Không đụng tới Google Drive trong test.
        self._orig_bg = nhom4_service._upload_files_background
        nhom4_service._upload_files_background = lambda *a, **k: None

    def tearDown(self):
        for name, fn in self._orig.items():
            setattr(nhom4_repository, name, fn)
        nhom4_service._upload_files_background = self._orig_bg
        self.ctx.pop()

    # 1) Thửa chưa có trong du_lieu_gcn -> nộp thành công.
    def test_1_submit_new_parcel_ok(self):
        data, err = nhom4_service.submit_ho_so(build_payload(), FakePdf(), None)
        self.assertIsNone(err, err)
        self.assertTrue(data["ok"])
        self.assertEqual(data["so_dong"], 1)

    # 2) Sau khi nộp -> dữ liệu xuất hiện trong du_lieu_gcn với ma_nguon đúng.
    def test_2_row_persisted_with_ma_nguon(self):
        nhom4_service.submit_ho_so(build_payload(), FakePdf(), None)
        self.assertEqual(len(self.store.rows), 1)
        self.assertEqual(self.store.rows[0]["ma_nguon"], "NHOM4_FORM")
        self.assertEqual(self.store.rows[0]["madvhc"], "26317")

    # 3) Thửa vừa nộp -> WebGIS nhận diện đã có dữ liệu / màu xanh.
    def test_3_has_gcn_true_after_submit(self):
        self.assertFalse(self.store.has_gcn("26317", 10, 200))
        nhom4_service.submit_ho_so(build_payload(), FakePdf(), None)
        self.assertTrue(self.store.has_gcn("26317", 10, 200))
        # check_trung_thua (endpoint kiểm tra realtime) cũng thấy trùng.
        res, err = nhom4_service.check_trung_thua("26317", "10", "200")
        self.assertIsNone(err)
        self.assertTrue(res["trung"])

    # 4) Nộp lại cùng mã xã + tờ + thửa -> bị từ chối 409, thông báo rõ.
    def test_4_resubmit_rejected(self):
        nhom4_service.submit_ho_so(build_payload(), FakePdf(), None)
        data, err = nhom4_service.submit_ho_so(build_payload(), FakePdf(), None)
        self.assertIsNone(data)
        body, status = err
        self.assertEqual(status, 409)
        self.assertIn("đã có dữ liệu GCN", body.get_json()["error"])
        self.assertIn("Thửa 200, tờ 10", body.get_json()["error"])
        self.assertEqual(len(self.store.rows), 1)  # không ghi thêm

    # 5) Thửa KHÔNG có trong du_lieu_gcn -> tuyệt đối không báo "đã nộp trùng".
    #    (Không còn bảng khóa phụ nào để giữ khóa cũ.)
    def test_5_unknown_parcel_never_flagged(self):
        # store rỗng -> mọi thửa đều được coi là chưa có dữ liệu.
        res, err = nhom4_service.check_trung_thua("26317", "999", "888")
        self.assertIsNone(err)
        self.assertFalse(res["trung"])
        data, err = nhom4_service.submit_ho_so(
            build_payload(so_to="999", so_thua="888"), FakePdf(), None
        )
        self.assertIsNone(err, err)
        self.assertTrue(data["ok"])

    # 6) Một hồ sơ có nhiều đồng sử dụng -> INSERT đủ các dòng chủ sử dụng.
    def test_6_multi_owner_inserts_all_rows(self):
        owners = [
            {
                "ho_ten": f"Nguoi {i}",
                "ngay_sinh": "1990",
                "gioi_tinh": "Nam",
                "cccd": f"12345678901{i}",
                "dia_chi_thuong_tru": "Thon 1",
                "phap_nhan": "Đồng sử dụng",
                "vai_tro_phap_nhan": "Đồng sử dụng",
            }
            for i in range(2)
        ]
        data, err = nhom4_service.submit_ho_so(
            build_payload(owners=owners), FakePdf(), None
        )
        self.assertIsNone(err, err)
        self.assertEqual(data["so_dong"], 2)
        self.assertEqual(len(self.store.rows), 2)
        keys = {self.store.key_of(r) for r in self.store.rows}
        self.assertEqual(keys, {"26317_10_200"})  # cùng 1 thửa, 2 chủ

        # Thửa đó giờ đã "có dữ liệu" -> lần nộp sau bị chặn.
        _, err2 = nhom4_service.submit_ho_so(build_payload(owners=owners), FakePdf(), None)
        self.assertIsNotNone(err2)
        self.assertEqual(err2[1], 409)

    # 7) Double-click nút Nộp: frontend phải khóa đồng bộ bằng ref, không
    #    chỉ dựa vào thuộc tính disabled (đợi re-render).
    def test_7_frontend_double_click_guard_present(self):
        page = os.path.join(REPO_DIR, "frontend", "src", "Nhom4FormPage.jsx")
        with open(page, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("useRef", src)
        self.assertIn("submittingRef", src)
        # Guard chạy TRƯỚC mọi await trong handleSubmit.
        self.assertRegex(src, r"if \(submittingRef\.current\) return;")
        self.assertRegex(src, r"submittingRef\.current = true;")
        self.assertRegex(src, r"finally\s*\{\s*\n\s*submittingRef\.current = false;")

    # 8) Đồng bộ Google Sheet không xóa/ghi đè dữ liệu ma_nguon='NHOM4_FORM'.
    #    replace_source() chỉ xóa theo đúng ma_nguon của nguồn Sheet đang
    #    sync; NHOM4_FORM không bao giờ là 1 nguồn trong bảng nguon_gcn.
    def test_8_sheet_sync_scoped_delete(self):
        sync_dir = os.path.join(REPO_DIR, "sync_gcn")
        with open(os.path.join(sync_dir, "supabase_sync.py"), encoding="utf-8") as fh:
            src = fh.read()
        # Xóa luôn có .eq("ma_nguon", ma_nguon) — không phải delete toàn bảng.
        self.assertRegex(
            src, r"\.delete\(\)\.eq\(\s*[\"']ma_nguon[\"']\s*,\s*ma_nguon\s*\)"
        )
        self.assertNotRegex(src, r"NHOM4_FORM")
        with open(os.path.join(sync_dir, "main.py"), encoding="utf-8") as fh:
            main_src = fh.read()
        # Nguồn sync đọc từ bảng nguon_gcn, không tự chèn NHOM4_FORM.
        self.assertNotRegex(main_src, r"NHOM4_FORM")


class FakeDrive:
    """google_drive_client giả: ghi lại các lần upload_pdf để kiểm tên file."""

    def __init__(self):
        self.uploads: list[tuple[str, bytes]] = []

    def resolve_xa_folder(self, ma_xa, ten_xa):
        return "folder-123"

    def upload_pdf(self, folder_id, filename, content):
        self.uploads.append((filename, content))
        return {"id": f"id-{filename}", "name": filename}


class Nhom4FileUploadTest(unittest.TestCase):
    """Đặt tên file quét trên Drive: -DDK/-GCN (file chính), -GT (giấy tờ),
    -TBXN (thông báo xác nhận, chỉ chế độ "Chưa được cấp GCN", tùy chọn)."""

    class _FakeResp:
        ok = True
        text = ""

    def setUp(self):
        self.app = Flask(__name__)
        self.ctx = self.app.app_context()
        self.ctx.push()

        self.drive = FakeDrive()
        self._orig_drive = nhom4_service.google_drive_client
        nhom4_service.google_drive_client = self.drive

        # Bắt patch THẬT mà nhom4_repository.update_file_info_by_submission
        # dựng (gồm cả ánh xạ cột file_tbxn_* + ghép tenfilequet).
        self.patches: list[dict] = []
        self._orig_rest = nhom4_repository.supabase_client.rest_request

        def fake_rest(method, table, params=None, json_body=None, extra_headers=None):
            self.patches.append(json_body)
            return self._FakeResp(), None

        nhom4_repository.supabase_client.rest_request = fake_rest

    def tearDown(self):
        nhom4_service.google_drive_client = self._orig_drive
        nhom4_repository.supabase_client.rest_request = self._orig_rest
        self.ctx.pop()

    def _run(self, tbxn_bytes):
        nhom4_service._upload_files_background(
            self.app, "26317", "Xa Test", "26317_10_200", "DDK",
            b"chinh", b"phu", tbxn_bytes, "sub-1",
        )

    def test_tbxn_uploaded_with_suffix(self):
        self._run(b"tbxn-body")
        names = [name for name, _ in self.drive.uploads]
        self.assertEqual(
            names, ["26317_10_200-DDK.pdf", "26317_10_200-GT.pdf", "26317_10_200-TBXN.pdf"]
        )
        self.assertEqual(self.patches[0]["file_tbxn_drive_id"], "id-26317_10_200-TBXN.pdf")
        self.assertEqual(self.patches[0]["file_tbxn_ten_file"], "26317_10_200-TBXN.pdf")
        self.assertIn("26317_10_200-TBXN.pdf", self.patches[0]["tenfilequet"])

    def test_no_tbxn_skips_upload(self):
        self._run(None)
        names = [name for name, _ in self.drive.uploads]
        self.assertEqual(names, ["26317_10_200-DDK.pdf", "26317_10_200-GT.pdf"])
        self.assertIsNone(self.patches[0]["file_tbxn_drive_id"])
        self.assertNotIn("TBXN", self.patches[0]["tenfilequet"])


class Nhom4SubmitTbxnTest(unittest.TestCase):
    """submit_ho_so nhận file_tbxn (tùy chọn) mà không phá luồng cũ."""

    def setUp(self):
        self.app = Flask(__name__)
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.store = FakeDuLieuGcn()
        self._orig = {}
        for name, fn in {
            "filter_existing_keys": self.store.filter_existing_keys,
            "insert_rows": self.store.insert_rows,
        }.items():
            self._orig[name] = getattr(nhom4_repository, name)
            setattr(nhom4_repository, name, fn)
        self._orig["list_phan_loai_by_xa"] = nhom4_repository.list_phan_loai_by_xa
        nhom4_repository.list_phan_loai_by_xa = lambda ma_xa: ({}, None)
        self._orig_bg = nhom4_service._upload_files_background
        self.bg_calls: list[tuple] = []
        nhom4_service._upload_files_background = lambda *a, **k: self.bg_calls.append(a)

    def tearDown(self):
        for name, fn in self._orig.items():
            setattr(nhom4_repository, name, fn)
        nhom4_service._upload_files_background = self._orig_bg
        self.ctx.pop()

    def test_submit_with_tbxn_ok_and_bytes_forwarded(self):
        data, err = nhom4_service.submit_ho_so(
            build_payload(), FakePdf("chinh.pdf"), None, FakePdf("tbxn.pdf")
        )
        self.assertIsNone(err, err)
        self.assertTrue(data["ok"])
        # tham số thứ 8 của _upload_files_background là tbxn_bytes.
        self.assertEqual(self.bg_calls[0][7], b"%PDF-1.4 fake body")

    def test_tbxn_ignored_when_da_co_gcn(self):
        payload = build_payload()
        payload["che_do"] = "Đã có GCN"
        payload["gcn"] = {"so_phat_hanh": "1234567890", "ngay_cap": "01/01/2020", "so_vao_so": "1"}
        data, err = nhom4_service.submit_ho_so(
            payload, FakePdf("gcn.pdf"), None, FakePdf("tbxn.pdf")
        )
        self.assertIsNone(err, err)
        self.assertIsNone(self.bg_calls[0][7])  # tbxn_bytes = None


class ThoiHanSoNamTest(unittest.TestCase):
    """Thời hạn sử dụng nhập bằng SỐ NĂM, không còn dd/mm/yyyy. Thêm NTS."""

    def setUp(self):
        self.app = Flask(__name__)
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.store = FakeDuLieuGcn()
        self._orig = {}
        for name, fn in {
            "filter_existing_keys": self.store.filter_existing_keys,
            "insert_rows": self.store.insert_rows,
        }.items():
            self._orig[name] = getattr(nhom4_repository, name)
            setattr(nhom4_repository, name, fn)
        self._orig["list_phan_loai_by_xa"] = nhom4_repository.list_phan_loai_by_xa
        nhom4_repository.list_phan_loai_by_xa = lambda ma_xa: ({}, None)
        self._orig_bg = nhom4_service._upload_files_background
        nhom4_service._upload_files_background = lambda *a, **k: None

    def tearDown(self):
        for name, fn in self._orig.items():
            setattr(nhom4_repository, name, fn)
        nhom4_service._upload_files_background = self._orig_bg
        self.ctx.pop()

    def test_validate_accepts_plain_year_count(self):
        self.assertTrue(nhom4_validation.validate_thoi_han_su_dung("CLN", "50"))
        self.assertTrue(nhom4_validation.validate_thoi_han_su_dung("CLN", "50 năm"))
        self.assertTrue(nhom4_validation.validate_thoi_han_su_dung("ONT", "Lâu dài"))

    def test_validate_rejects_ddmmyyyy(self):
        self.assertFalse(nhom4_validation.validate_thoi_han_su_dung("CLN", "31/12/2050"))
        self.assertFalse(nhom4_validation.validate_thoi_han_su_dung("CLN", "abc"))

    def test_normalize_to_nam(self):
        self.assertEqual(nhom4_validation.normalize_thoi_han_su_dung("CLN", "50"), "50 năm")
        self.assertEqual(nhom4_validation.normalize_thoi_han_su_dung("NTS", "50 năm"), "50 năm")
        self.assertEqual(nhom4_validation.normalize_thoi_han_su_dung("ONT", "Lâu dài"), "Lâu dài")

    def test_submit_with_year_count_stored_as_nam(self):
        payload = build_payload(loai_dat="NTS", thoi_han="50")
        data, err = nhom4_service.submit_ho_so(payload, FakePdf(), None)
        self.assertIsNone(err, err)
        self.assertEqual(self.store.rows[0]["loaidat1"], "NTS")
        self.assertEqual(self.store.rows[0]["thoihansudung1"], "50 năm")

    def test_submit_rejects_ddmmyyyy_thoi_han(self):
        payload = build_payload(loai_dat="CLN", thoi_han="31/12/2050")
        data, err = nhom4_service.submit_ho_so(payload, FakePdf(), None)
        self.assertIsNone(data)
        self.assertEqual(err[1], 400)
        self.assertIn("số năm", err[0].get_json()["error"])

    def test_frontend_constants_have_nts(self):
        path = os.path.join(REPO_DIR, "frontend", "src", "utils", "nhom4Constants.js")
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        self.assertRegex(src, r'LOAI_DAT_OPTIONS\s*=\s*\[[^\]]*"NTS"')

    def test_frontend_form_uses_so_nam_not_ddmmyyyy(self):
        path = os.path.join(REPO_DIR, "frontend", "src", "Nhom4FormPage.jsx")
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("const SO_NAM =", src)
        self.assertNotIn("DATE_DDMMYYYY", src)
        # placeholder dd/mm/yyyy chỉ còn ở ngày cấp GCN / ngày sinh, không
        # còn ở ô thời hạn sử dụng.
        self.assertNotRegex(src, r'thoiHanSuDung[\s\S]{0,200}dd/mm/yyyy')


class Nhom4CleanupTest(unittest.TestCase):
    """Bảo đảm code đã dọn hết cơ chế nhom4_thua_da_nop."""

    def test_repository_has_no_claim_release(self):
        self.assertFalse(hasattr(nhom4_repository, "claim_keys"))
        self.assertFalse(hasattr(nhom4_repository, "release_keys"))
        self.assertFalse(hasattr(nhom4_repository, "list_existing_keys"))
        self.assertTrue(hasattr(nhom4_repository, "filter_existing_keys"))

    def test_no_runtime_references_to_lock_table(self):
        for rel in (
            os.path.join("backend", "app", "services", "nhom4_service.py"),
            os.path.join("backend", "app", "repositories", "nhom4_repository.py"),
        ):
            with open(os.path.join(REPO_DIR, rel), encoding="utf-8") as fh:
                src = fh.read()
            # Bỏ comment rồi kiểm — cho phép nhắc tên trong chú thích.
            code = re.sub(r"#.*", "", src)
            self.assertNotIn("nhom4_thua_da_nop", code, rel)
            self.assertNotIn("nhom4_claim_keys", code, rel)
            self.assertNotIn("claim_keys(", code, rel)
            self.assertNotIn("release_keys(", code, rel)

    def test_setup_sql_no_longer_creates_lock_table(self):
        path = os.path.join(REPO_DIR, "sync_gcn", "create_du_lieu_gcn.sql")
        with open(path, encoding="utf-8") as fh:
            sql = fh.read().lower()
        self.assertNotIn("create table if not exists public.nhom4_thua_da_nop", sql)
        self.assertNotIn("create or replace function public.nhom4_claim_keys", sql)

    def test_drop_migration_exists(self):
        path = os.path.join(REPO_DIR, "sync_gcn", "drop_nhom4_thua_da_nop.sql")
        self.assertTrue(os.path.exists(path))
        with open(path, encoding="utf-8") as fh:
            sql = fh.read().lower()
        self.assertIn("drop function if exists public.nhom4_claim_keys", sql)
        self.assertIn("drop table if exists public.nhom4_thua_da_nop", sql)


if __name__ == "__main__":
    unittest.main(verbosity=2)

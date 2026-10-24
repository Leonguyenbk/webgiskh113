import { useState } from "react";

import {
  capNhatDanhMucHoSo,
  exportDanhMucHoSo,
  getDanhMucHoSo,
  importDanhMucHoSo,
  kiemTraGcnDanhMuc,
  taiMauDanhMucHoSo,
  themDanhMucHoSo,
} from "./services/danhMucHoSoService";

const PAGE_SIZE = 100;

// 24 Chi nhánh khu vực VPĐK (Đắk Lắk + Phú Yên cũ, theo KH 2959) — danh
// sách cố định do người dùng cung cấp, không tự suy ra từ tên thư mục
// DANHSACHGUIXA (tên thư mục không đủ/không khớp tên chính thức).
const CHI_NHANH_OPTIONS = [
  "Chi nhánh khu vực Buôn Ma Thuột",
  "Chi nhánh khu vực Buôn Hồ",
  "Chi nhánh khu vực Buôn Đôn",
  "Chi nhánh khu vực Cư Kuin",
  "Chi nhánh khu vực Cư M’gar",
  "Chi nhánh khu vực Ea H’leo",
  "Chi nhánh khu vực Ea Kar",
  "Chi nhánh khu vực Ea Súp",
  "Chi nhánh khu vực Krông Ana",
  "Chi nhánh khu vực Krông Bông",
  "Chi nhánh khu vực Krông Búk",
  "Chi nhánh khu vực Krông Năng",
  "Chi nhánh khu vực Krông Pắc",
  "Chi nhánh khu vực Lắk",
  "Chi nhánh khu vực M’Drắk",
  "Chi nhánh khu vực Tuy Hòa",
  "Chi nhánh khu vực Sông Cầu",
  "Chi nhánh khu vực Đông Hòa",
  "Chi nhánh khu vực Tuy An",
  "Chi nhánh khu vực Phú Hòa",
  "Chi nhánh khu vực Tây Hòa",
  "Chi nhánh khu vực Sơn Hòa",
  "Chi nhánh khu vực Sông Hinh",
  "Chi nhánh khu vực Đồng Xuân",
];

const FORM_EMPTY = {
  nam: new Date().getFullYear(),
  ngay: "",
  chi_nhanh: "",
  cap: "",
  so_tt_ho_so: "",
  ten_nguoi_su_dung_dat: "",
  thua_dat_so_moi: "",
  ban_do_so_moi: "",
  thua_dat_so_cu: "",
  ban_do_so_cu: "",
  dia_chi_thua_dat: "",
  so_seri_gcn: "",
  loai_ho_so: "",
  ghi_chu: "",
};

function formatSo(n) {
  return Number(n || 0).toLocaleString("vi-VN");
}

// API trả "ngay" dạng ISO (YYYY-MM-DD, từ cột date) — hiển thị DD/MM/YYYY
// theo đúng yêu cầu người dùng, không phụ thuộc locale trình duyệt.
function formatNgay(value) {
  if (!value) return "";
  const [y, m, d] = String(value).split("-");
  if (!y || !m || !d) return value;
  return `${d}/${m}/${y}`;
}

// 2 nguồn này KHÔNG còn chặn nhập — chỉ hiển thị để biết (đánh dấu "Đã có
// trên VBDLis" khi lưu). "da_co_trong_danh_muc" cũng chỉ là cảnh báo (1 GCN
// có thể có nhiều dòng hồ sơ) — xem backend/app/services/danhmuchoso_service.py.
const NGUON_VBDLIS_LABEL = {
  da_nhap_form_nhom4: "đã nhập form Nhóm 4",
  da_dong_bo_mplis: "đã đồng bộ từ MPLIS",
};

// Trang "Danh mục hồ sơ lưu trữ" (theo mẫu DANHMUCHOSO/MAUFILE.xlsx) —
// nhập + sửa + xem danh sách + tải Excel. GCN đã có dữ liệu điện tử nơi
// khác (form Nhóm 4/MPLIS) vẫn cho nhập, chỉ đánh dấu cột "Đã có trên
// VBDLis". GCN đã có SẴN TRONG CHÍNH danh mục này cũng vẫn cho nhập thêm
// dòng mới, chỉ hiển thị cảnh báo.
export default function DanhMucHoSoPage({ onNavigateHome }) {
  const [form, setForm] = useState(FORM_EMPTY);
  const [editingId, setEditingId] = useState(null); // null = đang thêm mới, số = đang sửa id này
  const [gcnCheck, setGcnCheck] = useState(null); // {ton_tai, ...} | null
  const [gcnChecking, setGcnChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [formNotice, setFormNotice] = useState("");

  const [namFilter, setNamFilter] = useState("");
  const [chiNhanhFilter, setChiNhanhFilter] = useState("");
  const [keyword, setKeyword] = useState("");
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [listError, setListError] = useState("");
  const [hasSearched, setHasSearched] = useState(false);

  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");

  const [importFile, setImportFile] = useState(null);
  const [importNam, setImportNam] = useState("");
  const [importChiNhanh, setImportChiNhanh] = useState("");
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState("");
  const [importResult, setImportResult] = useState(null);
  const [importProgress, setImportProgress] = useState(null); // {da_xu_ly, tong_dong, ...} khi đang chạy nền
  const [downloadingMau, setDownloadingMau] = useState(false);
  const [mauError, setMauError] = useState("");

  // Danh sách KHÔNG tự tải khi mở trang hoặc khi đổi bộ lọc — chỉ gửi
  // request khi bấm "Tìm kiếm" (hoặc nút Trước/Sau, dùng lại bộ lọc hiện
  // tại) để tránh kéo hết dữ liệu mỗi lần gõ.
  const runSearch = async (nextOffset = 0) => {
    setOffset(nextOffset);
    setLoading(true);
    setListError("");
    try {
      const result = await getDanhMucHoSo({
        limit: PAGE_SIZE,
        offset: nextOffset,
        keyword: keyword.trim() || undefined,
        nam: namFilter || undefined,
        chi_nhanh: chiNhanhFilter || undefined,
      });
      setItems(result?.items || []);
      setTotal(Number(result?.total) || 0);
      setHasSearched(true);
    } catch (err) {
      setListError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleChangeField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (field === "so_seri_gcn") setGcnCheck(null);
  };

  const handleCheckGcn = async () => {
    const soSeriGcn = form.so_seri_gcn.trim().toUpperCase();
    if (!soSeriGcn) return;
    setFormError("");
    setGcnChecking(true);
    try {
      // Đang sửa: loại trừ chính dòng này khỏi kiểm tra "đã có trong danh
      // mục" (không thì dòng nào cũng tự báo trùng với chính nó).
      const result = await kiemTraGcnDanhMuc(soSeriGcn, editingId ?? undefined);
      setGcnCheck(result);
    } catch (err) {
      setGcnCheck(null);
      setFormError(err.message);
    } finally {
      setGcnChecking(false);
    }
  };

  const gcnNguonVbdlis = gcnCheck
    ? Object.entries(NGUON_VBDLIS_LABEL)
        .filter(([key]) => gcnCheck[key])
        .map(([, label]) => label)
    : [];
  const gcnDaCoTrongDanhMuc = Boolean(gcnCheck?.da_co_trong_danh_muc);

  const handleEditRow = (row) => {
    setEditingId(row.id);
    setForm({
      nam: row.nam ?? "",
      ngay: row.ngay || "",
      chi_nhanh: row.chi_nhanh || "",
      cap: row.cap || "",
      so_tt_ho_so: row.so_tt_ho_so || "",
      ten_nguoi_su_dung_dat: row.ten_nguoi_su_dung_dat || "",
      thua_dat_so_moi: row.thua_dat_so_moi || "",
      ban_do_so_moi: row.ban_do_so_moi || "",
      thua_dat_so_cu: row.thua_dat_so_cu || "",
      ban_do_so_cu: row.ban_do_so_cu || "",
      dia_chi_thua_dat: row.dia_chi_thua_dat || "",
      so_seri_gcn: row.so_seri_gcn || "",
      loai_ho_so: row.loai_ho_so || "",
      ghi_chu: row.ghi_chu || "",
    });
    setGcnCheck(null);
    setFormError("");
    setFormNotice("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setForm(FORM_EMPTY);
    setGcnCheck(null);
    setFormError("");
    setFormNotice("");
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (saving) return;
    setFormError("");
    setFormNotice("");
    const soSeriGcn = form.so_seri_gcn.trim().toUpperCase();
    if (!soSeriGcn) {
      setFormError("Thiếu số sêri GCN");
      return;
    }
    const coThuaMoi = form.thua_dat_so_moi.trim() && form.ban_do_so_moi.trim();
    const coThuaCu = form.thua_dat_so_cu.trim() && form.ban_do_so_cu.trim();
    if (!coThuaMoi && !coThuaCu) {
      setFormError("Thiếu thông tin thửa đất — nhập đủ cặp Thửa/Bản đồ (Mới) HOẶC cặp Thửa/Bản đồ (Cũ).");
      return;
    }
    setSaving(true);
    try {
      if (editingId) {
        await capNhatDanhMucHoSo(editingId, { ...form, so_seri_gcn: soSeriGcn });
        setFormNotice(`Đã cập nhật hồ sơ — Số sêri GCN "${soSeriGcn}".`);
        setEditingId(null);
      } else {
        await themDanhMucHoSo({ ...form, so_seri_gcn: soSeriGcn });
        setFormNotice(`Đã lưu hồ sơ — Số sêri GCN "${soSeriGcn}".`);
      }
      // Giữ nguyên Năm + Chi nhánh cho lần nhập kế tiếp (thường nhập liên
      // tiếp nhiều hồ sơ cùng năm/cùng chi nhánh) — chỉ xóa các ô còn lại.
      setForm((prev) => ({ ...FORM_EMPTY, nam: prev.nam, chi_nhanh: prev.chi_nhanh }));
      setGcnCheck(null);
      // Chỉ làm mới danh sách nếu đã từng tìm kiếm — không tự tải danh
      // sách lần đầu sau khi lưu nếu trang vẫn đang ở trạng thái "chưa
      // tìm kiếm".
      if (hasSearched) runSearch(0);
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleExport = async () => {
    if (exporting) return;
    setExporting(true);
    setExportError("");
    try {
      const blob = await exportDanhMucHoSo({
        nam: namFilter || undefined,
        keyword: keyword.trim() || undefined,
        chi_nhanh: chiNhanhFilter || undefined,
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = namFilter ? `danh_muc_ho_so_${namFilter}.xlsx` : "danh_muc_ho_so.xlsx";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err.message);
    } finally {
      setExporting(false);
    }
  };

  const handleDownloadMau = async () => {
    if (downloadingMau) return;
    setDownloadingMau(true);
    setMauError("");
    try {
      const blob = await taiMauDanhMucHoSo();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "MAUFILE.xlsx";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setMauError(err.message);
    } finally {
      setDownloadingMau(false);
    }
  };

  const handleImportSubmit = async (event) => {
    event.preventDefault();
    if (importing || !importFile) return;
    setImporting(true);
    setImportError("");
    setImportResult(null);
    setImportProgress(null);
    try {
      const result = await importDanhMucHoSo({
        file: importFile,
        nam: importNam,
        chiNhanh: importChiNhanh || undefined,
        onProgress: setImportProgress,
      });
      setImportResult(result);
      setImportFile(null);
      const fileInput = document.getElementById("dmhsImportFile");
      if (fileInput) fileInput.value = "";
      if (hasSearched) runSearch(0);
    } catch (err) {
      setImportError(err.message);
    } finally {
      setImporting(false);
      setImportProgress(null);
    }
  };

  const rangeFrom = total === 0 ? 0 : offset + 1;
  const rangeTo = Math.min(offset + PAGE_SIZE, total);
  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  const fieldStyle = { width: "100%", marginBottom: 0 };

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Danh mục hồ sơ lưu trữ</h1>
          <p>Nhập, sửa &amp; tra cứu danh mục hồ sơ lưu trữ theo mẫu MAUFILE.xlsx.</p>
        </div>
        <a
          className="backLink"
          href="/"
          onClick={(event) => {
            event.preventDefault();
            onNavigateHome?.();
          }}
        >
          ← Về bản đồ
        </a>
      </header>

      <section className="dashboardWrap">
        <form
              className="importCard"
              style={{ width: "80%", maxWidth: "80%", margin: "0 auto 16px" }}
              onSubmit={handleSubmit}
            >
              <label style={{ fontSize: 16, marginBottom: 10, display: "block" }}>
                {editingId ? `Sửa hồ sơ #${editingId}` : "Nhập hồ sơ mới"}
              </label>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
                <div style={{ gridColumn: "span 2" }}>
                  <label htmlFor="dmhsGcn">Số sêri GCN *</label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input
                      id="dmhsGcn"
                      type="text"
                      className="filterInput"
                      style={fieldStyle}
                      required
                      placeholder="VD: AL 642898 hoặc 09156461"
                      value={form.so_seri_gcn}
                      onChange={(event) => handleChangeField("so_seri_gcn", event.target.value)}
                      onBlur={handleCheckGcn}
                    />
                    <button
                      type="button"
                      className="downloadButton"
                      disabled={gcnChecking || !form.so_seri_gcn.trim()}
                      onClick={handleCheckGcn}
                    >
                      {gcnChecking ? "…" : "Kiểm tra"}
                    </button>
                  </div>
                  {gcnCheck && (
                    <div style={{ marginTop: 6, fontSize: 13 }}>
                      {gcnDaCoTrongDanhMuc && (
                        <div style={{ color: "#b8860b" }}>
                          ⚠ GCN này đã có trong danh mục hồ sơ. Bạn vẫn có thể thêm hồ sơ mới.
                        </div>
                      )}
                      {gcnNguonVbdlis.length > 0 && (
                        <div style={{ color: "#b8860b" }}>
                          ℹ GCN này đã có dữ liệu điện tử trên hệ thống ({gcnNguonVbdlis.join(", ")}) — vẫn lưu được, sẽ đánh dấu "Đã có trên VBDLis".
                        </div>
                      )}
                      {!gcnDaCoTrongDanhMuc && gcnNguonVbdlis.length === 0 && (
                        <span style={{ color: "#2e7d32" }}>✓ Chưa có ở đâu, có thể nhập.</span>
                      )}
                    </div>
                  )}
                </div>
                <div>
                  <label htmlFor="dmhsNam">Năm *</label>
                  <input
                    id="dmhsNam"
                    type="number"
                    className="filterInput"
                    style={fieldStyle}
                    required
                    value={form.nam}
                    onChange={(event) => handleChangeField("nam", event.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="dmhsNgay">Ngày (DD/MM/YYYY)</label>
                  <input
                    id="dmhsNgay"
                    type="date"
                    className="filterInput"
                    style={fieldStyle}
                    value={form.ngay}
                    onChange={(event) => handleChangeField("ngay", event.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="dmhsChiNhanh">Chi nhánh *</label>
                  <select
                    id="dmhsChiNhanh"
                    className="filterInput"
                    style={fieldStyle}
                    required
                    value={form.chi_nhanh}
                    onChange={(event) => handleChangeField("chi_nhanh", event.target.value)}
                  >
                    <option value="">— Chọn chi nhánh —</option>
                    {CHI_NHANH_OPTIONS.map((ten) => (
                      <option key={ten} value={ten}>
                        {ten}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="dmhsCap">Cặp *</label>
                  <input
                    id="dmhsCap"
                    type="text"
                    className="filterInput"
                    style={fieldStyle}
                    required
                    value={form.cap}
                    onChange={(event) => handleChangeField("cap", event.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="dmhsSoTt">Số TT hồ sơ *</label>
                  <input
                    id="dmhsSoTt"
                    type="text"
                    className="filterInput"
                    style={fieldStyle}
                    required
                    value={form.so_tt_ho_so}
                    onChange={(event) => handleChangeField("so_tt_ho_so", event.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="dmhsLoai">Loại hồ sơ *</label>
                  <input
                    id="dmhsLoai"
                    type="text"
                    className="filterInput"
                    style={fieldStyle}
                    required
                    value={form.loai_ho_so}
                    onChange={(event) => handleChangeField("loai_ho_so", event.target.value)}
                  />
                </div>

                <div style={{ gridColumn: "span 2" }}>
                  <label htmlFor="dmhsTen">Tên người sử dụng đất *</label>
                  <input
                    id="dmhsTen"
                    type="text"
                    className="filterInput"
                    style={fieldStyle}
                    required
                    value={form.ten_nguoi_su_dung_dat}
                    onChange={(event) => handleChangeField("ten_nguoi_su_dung_dat", event.target.value)}
                  />
                </div>
                <div style={{ gridColumn: "span 2" }}>
                  <label htmlFor="dmhsDiaChi">Địa chỉ thửa đất (cấp xã/phường) *</label>
                  <input
                    id="dmhsDiaChi"
                    type="text"
                    className="filterInput"
                    style={fieldStyle}
                    required
                    value={form.dia_chi_thua_dat}
                    onChange={(event) => handleChangeField("dia_chi_thua_dat", event.target.value)}
                  />
                </div>

                <div style={{ gridColumn: "span 4", fontSize: 13, color: "#666", marginTop: -4 }}>
                  Chỉ cần nhập đủ 1 trong 2 cặp dưới đây — Thửa/Bản đồ (Mới) hoặc Thửa/Bản đồ (Cũ), không bắt buộc cả 4 ô.
                </div>
                <div>
                  <label htmlFor="dmhsThuaMoi">Thửa đất số (Mới)</label>
                  <input
                    id="dmhsThuaMoi"
                    type="text"
                    className="filterInput"
                    style={fieldStyle}
                    value={form.thua_dat_so_moi}
                    onChange={(event) => handleChangeField("thua_dat_so_moi", event.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="dmhsBanDoMoi">Bản đồ số (Mới)</label>
                  <input
                    id="dmhsBanDoMoi"
                    type="text"
                    className="filterInput"
                    style={fieldStyle}
                    value={form.ban_do_so_moi}
                    onChange={(event) => handleChangeField("ban_do_so_moi", event.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="dmhsThuaCu">Thửa đất số (Cũ)</label>
                  <input
                    id="dmhsThuaCu"
                    type="text"
                    className="filterInput"
                    style={fieldStyle}
                    value={form.thua_dat_so_cu}
                    onChange={(event) => handleChangeField("thua_dat_so_cu", event.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="dmhsBanDoCu">Bản đồ số (Cũ)</label>
                  <input
                    id="dmhsBanDoCu"
                    type="text"
                    className="filterInput"
                    style={fieldStyle}
                    value={form.ban_do_so_cu}
                    onChange={(event) => handleChangeField("ban_do_so_cu", event.target.value)}
                  />
                </div>

                <div style={{ gridColumn: "span 2" }}>
                  <label htmlFor="dmhsGhiChu">Ghi chú</label>
                  <input
                    id="dmhsGhiChu"
                    type="text"
                    className="filterInput"
                    style={fieldStyle}
                    value={form.ghi_chu}
                    onChange={(event) => handleChangeField("ghi_chu", event.target.value)}
                  />
                </div>
              </div>

              <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
                <button
                  type="submit"
                  className="downloadButton"
                  style={{ opacity: saving ? 0.6 : 1 }}
                  disabled={saving}
                >
                  {saving ? "Đang lưu…" : editingId ? "💾 Cập nhật hồ sơ" : "💾 Lưu hồ sơ"}
                </button>
                {editingId && (
                  <button type="button" className="downloadButton" onClick={handleCancelEdit} disabled={saving}>
                    Hủy sửa
                  </button>
                )}
              </div>

              {formNotice && (
                <div className="notice" style={{ marginTop: 10 }}>
                  <span>{formNotice}</span>
                </div>
              )}
              {formError && (
                <div className="notice error" style={{ marginTop: 10 }}>
                  <strong>Lỗi</strong>
                  <span>{formError}</span>
                </div>
              )}
            </form>

            <form
              className="importCard"
              style={{ width: "80%", maxWidth: "80%", margin: "0 auto 16px" }}
              onSubmit={handleImportSubmit}
            >
              <label style={{ fontSize: 16, marginBottom: 10, display: "block" }}>
                Nhập hàng loạt từ Excel (theo mẫu MAUFILE.xlsx)
              </label>
              <p style={{ margin: "0 0 10px", fontSize: 13, color: "#6a817e" }}>
                GCN đã có sẵn trong danh mục vẫn được nhập thêm bình thường (không chặn) — dùng để
                ghi nhận lịch sử khi hồ sơ xuất hiện nhiều lần theo thời gian. Cột "Ngày" nhận ô
                ngày Excel thật hoặc text dạng DD/MM/YYYY.
              </p>

              <div style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
                <div>
                  <label htmlFor="dmhsImportNam">Năm (chỉ cần nếu dòng/tiêu đề chưa có Năm)</label>
                  <input
                    id="dmhsImportNam"
                    type="number"
                    className="filterInput"
                    style={{ width: 140 }}
                    placeholder="Tự đọc từ tiêu đề"
                    value={importNam}
                    onChange={(event) => setImportNam(event.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="dmhsImportChiNhanh">Chi nhánh (nếu file chưa có cột Chi nhánh)</label>
                  <select
                    id="dmhsImportChiNhanh"
                    className="filterInput"
                    style={{ width: 280 }}
                    value={importChiNhanh}
                    onChange={(event) => setImportChiNhanh(event.target.value)}
                  >
                    <option value="">— Để trống (file đã có cột Chi nhánh) —</option>
                    {CHI_NHANH_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="dmhsImportFile">File .xlsx *</label>
                  <input
                    id="dmhsImportFile"
                    type="file"
                    accept=".xlsx"
                    required
                    onChange={(event) => setImportFile(event.target.files?.[0] || null)}
                  />
                </div>
                <button type="submit" className="downloadButton" disabled={importing || !importFile}>
                  {importing ? "⏳ Đang nhập…" : "⬆ Nhập từ file"}
                </button>
                <button
                  type="button"
                  className="downloadButton"
                  disabled={downloadingMau}
                  onClick={handleDownloadMau}
                >
                  {downloadingMau ? "⏳ Đang tải…" : "⬇ Tải mẫu trống"}
                </button>
              </div>

              {mauError && (
                <div className="notice error" style={{ marginTop: 10 }}>
                  <strong>Không tải được mẫu</strong>
                  <span>{mauError}</span>
                </div>
              )}
              {importing && importProgress && (
                <div className="notice" style={{ marginTop: 10 }}>
                  <span>
                    Đang nhập {formatSo(importProgress.da_xu_ly)}/{formatSo(importProgress.tong_dong)} dòng — đã lưu{" "}
                    {formatSo(importProgress.thanh_cong)}, lỗi {formatSo(importProgress.so_dong_loi)}. Có thể mất vài phút,
                    đừng nhập lại file này.
                  </span>
                </div>
              )}
              {importError && (
                <div className="notice error" style={{ marginTop: 10 }}>
                  <strong>Nhập thất bại</strong>
                  <span>{importError}</span>
                </div>
              )}
              {importResult && (
                <div className="notice" style={{ marginTop: 10 }}>
                  <span>
                    {importResult.cac_nam_da_dung?.length > 0 && `Năm ${importResult.cac_nam_da_dung.join(", ")} — `}
                    Đọc {formatSo(importResult.tong_dong_doc)} dòng — lưu thành công{" "}
                    {formatSo(importResult.thanh_cong)} dòng
                    {importResult.trung_danh_muc > 0 &&
                      ` (trong đó ${formatSo(importResult.trung_danh_muc)} dòng trùng GCN đã có sẵn trong danh mục, vẫn lưu thêm để ghi nhận lịch sử)`}
                    {importResult.so_dong_loi > 0 && `, ${formatSo(importResult.so_dong_loi)} dòng lỗi`}
                    .
                  </span>
                  {importResult.loi?.length > 0 && (
                    <ul style={{ margin: "8px 0 0", paddingLeft: 18, maxHeight: 180, overflowY: "auto" }}>
                      {importResult.loi.map((item, idx) => (
                        <li key={idx} style={{ fontSize: 12 }}>
                          Dòng {item.dong}: {item.loi}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </form>

            <div
              className="importCard statsTableCard"
              style={{ width: "80%", maxWidth: "80%", margin: "0 auto" }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-end",
                  flexWrap: "wrap",
                  gap: 12,
                }}
              >
                <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: 12 }}>
                  <div style={{ width: 120 }}>
                    <label htmlFor="dmhsFilterNam">Năm</label>
                    <input
                      id="dmhsFilterNam"
                      type="number"
                      className="filterInput"
                      style={fieldStyle}
                      value={namFilter}
                      placeholder="Tất cả"
                      onChange={(event) => setNamFilter(event.target.value)}
                    />
                  </div>
                  <div style={{ width: 260 }}>
                    <label htmlFor="dmhsFilterChiNhanh">Chi nhánh</label>
                    <select
                      id="dmhsFilterChiNhanh"
                      className="filterInput"
                      style={fieldStyle}
                      value={chiNhanhFilter}
                      onChange={(event) => setChiNhanhFilter(event.target.value)}
                    >
                      <option value="">Tất cả</option>
                      {CHI_NHANH_OPTIONS.map((ten) => (
                        <option key={ten} value={ten}>
                          {ten}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div style={{ width: 260 }}>
                    <label htmlFor="dmhsFilterKeyword">Tìm theo tên/GCN/Cặp/Số TT</label>
                    <input
                      id="dmhsFilterKeyword"
                      type="text"
                      className="filterInput"
                      style={fieldStyle}
                      value={keyword}
                      onChange={(event) => setKeyword(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          runSearch(0);
                        }
                      }}
                    />
                  </div>
                  <button
                    type="button"
                    className="downloadButton"
                    disabled={loading}
                    style={{ opacity: loading ? 0.5 : 1 }}
                    onClick={() => runSearch(0)}
                  >
                    {loading ? "Đang tìm…" : "🔍 Tìm kiếm"}
                  </button>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <label style={{ margin: 0 }}>
                    {loading
                      ? "Đang tải…"
                      : hasSearched
                        ? `${formatSo(rangeFrom)}–${formatSo(rangeTo)} / ${formatSo(total)} hồ sơ`
                        : "Chưa tìm kiếm"}
                  </label>
                  <button
                    type="button"
                    className="downloadButton"
                    disabled={exporting}
                    style={{ opacity: exporting ? 0.5 : 1 }}
                    onClick={handleExport}
                  >
                    {exporting ? "Đang tạo file…" : "⬇ Tải Excel"}
                  </button>
                  <button
                    type="button"
                    className="downloadButton"
                    disabled={!canPrev || loading}
                    style={{ opacity: !canPrev || loading ? 0.5 : 1 }}
                    onClick={() => runSearch(Math.max(0, offset - PAGE_SIZE))}
                  >
                    ← Trước
                  </button>
                  <button
                    type="button"
                    className="downloadButton"
                    disabled={!canNext || loading}
                    style={{ opacity: !canNext || loading ? 0.5 : 1 }}
                    onClick={() => runSearch(offset + PAGE_SIZE)}
                  >
                    Sau →
                  </button>
                </div>
              </div>

              {listError && (
                <div className="notice error" style={{ marginTop: 10 }}>
                  <strong>Không tải được danh mục</strong>
                  <span>{listError}</span>
                </div>
              )}
              {exportError && (
                <div className="notice error" style={{ marginTop: 10 }}>
                  <strong>Không tải được file</strong>
                  <span>{exportError}</span>
                </div>
              )}

              <div className="statsTableWrap" style={{ marginTop: 10 }}>
                <table className="statsTable">
                  <thead>
                    <tr>
                      <th>Năm</th>
                      <th>Ngày</th>
                      <th>Chi nhánh</th>
                      <th>Cặp</th>
                      <th>Số TT hồ sơ</th>
                      <th>Tên người sử dụng đất</th>
                      <th>Thửa (mới)</th>
                      <th>BĐ (mới)</th>
                      <th>Thửa (cũ)</th>
                      <th>BĐ (cũ)</th>
                      <th>Địa chỉ</th>
                      <th>Số sêri GCN</th>
                      <th>Loại hồ sơ</th>
                      <th>Ghi chú</th>
                      <th>Đã có trên VBDLis</th>
                      <th className="stickyActionCol"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {!loading && items.length === 0 ? (
                      <tr>
                        <td colSpan={16}>
                          {hasSearched ? "Không có hồ sơ phù hợp" : "Nhập điều kiện (hoặc để trống) rồi bấm \"Tìm kiếm\" để xem danh sách"}
                        </td>
                      </tr>
                    ) : (
                      items.map((row) => (
                        <tr key={row.id}>
                          <td>{row.nam ?? ""}</td>
                          <td>{formatNgay(row.ngay)}</td>
                          <td>{row.chi_nhanh || ""}</td>
                          <td>{row.cap || ""}</td>
                          <td>{row.so_tt_ho_so || ""}</td>
                          <td>{row.ten_nguoi_su_dung_dat || ""}</td>
                          <td>{row.thua_dat_so_moi || ""}</td>
                          <td>{row.ban_do_so_moi || ""}</td>
                          <td>{row.thua_dat_so_cu || ""}</td>
                          <td>{row.ban_do_so_cu || ""}</td>
                          <td>{row.dia_chi_thua_dat || ""}</td>
                          <td>{row.so_seri_gcn}</td>
                          <td>{row.loai_ho_so || ""}</td>
                          <td>{row.ghi_chu || ""}</td>
                          <td style={{ textAlign: "center" }}>{row.da_co_tren_vbdlis ? "✓" : ""}</td>
                          <td className="stickyActionCol">
                            <button type="button" className="nhom4MiniBtn" onClick={() => handleEditRow(row)}>
                              ✏ Sửa
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
      </section>
    </main>
  );
}

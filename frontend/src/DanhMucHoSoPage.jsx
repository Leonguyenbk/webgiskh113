import { useEffect, useMemo, useState } from "react";

import {
  exportDanhMucHoSo,
  getDanhMucHoSo,
  kiemTraGcnDanhMuc,
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

// Số sêri GCN: 1-2 chữ cái (kể cả "Đ") + khoảng trắng tuỳ chọn + 6-8 số —
// khớp đúng quy tắc kiểm tra ở backend (danhmuchoso_service.py).
const SO_SERI_GCN_RE = /^[A-ZĐ]{1,2}\s?\d{6,8}$/;

function formatSo(n) {
  return Number(n || 0).toLocaleString("vi-VN");
}

const NGUON_LABEL = {
  da_nhap_form_nhom4: "đã nhập form Nhóm 4",
  da_dong_bo_mplis: "đã đồng bộ từ MPLIS",
  da_co_trong_danh_muc: "đã có trong danh mục hồ sơ",
};

// Trang "Danh mục hồ sơ lưu trữ" (theo mẫu DANHMUCHOSO/MAUFILE.xlsx) —
// nhập + xem danh sách + tải Excel. Chặn nhập hồ sơ nếu Số sêri GCN đã
// tồn tại trên hệ thống (đã nhập form Nhóm 4, đã đồng bộ MPLIS, hoặc đã
// có trong chính danh mục này) — xem backend/app/services/danhmuchoso_service.py.
export default function DanhMucHoSoPage({ onNavigateHome }) {
  const [form, setForm] = useState(FORM_EMPTY);
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

  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setListError("");
    getDanhMucHoSo(
      {
        limit: PAGE_SIZE,
        offset,
        keyword: keyword.trim() || undefined,
        nam: namFilter || undefined,
        chi_nhanh: chiNhanhFilter || undefined,
      },
      { signal: controller.signal },
    )
      .then((result) => {
        setItems(result?.items || []);
        setTotal(Number(result?.total) || 0);
      })
      .catch((err) => {
        if (err.name !== "AbortError") setListError(err.message);
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [offset, keyword, namFilter, chiNhanhFilter]);

  const handleChangeField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (field === "so_seri_gcn") setGcnCheck(null);
  };

  const handleCheckGcn = async () => {
    const soSeriGcn = form.so_seri_gcn.trim().toUpperCase();
    if (!soSeriGcn) return;
    setFormError("");
    if (!SO_SERI_GCN_RE.test(soSeriGcn)) {
      setGcnCheck(null);
      setFormError(`Số sêri GCN "${soSeriGcn}" không đúng định dạng — phải là 1-2 chữ cái kèm 6-8 số (ví dụ "AL 642898").`);
      return;
    }
    setGcnChecking(true);
    try {
      const result = await kiemTraGcnDanhMuc(soSeriGcn);
      setGcnCheck(result);
    } catch (err) {
      setGcnCheck(null);
      setFormError(err.message);
    } finally {
      setGcnChecking(false);
    }
  };

  const gcnNguon = gcnCheck
    ? Object.entries(NGUON_LABEL)
        .filter(([key]) => gcnCheck[key])
        .map(([, label]) => label)
    : [];

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
    if (!SO_SERI_GCN_RE.test(soSeriGcn)) {
      setFormError(`Số sêri GCN "${soSeriGcn}" không đúng định dạng — phải là 1-2 chữ cái kèm 6-8 số (ví dụ "AL 642898").`);
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
      await themDanhMucHoSo({ ...form, so_seri_gcn: soSeriGcn });
      setFormNotice(`Đã lưu hồ sơ — Số sêri GCN "${soSeriGcn}".`);
      // Giữ nguyên Năm + Chi nhánh cho lần nhập kế tiếp (thường nhập liên
      // tiếp nhiều hồ sơ cùng năm/cùng chi nhánh) — chỉ xóa các ô còn lại.
      setForm((prev) => ({ ...FORM_EMPTY, nam: prev.nam, chi_nhanh: prev.chi_nhanh }));
      setGcnCheck(null);
      setOffset(0);
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
          <p>Nhập &amp; tra cứu danh mục hồ sơ lưu trữ theo mẫu MAUFILE.xlsx — chặn nhập trùng số sêri GCN đã có trên hệ thống.</p>
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
              <label style={{ fontSize: 16, marginBottom: 10, display: "block" }}>Nhập hồ sơ mới</label>

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
                      placeholder="VD: AL 642898"
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
                      {gcnCheck.ton_tai ? (
                        <span style={{ color: "#c0392b" }}>
                          ⚠ GCN này đã tồn tại ({gcnNguon.join(", ")}) — không thể nhập.
                        </span>
                      ) : (
                        <span style={{ color: "#2e7d32" }}>✓ Chưa tồn tại, có thể nhập.</span>
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
                  <label htmlFor="dmhsGhiChu">Ghi chú *</label>
                  <input
                    id="dmhsGhiChu"
                    type="text"
                    className="filterInput"
                    style={fieldStyle}
                    required
                    value={form.ghi_chu}
                    onChange={(event) => handleChangeField("ghi_chu", event.target.value)}
                  />
                </div>
              </div>

              <button
                type="submit"
                className="downloadButton"
                style={{ marginTop: 14, opacity: saving || gcnCheck?.ton_tai ? 0.6 : 1 }}
                disabled={saving || gcnCheck?.ton_tai}
              >
                {saving ? "Đang lưu…" : "💾 Lưu hồ sơ"}
              </button>

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
                      onChange={(event) => {
                        setNamFilter(event.target.value);
                        setOffset(0);
                      }}
                    />
                  </div>
                  <div style={{ width: 260 }}>
                    <label htmlFor="dmhsFilterChiNhanh">Chi nhánh</label>
                    <select
                      id="dmhsFilterChiNhanh"
                      className="filterInput"
                      style={fieldStyle}
                      value={chiNhanhFilter}
                      onChange={(event) => {
                        setChiNhanhFilter(event.target.value);
                        setOffset(0);
                      }}
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
                      onChange={(event) => {
                        setKeyword(event.target.value);
                        setOffset(0);
                      }}
                    />
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <label style={{ margin: 0 }}>
                    {loading ? "Đang tải…" : `${formatSo(rangeFrom)}–${formatSo(rangeTo)} / ${formatSo(total)} hồ sơ`}
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
                    onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_SIZE))}
                  >
                    ← Trước
                  </button>
                  <button
                    type="button"
                    className="downloadButton"
                    disabled={!canNext || loading}
                    style={{ opacity: !canNext || loading ? 0.5 : 1 }}
                    onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
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
                    </tr>
                  </thead>
                  <tbody>
                    {!loading && items.length === 0 ? (
                      <tr>
                        <td colSpan={13}>Chưa có hồ sơ nào</td>
                      </tr>
                    ) : (
                      items.map((row) => (
                        <tr key={row.id}>
                          <td>{row.nam ?? ""}</td>
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

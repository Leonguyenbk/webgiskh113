import { useEffect, useMemo, useState } from "react";

import {
  exportDanhMucHoSo,
  getDanhMucHoSo,
  kiemTraGcnDanhMuc,
  themDanhMucHoSo,
} from "./services/danhMucHoSoService";

const PAGE_SIZE = 100;

const FORM_EMPTY = {
  nam: new Date().getFullYear(),
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
  const [token, setToken] = useState("");

  const [form, setForm] = useState(FORM_EMPTY);
  const [gcnCheck, setGcnCheck] = useState(null); // {ton_tai, ...} | null
  const [gcnChecking, setGcnChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");
  const [formNotice, setFormNotice] = useState("");

  const [namFilter, setNamFilter] = useState("");
  const [keyword, setKeyword] = useState("");
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [listError, setListError] = useState("");

  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");

  useEffect(() => {
    if (!token) {
      setItems([]);
      setTotal(0);
      return undefined;
    }
    const controller = new AbortController();
    setLoading(true);
    setListError("");
    getDanhMucHoSo(
      { limit: PAGE_SIZE, offset, keyword: keyword.trim() || undefined, nam: namFilter || undefined },
      token,
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, offset, keyword, namFilter]);

  const handleChangeField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (field === "so_seri_gcn") setGcnCheck(null);
  };

  const handleCheckGcn = async () => {
    const soSeriGcn = form.so_seri_gcn.trim();
    if (!soSeriGcn || !token) return;
    setGcnChecking(true);
    try {
      const result = await kiemTraGcnDanhMuc(soSeriGcn, token);
      setGcnCheck(result);
    } catch (err) {
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
    if (saving || !token) return;
    setFormError("");
    setFormNotice("");
    if (!form.so_seri_gcn.trim()) {
      setFormError("Thiếu số sêri GCN");
      return;
    }
    setSaving(true);
    try {
      await themDanhMucHoSo(form, token);
      setFormNotice(`Đã lưu hồ sơ — Số sêri GCN "${form.so_seri_gcn.trim()}".`);
      setForm((prev) => ({ ...FORM_EMPTY, nam: prev.nam }));
      setGcnCheck(null);
      setOffset(0);
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleExport = async () => {
    if (exporting || !token) return;
    setExporting(true);
    setExportError("");
    try {
      const blob = await exportDanhMucHoSo(
        { nam: namFilter || undefined, keyword: keyword.trim() || undefined },
        token,
      );
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
        <div className="importCard" style={{ maxWidth: 560, margin: "0 auto 16px" }}>
          <label htmlFor="dmhsToken">Mã xác thực</label>
          <input
            id="dmhsToken"
            type="password"
            className="filterInput"
            autoComplete="off"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="Nhập mã do quản trị viên cấp"
          />
        </div>

        {!token ? (
          <div className="notice" style={{ maxWidth: 560, margin: "0 auto" }}>
            <span>Nhập mã xác thực ở trên để dùng trang này (chứa tên người sử dụng đất).</span>
          </div>
        ) : (
          <>
            <form
              className="importCard"
              style={{ width: "80%", maxWidth: "80%", margin: "0 auto 16px" }}
              onSubmit={handleSubmit}
            >
              <label style={{ fontSize: 16, marginBottom: 10, display: "block" }}>Nhập hồ sơ mới</label>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
                <div>
                  <label htmlFor="dmhsNam">Năm</label>
                  <input
                    id="dmhsNam"
                    type="number"
                    className="filterInput"
                    style={fieldStyle}
                    value={form.nam}
                    onChange={(event) => handleChangeField("nam", event.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="dmhsCap">Cặp</label>
                  <input
                    id="dmhsCap"
                    type="text"
                    className="filterInput"
                    style={fieldStyle}
                    value={form.cap}
                    onChange={(event) => handleChangeField("cap", event.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="dmhsSoTt">Số TT hồ sơ</label>
                  <input
                    id="dmhsSoTt"
                    type="text"
                    className="filterInput"
                    style={fieldStyle}
                    value={form.so_tt_ho_so}
                    onChange={(event) => handleChangeField("so_tt_ho_so", event.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="dmhsLoai">Loại hồ sơ</label>
                  <input
                    id="dmhsLoai"
                    type="text"
                    className="filterInput"
                    style={fieldStyle}
                    value={form.loai_ho_so}
                    onChange={(event) => handleChangeField("loai_ho_so", event.target.value)}
                  />
                </div>

                <div style={{ gridColumn: "span 2" }}>
                  <label htmlFor="dmhsTen">Tên người sử dụng đất</label>
                  <input
                    id="dmhsTen"
                    type="text"
                    className="filterInput"
                    style={fieldStyle}
                    value={form.ten_nguoi_su_dung_dat}
                    onChange={(event) => handleChangeField("ten_nguoi_su_dung_dat", event.target.value)}
                  />
                </div>
                <div style={{ gridColumn: "span 2" }}>
                  <label htmlFor="dmhsDiaChi">Địa chỉ thửa đất (cấp xã/phường)</label>
                  <input
                    id="dmhsDiaChi"
                    type="text"
                    className="filterInput"
                    style={fieldStyle}
                    value={form.dia_chi_thua_dat}
                    onChange={(event) => handleChangeField("dia_chi_thua_dat", event.target.value)}
                  />
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
                  <label htmlFor="dmhsGcn">Số sêri GCN</label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <input
                      id="dmhsGcn"
                      type="text"
                      className="filterInput"
                      style={fieldStyle}
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
                        <td colSpan={12}>Chưa có hồ sơ nào</td>
                      </tr>
                    ) : (
                      items.map((row) => (
                        <tr key={row.id}>
                          <td>{row.nam ?? ""}</td>
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
          </>
        )}
      </section>
    </main>
  );
}

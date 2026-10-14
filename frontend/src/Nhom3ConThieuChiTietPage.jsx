import { useEffect, useMemo, useState } from "react";

import { API_URL } from "./config/env";
import { getNhom3DanhSachConThieu, getXaList } from "./services/parcelService";

const PAGE_SIZE = 100;

function formatSo(n) {
  return Number(n || 0).toLocaleString("vi-VN");
}

// Sinh danh sách số trang hiển thị kiểu "1 2 3 … 42" — luôn giữ trang đầu,
// trang cuối, trang hiện tại và 1 trang mỗi bên, còn lại gộp thành "…".
function getPageNumbers(current, totalPages) {
  if (totalPages <= 1) return [1];
  const pages = new Set([1, totalPages, current]);
  if (current - 1 > 1) pages.add(current - 1);
  if (current + 1 < totalPages) pages.add(current + 1);
  const sorted = [...pages].sort((a, b) => a - b);

  const result = [];
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i] - sorted[i - 1] > 1) result.push("...");
    result.push(sorted[i]);
  }
  return result;
}

// Trang chi tiết thửa Nhóm 3 còn thiếu dữ liệu — mở từ icon 📋 cuối mỗi
// dòng trang "/nhom-3-con-thieu". Phân trang 100 thửa/trang, có thể đổi
// xã/phường và lọc trạng thái ngay tại đây (đọc cùng RPC
// public.nhom3_list_con_thieu).
export default function Nhom3ConThieuChiTietPage({ maXa, tenXa, onNavigateBack }) {
  const [xaList, setXaList] = useState([]);
  const [xaError, setXaError] = useState("");

  const [maXaState, setMaXaState] = useState(maXa || "");
  const [xaQuery, setXaQuery] = useState(tenXa || maXa || "");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [trangThaiFilter, setTrangThaiFilter] = useState(""); // "" | "1" | "0"

  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");

  // Props đổi khi bấm icon 📋 ở 1 dòng khác trên trang danh sách (cùng
  // route "/nhom-3-chi-tiet" -> component không remount, chỉ nhận props
  // mới) -> đồng bộ lại toàn bộ state theo xã mới.
  useEffect(() => {
    setMaXaState(maXa || "");
    setXaQuery(tenXa || maXa || "");
    setTrangThaiFilter("");
    setOffset(0);
  }, [maXa, tenXa]);

  useEffect(() => {
    getXaList()
      .then((result) => setXaList(result?.items || []))
      .catch((err) => setXaError(err.message));
  }, []);

  useEffect(() => {
    if (!maXaState) {
      setItems([]);
      setTotal(0);
      return undefined;
    }
    const controller = new AbortController();
    setLoading(true);
    setError("");

    getNhom3DanhSachConThieu(
      {
        ma_xa: maXaState,
        limit: PAGE_SIZE,
        offset,
        co_nhap: trangThaiFilter || undefined,
      },
      { signal: controller.signal },
    )
      .then((result) => {
        setItems(result?.items || []);
        setTotal(Number(result?.total) || 0);
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [maXaState, offset, trangThaiFilter]);

  const filteredXaOptions = useMemo(() => {
    const keyword = xaQuery.trim().toLocaleLowerCase("vi");
    if (!keyword) return xaList;
    return xaList.filter(({ ma_xa: ma, ten_xa }) =>
      `${ten_xa} ${ma}`.toLocaleLowerCase("vi").includes(keyword),
    );
  }, [xaList, xaQuery]);

  const handleSelectXa = (ma, ten) => {
    setMaXaState(ma);
    setXaQuery(ten || ma);
    setDropdownOpen(false);
    setOffset(0);
  };

  const handleChangeTrangThai = (value) => {
    setTrangThaiFilter(value);
    setOffset(0);
  };

  const handleDownload = async () => {
    if (downloading || !maXaState) return;
    setDownloading(true);
    setDownloadError("");
    try {
      const res = await fetch(
        `${API_URL}/api/nhom3-con-thieu/export?ma_xa=${encodeURIComponent(maXaState)}`,
      );
      if (!res.ok) {
        let message = `Tải thất bại (HTTP ${res.status})`;
        try {
          message = (await res.json())?.error || message;
        } catch {
          /* body không phải JSON */
        }
        throw new Error(message);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `nhom3_con_thieu_${maXaState}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setDownloadError(err.message);
    } finally {
      setDownloading(false);
    }
  };

  const rangeFrom = total === 0 ? 0 : offset + 1;
  const rangeTo = Math.min(offset + PAGE_SIZE, total);
  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;
  const pageNumbers = useMemo(() => getPageNumbers(currentPage, totalPages), [currentPage, totalPages]);
  const headerTen = xaList.find((x) => x.ma_xa === maXaState)?.ten_xa || tenXa || maXaState;

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Nhóm 3 còn thiếu — {headerTen}</h1>
          <p>Danh sách thửa cần thu thập (Nhóm 3) chưa đủ dữ liệu — ghi rõ đã nhập nhưng sai form hoặc chưa nhập.</p>
        </div>
        <a
          className="backLink"
          href="/nhom-3-con-thieu"
          onClick={(event) => {
            event.preventDefault();
            onNavigateBack?.();
          }}
        >
          ← Về thống kê Nhóm 3
        </a>
      </header>

      <section className="dashboardWrap">
        {xaError && (
          <div className="notice error">
            <strong>Không tải được danh sách xã/phường</strong>
            <span>{xaError}</span>
          </div>
        )}

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
              <div style={{ width: 260, maxWidth: "100%" }}>
                <label htmlFor="conThieuChiTietXa">Xã / phường</label>
                <div className="comboBox" style={{ marginBottom: 0 }}>
                  <input
                    id="conThieuChiTietXa"
                    type="text"
                    className="filterInput"
                    autoComplete="off"
                    value={xaQuery}
                    placeholder="Nhập tên xã/phường để tìm…"
                    style={{ width: "100%" }}
                    onChange={(event) => {
                      setXaQuery(event.target.value);
                      setDropdownOpen(true);
                    }}
                    onFocus={() => setDropdownOpen(true)}
                    onBlur={() => setDropdownOpen(false)}
                  />

                  {dropdownOpen && (
                    <div className="comboBoxList">
                      {filteredXaOptions.length === 0 ? (
                        <div className="comboBoxEmpty">Không tìm thấy xã/phường</div>
                      ) : (
                        filteredXaOptions.map(({ ma_xa: ma, ten_xa }) => (
                          <div
                            key={ma}
                            className={`comboBoxItem${ma === maXaState ? " active" : ""}`}
                            onMouseDown={(event) => {
                              event.preventDefault();
                              handleSelectXa(ma, ten_xa);
                            }}
                          >
                            {ten_xa || ma}
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div style={{ width: 220 }}>
                <label htmlFor="conThieuChiTietTrangThai">Trạng thái</label>
                <select
                  id="conThieuChiTietTrangThai"
                  className="filterInput"
                  style={{ width: "100%", marginBottom: 0 }}
                  value={trangThaiFilter}
                  onChange={(event) => handleChangeTrangThai(event.target.value)}
                >
                  <option value="">Tất cả</option>
                  <option value="1">Đã nhập nhưng sai form</option>
                  <option value="0">Chưa nhập</option>
                </select>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <label style={{ margin: 0 }}>
                {loading
                  ? "Đang tải…"
                  : `${formatSo(rangeFrom)}–${formatSo(rangeTo)} / ${formatSo(total)} thửa`}
              </label>
              <button
                type="button"
                className="downloadButton"
                disabled={downloading || !maXaState}
                style={{ opacity: downloading || !maXaState ? 0.5 : 1 }}
                onClick={handleDownload}
              >
                {downloading ? "Đang tạo file…" : "⬇ Tải Excel"}
              </button>
            </div>
          </div>

          {error && (
            <div className="notice error" style={{ marginTop: 10 }}>
              <strong>Không tải được dữ liệu</strong>
              <span>{error}</span>
            </div>
          )}
          {downloadError && (
            <div className="notice error" style={{ marginTop: 10 }}>
              <strong>Không tải được file</strong>
              <span>{downloadError}</span>
            </div>
          )}

          {!maXaState ? (
            <div className="emptyState" style={{ marginTop: 10 }}>
              <div>📋</div>
              <strong>Chưa chọn xã/phường</strong>
              <span>Chọn 1 xã/phường ở trên để xem danh sách còn thiếu.</span>
            </div>
          ) : (
            <>
              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  alignItems: "center",
                  gap: 4,
                  marginTop: 10,
                  flexWrap: "wrap",
                }}
              >
                <button
                  type="button"
                  className="downloadButton"
                  disabled={!canPrev || loading}
                  style={{ opacity: !canPrev || loading ? 0.5 : 1, padding: "4px 10px" }}
                  onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_SIZE))}
                >
                  ← Trước
                </button>
                {pageNumbers.map((p, idx) =>
                  p === "..." ? (
                    <span key={`ellipsis_${idx}`} style={{ padding: "0 4px", color: "#888" }}>
                      …
                    </span>
                  ) : (
                    <button
                      key={p}
                      type="button"
                      className="downloadButton"
                      disabled={loading}
                      style={{
                        padding: "4px 10px",
                        opacity: loading ? 0.6 : 1,
                        background: p === currentPage ? "#0b5f59" : undefined,
                        fontWeight: p === currentPage ? 700 : 400,
                      }}
                      onClick={() => setOffset((p - 1) * PAGE_SIZE)}
                    >
                      {p}
                    </button>
                  ),
                )}
                <button
                  type="button"
                  className="downloadButton"
                  disabled={!canNext || loading}
                  style={{ opacity: !canNext || loading ? 0.5 : 1, padding: "4px 10px" }}
                  onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
                >
                  Sau →
                </button>
              </div>

              <div className="statsTableWrap" style={{ marginTop: 10 }}>
                <table className="statsTable">
                  <thead>
                    <tr>
                      <th>STT</th>
                      <th>Số tờ</th>
                      <th>Số thửa</th>
                      <th>Mã định danh</th>
                      <th>Trạng thái</th>
                    </tr>
                  </thead>
                  <tbody>
                    {!loading && items.length === 0 ? (
                      <tr>
                        <td colSpan={5}>Không có thửa phù hợp bộ lọc</td>
                      </tr>
                    ) : (
                      items.map((row, index) => (
                        <tr key={`${row.so_to}_${row.so_thua}_${index}`}>
                          <td>{formatSo(offset + index + 1)}</td>
                          <td>{row.so_to}</td>
                          <td>{row.so_thua}</td>
                          <td>{row.ma_dinh_danh || ""}</td>
                          <td>
                            <span
                              className="tag"
                              style={
                                row.co_nhap
                                  ? { color: "#7c5a00", background: "#fff3b0" }
                                  : { color: "#991b1b", background: "#fee2e2" }
                              }
                            >
                              {row.ghi_chu}
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </section>
    </main>
  );
}

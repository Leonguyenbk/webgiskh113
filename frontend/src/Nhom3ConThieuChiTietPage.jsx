import { useEffect, useState } from "react";

import { API_URL } from "./config/env";
import { getNhom3DanhSachConThieu } from "./services/parcelService";

const PAGE_SIZE = 100;

function formatSo(n) {
  return Number(n || 0).toLocaleString("vi-VN");
}

// Trang chi tiết thửa Nhóm 3 còn thiếu dữ liệu của 1 xã — mở từ icon 📋
// cuối mỗi dòng trang "/nhom-3-con-thieu". Phân trang 100 thửa/trang (đọc
// cùng RPC public.nhom3_list_con_thieu, p_ma_xa cố định theo xã đang xem).
export default function Nhom3ConThieuChiTietPage({ maXa, tenXa, onNavigateBack }) {
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");

  useEffect(() => {
    if (!maXa) return undefined;
    const controller = new AbortController();
    setLoading(true);
    setError("");

    getNhom3DanhSachConThieu(
      { ma_xa: maXa, limit: PAGE_SIZE, offset },
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
  }, [maXa, offset]);

  const handleDownload = async () => {
    if (downloading || !maXa) return;
    setDownloading(true);
    setDownloadError("");
    try {
      const res = await fetch(
        `${API_URL}/api/nhom3-con-thieu/export?ma_xa=${encodeURIComponent(maXa)}`,
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
      link.download = `nhom3_con_thieu_${maXa}.xlsx`;
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

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Nhóm 3 còn thiếu — {tenXa || maXa}</h1>
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
        {!maXa ? (
          <div className="notice error">
            <strong>Thiếu mã xã/phường</strong>
            <span>Hãy mở trang này từ icon 📋 ở trang thống kê Nhóm 3.</span>
          </div>
        ) : (
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
              <label style={{ margin: 0 }}>
                {loading
                  ? "Đang tải…"
                  : `${formatSo(rangeFrom)}–${formatSo(rangeTo)} / ${formatSo(total)} thửa còn thiếu`}
              </label>

              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="downloadButton"
                  disabled={downloading}
                  style={{ opacity: downloading ? 0.5 : 1 }}
                  onClick={handleDownload}
                >
                  {downloading ? "Đang tạo file…" : "⬇ Tải Excel"}
                </button>
                <button
                  type="button"
                  className="downloadButton"
                  disabled={!canPrev || loading}
                  style={{ opacity: !canPrev || loading ? 0.5 : 1 }}
                  onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_SIZE))}
                >
                  ← Trang trước
                </button>
                <button
                  type="button"
                  className="downloadButton"
                  disabled={!canNext || loading}
                  style={{ opacity: !canNext || loading ? 0.5 : 1 }}
                  onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
                >
                  Trang sau →
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

            <div className="statsTableWrap" style={{ marginTop: 10 }}>
              <table className="statsTable">
                <thead>
                  <tr>
                    <th>Số tờ</th>
                    <th>Số thửa</th>
                    <th>Mã định danh</th>
                    <th>Trạng thái</th>
                  </tr>
                </thead>
                <tbody>
                  {!loading && items.length === 0 ? (
                    <tr>
                      <td colSpan={4}>Xã/phường này không còn thửa thiếu dữ liệu</td>
                    </tr>
                  ) : (
                    items.map((row, index) => (
                      <tr key={`${row.so_to}_${row.so_thua}_${index}`}>
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
          </div>
        )}
      </section>
    </main>
  );
}

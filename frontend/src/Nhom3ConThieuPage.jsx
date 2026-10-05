import { useEffect, useState } from "react";

import { getNhom3TongHop } from "./services/parcelService";

function formatSo(n) {
  return Number(n || 0).toLocaleString("vi-VN");
}

function formatPercent(phan, tong) {
  if (!tong) return 0;
  return Math.round((phan / tong) * 1000) / 10;
}

export default function Nhom3ConThieuPage({ onNavigateHome }) {
  const [tongHop, setTongHop] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    getNhom3TongHop()
      .then((result) => setTongHop(result))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const theoXa = tongHop?.theo_xa || [];
  const daLam = (tongHop?.da_nhom_1_2 || 0) + (tongHop?.da_thu_thap || 0);
  const tyLeDaLam = formatPercent(daLam, tongHop?.tong || 0);

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Nhóm 3 — thống kê còn thiếu dữ liệu</h1>
          <p>
            Đối chiếu danh sách thửa cần thu thập (Nhóm 3) với thửa đã thuộc Nhóm 1/2 và thửa đã thu thập — chỉ còn lại là thửa thật sự cần nhập biểu.
          </p>
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
        {loading && <div className="notice">Đang tải số liệu thống kê…</div>}
        {error && (
          <div className="notice error">
            <strong>Không tải được số liệu</strong>
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && tongHop && (
          <>
            <div className="statTiles">
              <div className="statTile">
                <span>Tổng thửa Nhóm 3 có trên bản đồ</span>
                <strong>{formatSo(tongHop.tong)}</strong>
              </div>
              <div className="statTile">
                <span>Đã lên Nhóm 1/2 (không cần nhập biểu)</span>
                <strong>{formatSo(tongHop.da_nhom_1_2)}</strong>
              </div>
              <div className="statTile">
                <span>Đã nhập đủ dữ liệu bắt buộc (như form Nhóm 4)</span>
                <strong>{formatSo(tongHop.da_thu_thap)}</strong>
              </div>
              <div className="statTile">
                <span>Số thửa đã làm (Nhóm 1/2 + đã nhập biểu)</span>
                <strong style={{ color: "#2e7d32" }}>
                  {formatSo(daLam)} <span style={{ fontWeight: 400, fontSize: 14 }}>({tyLeDaLam}%)</span>
                </strong>
              </div>
              <div className="statTile">
                <span>Còn thiếu dữ liệu</span>
                <strong style={{ color: "#c0392b" }}>{formatSo(tongHop.con_thieu)}</strong>
              </div>
            </div>

            <div
              className="importCard statsTableCard"
              style={{ width: "80%", maxWidth: "80%", margin: "16px auto 0" }}
            >
              <label>Chi tiết theo xã/phường</label>
              <div className="statsTableWrap" style={{ marginTop: 10 }}>
                <table className="statsTable">
                  <thead>
                    <tr>
                      <th>Xã / phường</th>
                      <th>Tổng Nhóm 3</th>
                      <th>Đã Nhóm 1/2</th>
                      <th>Đã nhập đủ dữ liệu</th>
                      <th>Đã làm</th>
                      <th>%</th>
                      <th>Còn thiếu</th>
                    </tr>
                  </thead>
                  <tbody>
                    {theoXa.length === 0 ? (
                      <tr>
                        <td colSpan={7}>Chưa có dữ liệu</td>
                      </tr>
                    ) : (
                      theoXa.map((row) => {
                        const rowDaLam = (row.da_nhom_1_2 || 0) + (row.da_thu_thap || 0);
                        return (
                          <tr key={row.ma_xa}>
                            <td>{row.ten_xa || row.ma_xa}</td>
                            <td>{formatSo(row.tong)}</td>
                            <td>{formatSo(row.da_nhom_1_2)}</td>
                            <td>{formatSo(row.da_thu_thap)}</td>
                            <td>{formatSo(rowDaLam)}</td>
                            <td>{formatPercent(rowDaLam, row.tong)}%</td>
                            <td>{formatSo(row.con_thieu)}</td>
                          </tr>
                        );
                      })
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

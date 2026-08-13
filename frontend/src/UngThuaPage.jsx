import { useEffect, useMemo, useState } from "react";

import { getXaList } from "./services/parcelService";
import { getUngThuaList } from "./services/mplisService";

function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("vi-VN");
}

export default function UngThuaPage({ onNavigateHome }) {
  const [xaList, setXaList] = useState([]);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");

    Promise.all([getXaList(), getUngThuaList()])
      .then(([xaResult, itemsResult]) => {
        setXaList(xaResult?.items || []);
        setItems(itemsResult?.items || []);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const xaNameByCode = useMemo(() => {
    const map = {};
    xaList.forEach(({ ma_xa, ten_xa }) => {
      map[ma_xa] = ten_xa;
    });
    return map;
  }, [xaList]);

  const rows = useMemo(() => {
    const keyword = query.trim().toLocaleLowerCase("vi");

    return items
      .map((item) => ({ ...item, ten_xa: xaNameByCode[item.ma_xa] || item.ma_xa }))
      .filter((item) => {
        if (!keyword) return true;
        return [
          item.ten_xa,
          item.ma_xa,
          item.so_to,
          item.so_thua,
          item.to_thua_mplis,
          item.so_giay_chung_nhan,
          item.ma_don_mplis,
        ]
          .filter((value) => value !== null && value !== undefined)
          .some((value) => String(value).toLocaleLowerCase("vi").includes(keyword));
      });
  }, [items, query, xaNameByCode]);

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Thửa đã ứng thửa MPLIS</h1>
          <p>
            Danh sách thửa "chưa phân loại" đã được người thu thập đối chiếu
            thủ công với MPLIS (khác tờ thửa hiện tại)
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
        {loading && <div className="notice">Đang tải danh sách…</div>}

        {error && (
          <div className="notice error">
            <strong>Không tải được dữ liệu</strong>
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && (
          <div className="importCard statsTableCard">
            <label htmlFor="ungThuaSearch">
              Tìm theo xã/phường, tờ, thửa, tờ thửa MPLIS, số GCN, mã đơn…
            </label>
            <input
              id="ungThuaSearch"
              type="text"
              className="filterInput"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Nhập từ khóa để lọc…"
            />

            {rows.length === 0 ? (
              <div className="notice">Chưa có thửa nào được ứng thửa.</div>
            ) : (
              <div className="statsTableWrap">
                <table className="statsTable">
                  <thead>
                    <tr>
                      <th>Xã / phường</th>
                      <th>Tờ / thửa (bản đồ)</th>
                      <th>Tờ thửa trên MPLIS</th>
                      <th>Số giấy chứng nhận</th>
                      <th>Mã đơn MPLIS</th>
                      <th>Cập nhật lúc</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={row.id}>
                        <td>{row.ten_xa}</td>
                        <td>
                          {row.so_to}/{row.so_thua}
                        </td>
                        <td>{row.to_thua_mplis}</td>
                        <td>{row.so_giay_chung_nhan || "—"}</td>
                        <td>{row.ma_don_mplis || "—"}</td>
                        <td>{formatDateTime(row.updated_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </section>
    </main>
  );
}

import { useEffect, useMemo, useState } from "react";

import Nhom3BarChart from "./Nhom3BarChart";
import Nhom3TrendChart from "./Nhom3TrendChart";
import { getNhom3TongHop, getNhom3Trend } from "./services/parcelService";
import { colorForMaXa } from "./utils/nhom3ChartColors";

function formatPercent(v) {
  return Number(v || 0).toLocaleString("vi-VN", { maximumFractionDigits: 1 });
}

function formatToc(v) {
  return Number(v || 0).toLocaleString("vi-VN", { maximumFractionDigits: 1 });
}

// Lấy giá trị tốc độ (thửa/ngày) ở LÁT CẮT GẦN NHẤT có giá trị (không
// null) của mỗi xã — dùng cho biểu đồ so sánh "ai đang làm nhanh nhất".
function latestRatePerXa(trendItems) {
  const byXa = new Map();
  for (const it of trendItems || []) {
    if (it.toc_do_thua_ngay === null || it.toc_do_thua_ngay === undefined) continue;
    const t = new Date(it.ghi_nhan_luc).getTime();
    const cur = byXa.get(it.ma_xa);
    if (!cur || t > cur.t) {
      byXa.set(it.ma_xa, { t, ma_xa: it.ma_xa, ten_xa: it.ten_xa || it.ma_xa, value: Number(it.toc_do_thua_ngay) });
    }
  }
  return Array.from(byXa.values());
}

export default function Nhom3DashboardPage({ onNavigateHome, onNavigateNhom3ConThieu }) {
  const [tongHop, setTongHop] = useState(null);
  const [trendItems, setTrendItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    Promise.all([getNhom3TongHop(), getNhom3Trend()])
      .then(([tongHopResult, trendResult]) => {
        setTongHop(tongHopResult);
        setTrendItems(trendResult?.items || []);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const ratioRows = useMemo(() => {
    const theoXa = tongHop?.theo_xa || [];
    return theoXa
      .map((row) => {
        const daLam = (row.da_nhom_1_2 || 0) + (row.da_thu_thap || 0);
        const value = row.tong ? (daLam / row.tong) * 100 : 0;
        return { ma_xa: row.ma_xa, ten_xa: row.ten_xa || row.ma_xa, value, color: colorForMaXa(row.ma_xa) };
      })
      .sort((a, b) => b.value - a.value);
  }, [tongHop]);

  const speedRows = useMemo(() => {
    return latestRatePerXa(trendItems)
      .map((r) => ({ ...r, color: colorForMaXa(r.ma_xa) }))
      .sort((a, b) => b.value - a.value);
  }, [trendItems]);

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Nhóm 3 — Dashboard tỉ lệ &amp; tốc độ theo xã</h1>
          <p>So sánh tỉ lệ hoàn thành và tốc độ xử lý (thửa/ngày) giữa các xã/phường, cùng trend theo thời gian.</p>
        </div>
        <a
          className="backLink"
          href="/nhom-3-con-thieu"
          onClick={(event) => {
            event.preventDefault();
            onNavigateNhom3ConThieu?.();
          }}
        >
          Bảng số liệu →
        </a>
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
        {loading && <div className="notice">Đang tải số liệu…</div>}
        {error && (
          <div className="notice error">
            <strong>Không tải được số liệu</strong>
            <span>{error}</span>
          </div>
        )}

        {!loading && !error && (
          <>
            <div className="dashboardCharts2Col">
              <div className="dashboardCard">
                <label>Tỉ lệ hoàn thành theo xã (%)</label>
                <Nhom3BarChart
                  rows={ratioRows}
                  formatValue={formatPercent}
                  unit="%"
                  emptyMessage="Chưa có dữ liệu"
                />
              </div>

              <div className="dashboardCard">
                <label>Tốc độ xử lý hiện tại theo xã (thửa/ngày)</label>
                <Nhom3BarChart
                  rows={speedRows}
                  formatValue={formatToc}
                  unit="thửa/ngày"
                  emptyMessage="Cần ít nhất 2 lần ghi nhận lịch sử (lịch 3 giờ/lần) mới có tốc độ — quay lại sau."
                />
              </div>
            </div>

            <div style={{ marginTop: 20 }}>
              <Nhom3TrendChart items={trendItems} />
            </div>
          </>
        )}
      </section>
    </main>
  );
}

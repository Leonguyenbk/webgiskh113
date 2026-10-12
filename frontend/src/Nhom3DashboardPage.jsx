import { useEffect, useMemo, useState } from "react";

import Nhom3BarChart from "./Nhom3BarChart";
import Nhom3StatusPie from "./Nhom3StatusPie";
import Nhom3TrendChart from "./Nhom3TrendChart";
import { getNhom3TongHop, getNhom3Trend } from "./services/parcelService";
import { colorForMaXa } from "./utils/nhom3ChartColors";

function formatPercent(v) {
  return Number(v || 0).toLocaleString("vi-VN", { maximumFractionDigits: 1 });
}

function formatToc(v) {
  return Number(v || 0).toLocaleString("vi-VN", { maximumFractionDigits: 1 });
}

const DATE_RANGE_OPTIONS = [
  { value: "", label: "— Toàn bộ lịch sử —" },
  { value: "7", label: "7 ngày gần nhất" },
  { value: "14", label: "14 ngày gần nhất" },
  { value: "30", label: "30 ngày gần nhất" },
];

function tuFromPreset(days) {
  if (!days) return null;
  const d = new Date();
  d.setDate(d.getDate() - Number(days));
  return d.toISOString();
}

// Lấy giá trị tốc độ (thửa/ngày) ở LÁT CẮT GẦN NHẤT có giá trị (không
// null) của mỗi xã, TRONG khoảng đang chọn — dùng cho biểu đồ so sánh "ai
// đang làm nhanh nhất".
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

// So sánh tốc độ NỬA ĐẦU vs NỬA SAU của khoảng đang xem, theo từng xã —
// trả lời câu hỏi "xã này đang tăng tốc hay chậm lại". Ngưỡng 10% để
// không nhấp nháy vì nhiễu khi chỉ có vài điểm.
function accelPerXa(trendItems) {
  const byXa = new Map();
  for (const it of trendItems || []) {
    if (it.toc_do_thua_ngay === null || it.toc_do_thua_ngay === undefined) continue;
    if (!byXa.has(it.ma_xa)) byXa.set(it.ma_xa, []);
    byXa.get(it.ma_xa).push({ t: new Date(it.ghi_nhan_luc).getTime(), v: Number(it.toc_do_thua_ngay) });
  }
  const result = new Map();
  for (const [maXa, pts] of byXa) {
    pts.sort((a, b) => a.t - b.t);
    if (pts.length < 2) {
      result.set(maXa, { direction: null, pct: null });
      continue;
    }
    const mid = Math.ceil(pts.length / 2);
    const firstHalf = pts.slice(0, mid);
    const secondHalf = pts.slice(mid);
    const avg = (arr) => arr.reduce((s, p) => s + p.v, 0) / arr.length;
    const avgFirst = avg(firstHalf);
    const avgSecond = avg(secondHalf);
    const pct = avgFirst !== 0 ? ((avgSecond - avgFirst) / Math.abs(avgFirst)) * 100 : avgSecond > 0 ? 100 : 0;
    const direction = pct > 10 ? "up" : pct < -10 ? "down" : "flat";
    result.set(maXa, { direction, pct });
  }
  return result;
}

export default function Nhom3DashboardPage({ onNavigateHome, onNavigateNhom3ConThieu }) {
  const [tongHop, setTongHop] = useState(null);
  const [trendItems, setTrendItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [trendLoading, setTrendLoading] = useState(true);
  const [error, setError] = useState("");
  const [filterMaXa, setFilterMaXa] = useState(""); // "" = tất cả
  const [dateRangeDays, setDateRangeDays] = useState(""); // "" = toàn bộ lịch sử

  useEffect(() => {
    setLoading(true);
    setError("");
    getNhom3TongHop()
      .then((result) => setTongHop(result))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    setTrendLoading(true);
    getNhom3Trend({ ma_xa: filterMaXa || undefined, tu: tuFromPreset(dateRangeDays) || undefined })
      .then((result) => setTrendItems(result?.items || []))
      .catch((err) => setError(err.message))
      .finally(() => setTrendLoading(false));
  }, [filterMaXa, dateRangeDays]);

  const theoXa = tongHop?.theo_xa || [];

  const ratioRows = useMemo(() => {
    return theoXa
      .map((row) => {
        const daLam = (row.da_nhom_1_2 || 0) + (row.da_thu_thap || 0);
        const value = row.tong ? (daLam / row.tong) * 100 : 0;
        return { ma_xa: row.ma_xa, ten_xa: row.ten_xa || row.ma_xa, value, color: colorForMaXa(row.ma_xa) };
      })
      .sort((a, b) => b.value - a.value);
  }, [theoXa]);

  const accelMap = useMemo(() => accelPerXa(trendItems), [trendItems]);

  const speedRows = useMemo(() => {
    return latestRatePerXa(trendItems)
      .map((r) => ({ ...r, color: colorForMaXa(r.ma_xa), accel: accelMap.get(r.ma_xa) }))
      .sort((a, b) => b.value - a.value);
  }, [trendItems, accelMap]);

  // Dữ liệu biểu đồ tròn: "Tất cả" -> tổng toàn bộ (từ tongHop, đã tổng
  // hợp sẵn ở backend); chọn 1 xã -> lấy đúng dòng của xã đó. (Số liệu
  // hiện trạng, không phụ thuộc khoảng ngày đang lọc cho trend.)
  const pieSource = useMemo(() => {
    if (!filterMaXa) {
      return { daNhom12: tongHop?.da_nhom_1_2 || 0, daThuThap: tongHop?.da_thu_thap || 0, conThieu: tongHop?.con_thieu || 0 };
    }
    const row = theoXa.find((r) => r.ma_xa === filterMaXa);
    return { daNhom12: row?.da_nhom_1_2 || 0, daThuThap: row?.da_thu_thap || 0, conThieu: row?.con_thieu || 0 };
  }, [filterMaXa, tongHop, theoXa]);

  const pieTitle = filterMaXa
    ? theoXa.find((r) => r.ma_xa === filterMaXa)?.ten_xa || filterMaXa
    : "Toàn bộ dự án";

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
            <div className="dashboardFilterRow">
              <label htmlFor="nhom3DashboardXaFilter">Lọc theo xã/phường:</label>
              <select
                id="nhom3DashboardXaFilter"
                value={filterMaXa}
                onChange={(event) => setFilterMaXa(event.target.value)}
              >
                <option value="">— Tất cả —</option>
                {theoXa.map((row) => (
                  <option key={row.ma_xa} value={row.ma_xa}>
                    {row.ten_xa || row.ma_xa}
                  </option>
                ))}
              </select>

              <label htmlFor="nhom3DashboardDateRange">Khoảng thời gian (tốc độ/trend):</label>
              <select
                id="nhom3DashboardDateRange"
                value={dateRangeDays}
                onChange={(event) => setDateRangeDays(event.target.value)}
              >
                {DATE_RANGE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              {trendLoading && <span className="text-muted" style={{ fontSize: 12 }}>Đang tải…</span>}
            </div>

            <div className="dashboardCharts3Col">
              <div className="dashboardCard">
                <label>Phân bổ trạng thái — {pieTitle}</label>
                <Nhom3StatusPie
                  daNhom12={pieSource.daNhom12}
                  daThuThap={pieSource.daThuThap}
                  conThieu={pieSource.conThieu}
                  title={pieTitle}
                />
              </div>

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
                <label>
                  Tốc độ xử lý theo xã (thửa/ngày){" "}
                  <span style={{ fontWeight: 400, color: "#6a817e", fontSize: 11 }}>
                    — ▲/▼ so nửa đầu với nửa sau khoảng đang xem
                  </span>
                </label>
                <Nhom3BarChart
                  rows={speedRows}
                  formatValue={formatToc}
                  unit="thửa/ngày"
                  emptyMessage="Cần ít nhất 2 lần ghi nhận lịch sử (lịch 3 giờ/lần) mới có tốc độ — quay lại sau."
                />
              </div>
            </div>

            <div style={{ marginTop: 16 }}>
              <Nhom3TrendChart items={trendItems} />
            </div>
          </>
        )}
      </section>
    </main>
  );
}

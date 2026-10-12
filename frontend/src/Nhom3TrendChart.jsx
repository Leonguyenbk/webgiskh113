import { useMemo, useRef, useState } from "react";

import { colorForMaXa } from "./utils/nhom3ChartColors";

const WIDTH = 760;
const HEIGHT = 300;
const PAD = { top: 16, right: 16, bottom: 36, left: 52 };

function formatThoiDiem(d) {
  return d.toLocaleString("vi-VN", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function formatToc(v) {
  if (v === null || v === undefined) return "—";
  return Number(v).toLocaleString("vi-VN", { maximumFractionDigits: 1 });
}

// items: mảng phẳng từ API /api/nhom3-con-thieu/trend — mỗi dòng 1 lát cắt
// (1 xã, 1 thời điểm). Gom theo ma_xa, sắp theo thời gian.
function groupByXa(items) {
  const map = new Map();
  for (const it of items) {
    if (!map.has(it.ma_xa)) map.set(it.ma_xa, { ma_xa: it.ma_xa, ten_xa: it.ten_xa || it.ma_xa, points: [] });
    map.get(it.ma_xa).points.push({
      t: new Date(it.ghi_nhan_luc),
      v: it.toc_do_thua_ngay === null || it.toc_do_thua_ngay === undefined ? null : Number(it.toc_do_thua_ngay),
    });
  }
  const series = Array.from(map.values());
  series.forEach((s) => s.points.sort((a, b) => a.t - b.t));
  series.sort((a, b) => a.ma_xa.localeCompare(b.ma_xa));
  series.forEach((s) => (s.color = colorForMaXa(s.ma_xa)));
  return series;
}

export default function Nhom3TrendChart({ items }) {
  const [showTable, setShowTable] = useState(false);
  const [hoverX, setHoverX] = useState(null);
  const svgRef = useRef(null);

  const series = useMemo(() => groupByXa(items || []), [items]);

  const allTimes = useMemo(() => {
    const ts = [];
    series.forEach((s) => s.points.forEach((p) => ts.push(p.t.getTime())));
    return ts;
  }, [series]);

  const soLatCoToc = series.reduce(
    (sum, s) => sum + s.points.filter((p) => p.v !== null).length,
    0
  );

  // Các thời điểm duy nhất (đã ghi nhận ở bất kỳ xã nào) để bắt hover theo
  // cột gần nhất, không cần khớp pixel chính xác. Phải khai báo TRƯỚC các
  // return sớm bên dưới — hook không được gọi có điều kiện.
  const uniqueTimes = useMemo(() => Array.from(new Set(allTimes)).sort((a, b) => a - b), [allTimes]);

  if (allTimes.length === 0) {
    return <div className="notice">Chưa có lịch sử tiến độ — sẽ có dữ liệu sau lần tính cache đầu tiên.</div>;
  }

  if (soLatCoToc === 0) {
    return (
      <div className="notice">
        Mới có 1 lát cắt lịch sử cho mỗi xã — cần ít nhất 2 lần ghi nhận (lịch tự động 3 giờ/lần) mới tính được
        tốc độ (thửa/ngày). Quay lại sau.
      </div>
    );
  }

  const tMin = Math.min(...allTimes);
  const tMax = Math.max(...allTimes);
  const tSpan = tMax - tMin || 1;

  const vMax = Math.max(
    1,
    ...series.flatMap((s) => s.points.filter((p) => p.v !== null).map((p) => Math.abs(p.v)))
  );

  const innerW = WIDTH - PAD.left - PAD.right;
  const innerH = HEIGHT - PAD.top - PAD.bottom;

  const xOf = (t) => PAD.left + ((t.getTime() - tMin) / tSpan) * innerW;
  const yOf = (v) => PAD.top + innerH - (v / vMax) * innerH;

  // 4 mốc lưới ngang + nhãn trục Y.
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * vMax);

  function handleMove(evt) {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const px = ((evt.clientX - rect.left) / rect.width) * WIDTH;
    const frac = (px - PAD.left) / innerW;
    const targetT = tMin + frac * tSpan;
    let nearest = uniqueTimes[0];
    let bestDiff = Math.abs(uniqueTimes[0] - targetT);
    for (const t of uniqueTimes) {
      const diff = Math.abs(t - targetT);
      if (diff < bestDiff) {
        bestDiff = diff;
        nearest = t;
      }
    }
    setHoverX(nearest);
  }

  const hoverRows = hoverX
    ? series
        .map((s) => {
          const p = s.points.find((pt) => pt.t.getTime() === hoverX);
          return p ? { ten_xa: s.ten_xa, color: s.color, v: p.v } : null;
        })
        .filter(Boolean)
    : [];

  return (
    <div className="trendChartWrap">
      <div className="trendChartHeader">
        <label>Tốc độ xử lý theo xã (thửa/ngày)</label>
        <button type="button" className="trendTableToggle" onClick={() => setShowTable((v) => !v)}>
          {showTable ? "Xem biểu đồ" : "Xem dạng bảng"}
        </button>
      </div>

      {!showTable && (
        <div className="trendChartBody">
          <svg
            ref={svgRef}
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            width="100%"
            role="img"
            aria-label="Biểu đồ tốc độ xử lý thửa đất theo ngày, theo từng xã"
            onMouseMove={handleMove}
            onMouseLeave={() => setHoverX(null)}
          >
            {yTicks.map((v, i) => (
              <g key={i}>
                <line
                  x1={PAD.left}
                  x2={WIDTH - PAD.right}
                  y1={yOf(v)}
                  y2={yOf(v)}
                  stroke="#e1e0d9"
                  strokeWidth={1}
                />
                <text x={PAD.left - 8} y={yOf(v)} textAnchor="end" dominantBaseline="middle" fontSize={10} fill="#898781">
                  {formatToc(v)}
                </text>
              </g>
            ))}
            <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={PAD.top + innerH} stroke="#c3c2b7" strokeWidth={1} />
            <line
              x1={PAD.left}
              x2={WIDTH - PAD.right}
              y1={PAD.top + innerH}
              y2={PAD.top + innerH}
              stroke="#c3c2b7"
              strokeWidth={1}
            />

            <text x={PAD.left} y={HEIGHT - 6} fontSize={10} fill="#898781">
              {formatThoiDiem(new Date(tMin))}
            </text>
            <text x={WIDTH - PAD.right} y={HEIGHT - 6} fontSize={10} fill="#898781" textAnchor="end">
              {formatThoiDiem(new Date(tMax))}
            </text>

            {hoverX !== null && (
              <line
                x1={xOf(new Date(hoverX))}
                x2={xOf(new Date(hoverX))}
                y1={PAD.top}
                y2={PAD.top + innerH}
                stroke="#c3c2b7"
                strokeWidth={1}
                strokeDasharray="3 3"
              />
            )}

            {series.map((s) => {
              const pts = s.points.filter((p) => p.v !== null);
              if (pts.length === 0) return null;
              const d = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${xOf(p.t)} ${yOf(p.v)}`).join(" ");
              return (
                <g key={s.ma_xa}>
                  <path d={d} fill="none" stroke={s.color} strokeWidth={2} strokeLinecap="round" />
                  {pts.map((p, i) => (
                    <circle key={i} cx={xOf(p.t)} cy={yOf(p.v)} r={3} fill={s.color} />
                  ))}
                </g>
              );
            })}
          </svg>

          {hoverX !== null && hoverRows.length > 0 && (
            <div className="trendTooltip">
              <div className="trendTooltipTime">{formatThoiDiem(new Date(hoverX))}</div>
              {hoverRows.map((r, i) => (
                <div key={i} className="trendTooltipRow">
                  <span className="trendSwatch" style={{ background: r.color }} />
                  <span className="trendTooltipLabel">{r.ten_xa}</span>
                  <strong>{formatToc(r.v)}</strong>
                </div>
              ))}
            </div>
          )}

          <div className="trendLegend">
            {series.map((s) => (
              <div key={s.ma_xa} className="trendLegendItem">
                <span className="trendSwatch" style={{ background: s.color }} />
                {s.ten_xa}
              </div>
            ))}
          </div>
        </div>
      )}

      {showTable && (
        <div className="statsTableWrap" style={{ marginTop: 10 }}>
          <table className="statsTable">
            <thead>
              <tr>
                <th>Xã / phường</th>
                <th>Thời điểm ghi nhận</th>
                <th>Tốc độ (thửa/ngày)</th>
              </tr>
            </thead>
            <tbody>
              {series.flatMap((s) =>
                s.points.map((p, i) => (
                  <tr key={`${s.ma_xa}-${i}`}>
                    <td>
                      <span className="trendSwatch" style={{ background: s.color, marginRight: 6 }} />
                      {s.ten_xa}
                    </td>
                    <td>{formatThoiDiem(p.t)}</td>
                    <td>{formatToc(p.v)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

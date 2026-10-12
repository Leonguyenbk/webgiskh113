// Donut 3 phần: Đã Nhóm 1/2 / Đã nhập đủ dữ liệu / Còn thiếu — dùng
// stroke-dasharray + strokeDashoffset tích luỹ trên nhiều <circle> chồng
// nhau (cùng kỹ thuật DonutChart ở GcnDashboardPage.jsx, mở rộng cho 3
// phần thay vì 2).
const SEGMENTS = [
  { key: "da_nhom_1_2", label: "Đã Nhóm 1/2", color: "#16a34a" },
  { key: "da_thu_thap", label: "Đã nhập đủ dữ liệu", color: "#2563eb" },
  { key: "con_thieu", label: "Còn thiếu", color: "#dc2626" },
];

function formatSo(n) {
  return Number(n || 0).toLocaleString("vi-VN");
}

export default function Nhom3StatusPie({ daNhom12, daThuThap, conThieu, title }) {
  const total = (daNhom12 || 0) + (daThuThap || 0) + (conThieu || 0);
  const values = { da_nhom_1_2: daNhom12 || 0, da_thu_thap: daThuThap || 0, con_thieu: conThieu || 0 };

  const size = 180;
  const stroke = 24;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;

  let offset = 0;

  return (
    <div className="pieWrap">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={title || "Phân bổ trạng thái"}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#eef2f1" strokeWidth={stroke} />
        {total > 0 &&
          SEGMENTS.map((seg) => {
            const value = values[seg.key];
            const len = (value / total) * circumference;
            const el = (
              <circle
                key={seg.key}
                cx={size / 2}
                cy={size / 2}
                r={radius}
                fill="none"
                stroke={seg.color}
                strokeWidth={stroke}
                strokeDasharray={`${len} ${circumference - len}`}
                strokeDashoffset={-offset}
                transform={`rotate(-90 ${size / 2} ${size / 2})`}
              >
                <title>{`${seg.label}: ${formatSo(value)} (${total ? Math.round((value / total) * 100) : 0}%)`}</title>
              </circle>
            );
            offset += len;
            return el;
          })}
        <text x={size / 2} y={size / 2 - 4} textAnchor="middle" fontSize={20} fontWeight={700} fill="#102a2b">
          {formatSo(total)}
        </text>
        <text x={size / 2} y={size / 2 + 16} textAnchor="middle" fontSize={11} fill="#6a817e">
          tổng thửa
        </text>
      </svg>

      <div className="pieLegend">
        {SEGMENTS.map((seg) => {
          const value = values[seg.key];
          const pct = total ? Math.round((value / total) * 1000) / 10 : 0;
          return (
            <div key={seg.key}>
              <span style={{ background: seg.color }} />
              <label>{seg.label}</label>
              <strong>
                {formatSo(value)} <span style={{ fontWeight: 400 }}>({pct}%)</span>
              </strong>
            </div>
          );
        })}
      </div>
    </div>
  );
}

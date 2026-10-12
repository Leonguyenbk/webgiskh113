// Biểu đồ cột ngang đơn giản (xếp hạng theo độ lớn) — dùng chung cho tỉ lệ
// hoàn thành (%) và tốc độ xử lý hiện tại (thửa/ngày) theo xã. Màu theo
// colorForMaXa (utils/nhom3ChartColors) — cùng màu với biểu đồ trend để 1
// xã luôn nhận diện được qua cùng 1 màu trên cả trang.
export default function Nhom3BarChart({ rows, formatValue, unit, emptyMessage }) {
  if (!rows || rows.length === 0) {
    return <div className="notice">{emptyMessage || "Chưa có dữ liệu"}</div>;
  }

  const max = Math.max(1, ...rows.map((r) => Math.abs(r.value)));

  return (
    <div className="barChart">
      {rows.map((r) => (
        <div className="barRow" key={r.ma_xa}>
          <span className="trendSwatch" style={{ background: r.color }} />
          <span className="barLabel">{r.ten_xa}</span>
          <div className="barTrack">
            <div
              className="barFill"
              style={{ width: `${Math.max(2, (Math.abs(r.value) / max) * 100)}%`, background: r.color }}
            />
          </div>
          <span className="barValue">
            {formatValue ? formatValue(r.value) : r.value}
            {unit ? ` ${unit}` : ""}
          </span>
        </div>
      ))}
    </div>
  );
}

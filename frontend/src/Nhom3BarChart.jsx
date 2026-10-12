// Màu trạng thái CỐ ĐỊNH (không phải màu phân loại theo xã) — dùng riêng
// cho mũi tên tăng/giảm tốc, luôn đi kèm icon + nhãn %, không dùng màu
// đơn độc để truyền ý nghĩa.
const ACCEL_COLOR = { up: "#0ca30c", down: "#d03b3b", flat: "#898781" };
const ACCEL_ARROW = { up: "▲", down: "▼", flat: "→" };

function AccelBadge({ accel }) {
  if (!accel || accel.direction === null || accel.direction === undefined) return null;
  const color = ACCEL_COLOR[accel.direction];
  const arrow = ACCEL_ARROW[accel.direction];
  const pctText = Number.isFinite(accel.pct) ? `${Math.abs(Math.round(accel.pct))}%` : "";
  return (
    <span className="barAccel" style={{ color }} title="So tốc độ nửa đầu với nửa sau khoảng đang xem">
      {arrow} {pctText}
    </span>
  );
}

// Biểu đồ cột ngang đơn giản (xếp hạng theo độ lớn) — dùng chung cho tỉ lệ
// hoàn thành (%) và tốc độ xử lý hiện tại (thửa/ngày) theo xã. Màu theo
// colorForMaXa (utils/nhom3ChartColors) — cùng màu với biểu đồ trend để 1
// xã luôn nhận diện được qua cùng 1 màu trên cả trang. rows[].accel (tuỳ
// chọn) = { direction: "up"|"down"|"flat"|null, pct } hiển thị mũi tên
// tăng/giảm tốc cạnh giá trị.
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
          <AccelBadge accel={r.accel} />
        </div>
      ))}
    </div>
  );
}

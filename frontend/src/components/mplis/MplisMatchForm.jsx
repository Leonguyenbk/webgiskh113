import { useMplisMatch } from "../../hooks/useMplisMatch";
import { UNG_THUA_COLOR, UNG_THUA_LABEL } from "../../utils/constants";

// Form đối chiếu thủ công 1 thửa "chưa phân loại" với MPLIS — người thu
// thập nhập tờ thửa/số GCN/mã đơn thực tế trên MPLIS rồi bấm Lưu, thửa
// chuyển màu vàng trên bản đồ (xem getParcelFillColor trong
// utils/constants.js). Không biết gì về bản đồ/lớp GeoJSON — chỉ gọi
// mplisService rồi báo lên qua onSaved, nơi gọi (ParcelInfoPanel/App) tự
// quyết định cập nhật state nào.
export default function MplisMatchForm({ parcel, onSaved }) {
  const { form, setField, saving, error, save } = useMplisMatch(parcel);

  const handleSave = async () => {
    const saved = await save();
    if (saved) onSaved?.(saved);
  };

  return (
    <div className="ungThuaBox">
      <strong>Ứng thửa MPLIS</strong>

      {parcel?.ung_thua ? (
        <span
          className="tag"
          style={{ color: "#713f12", backgroundColor: UNG_THUA_COLOR }}
        >
          {UNG_THUA_LABEL}
        </span>
      ) : (
        <span className="empty">Thửa chưa được đối chiếu với MPLIS</span>
      )}

      <label htmlFor="ungThuaToThua">Tờ thửa trên MPLIS</label>
      <input
        id="ungThuaToThua"
        className="filterInput"
        value={form.to_thua_mplis}
        placeholder="VD: Tờ 12 - Thửa 34"
        onChange={(event) => setField("to_thua_mplis", event.target.value)}
      />

      <label htmlFor="ungThuaSoGcn">Số giấy chứng nhận</label>
      <input
        id="ungThuaSoGcn"
        className="filterInput"
        value={form.so_giay_chung_nhan}
        onChange={(event) => setField("so_giay_chung_nhan", event.target.value)}
      />

      <label htmlFor="ungThuaMaDon">Mã đơn trên MPLIS (nếu có)</label>
      <input
        id="ungThuaMaDon"
        className="filterInput"
        value={form.ma_don_mplis}
        onChange={(event) => setField("ma_don_mplis", event.target.value)}
      />

      {error && <span className="empty">{error}</span>}

      <button
        type="button"
        className="searchButton"
        disabled={!form.to_thua_mplis.trim() || saving}
        onClick={handleSave}
      >
        {saving ? "Đang lưu…" : parcel?.ung_thua ? "Cập nhật" : "Lưu"}
      </button>
    </div>
  );
}

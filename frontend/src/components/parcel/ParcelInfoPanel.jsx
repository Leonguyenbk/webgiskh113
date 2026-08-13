import MplisMatchForm from "../mplis/MplisMatchForm";
import { GCN_COLOR, GCN_LABEL, GROUP_LABELS, getGroupColor, getGroupKey } from "../../utils/constants";
import { googleMapsDirectionsUrl } from "../../utils/geometry";
import ParcelMissingInfo from "./ParcelMissingInfo";

function EmptyValue({ children }) {
  return children ? children : <span className="empty">Chưa có</span>;
}

// Khung "Thông tin thửa đất" bên phải bản đồ — chỉ bố trí giao diện và
// truyền dữ liệu xuống các component con (MplisMatchForm, ParcelMissingInfo),
// không tự chứa logic gọi API/validate.
export default function ParcelInfoPanel({
  parcel,
  feature,
  xaNameByCode,
  onClose,
  onZoom,
  onMplisSaved,
}) {
  if (!parcel) return null;

  return (
    <aside className="parcelDrawer">
      <div className="drawerHeader">
        <div>
          <strong>Thông tin thửa đất</strong>
          <span>Chi tiết thửa đang chọn</span>
        </div>

        <button type="button" onClick={onClose} aria-label="Đóng thông tin thửa đất">
          ×
        </button>
      </div>

      <div className="parcelCard">
        <div className="parcelId">
          <div>
            <small>Số tờ</small>
            <strong>{parcel.so_to}</strong>
          </div>

          <span>/</span>

          <div>
            <small>Số thửa</small>
            <strong>{parcel.so_thua}</strong>
          </div>
        </div>

        <dl>
          <div>
            <dt>Xã / phường</dt>
            <dd>
              <EmptyValue>{xaNameByCode[parcel.ma_xa] || parcel.ma_xa}</EmptyValue>
            </dd>
          </div>

          <div>
            <dt>Mục đích</dt>
            <dd>
              <span className="tag">{parcel.muc_dich_su_dung}</span>
            </dd>
          </div>

          <div>
            <dt>Diện tích</dt>
            <dd>{Number(parcel.dien_tich).toLocaleString("vi-VN")} m²</dd>
          </div>

          <div>
            <dt>Phân loại KH 2959</dt>
            <dd>
              <span
                className="tag"
                style={{
                  color: "white",
                  backgroundColor: getGroupColor(parcel.dong_bo?.phan_loai_ke_hoach_2959),
                }}
              >
                {parcel.dong_bo?.phan_loai_ke_hoach_2959 ||
                  GROUP_LABELS[getGroupKey(parcel.dong_bo?.phan_loai_ke_hoach_2959)]}
              </span>
            </dd>
          </div>

          <div>
            <dt>Dữ liệu GCN</dt>
            <dd>
              <span
                className="tag"
                style={{
                  color: parcel.co_gcn ? "white" : "#334155",
                  backgroundColor: parcel.co_gcn ? GCN_COLOR : "#e2e8f0",
                }}
              >
                {parcel.co_gcn ? GCN_LABEL : "Thửa đất chưa nhập biểu"}
              </span>
            </dd>
          </div>
        </dl>

        <MplisMatchForm parcel={parcel} onSaved={onMplisSaved} />

        <ParcelMissingInfo dongBo={parcel.dong_bo} />

        <button type="button" className="zoomButton" onClick={onZoom}>
          Phóng đến thửa
        </button>

        {feature && (
          <a
            className="directionsButton"
            href={googleMapsDirectionsUrl(feature)}
            target="_blank"
            rel="noopener noreferrer"
          >
            🧭 Chỉ đường Google Maps
          </a>
        )}
      </div>
    </aside>
  );
}

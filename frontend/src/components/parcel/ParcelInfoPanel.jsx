import { useEffect, useState } from "react";

import { DU_AN_COLOR, DU_AN_LABEL, GCN_COLOR, GCN_LABEL, GROUP_LABELS, NGOAI_DS_COLOR, NGOAI_DS_LABEL, getGroupColor, getGroupKey, isNgoaiDsGuiXa, isNhom12 } from "../../utils/constants";
import { googleMapsDirectionsUrl } from "../../utils/geometry";
import ParcelMissingInfo from "./ParcelMissingInfo";

function EmptyValue({ children }) {
  return children ? children : <span className="empty">Chưa có</span>;
}

// Khung "Thông tin thửa đất" bên phải bản đồ (desktop) / bottom-sheet
// (điện thoại, xem @media max-width:760px trong styles.css) — chỉ bố trí
// giao diện và truyền dữ liệu xuống component con (ParcelMissingInfo),
// không tự chứa logic gọi API/validate.
export default function ParcelInfoPanel({
  parcel,
  feature,
  xaNameByCode,
  onClose,
  onZoom,
  onNhapNhom4,
}) {
  // Trên điện thoại mặc định thu gọn (chỉ hiện số tờ/số thửa) — đỡ che
  // bản đồ. Đổi sang thửa khác thì thu gọn lại từ đầu, không giữ trạng
  // thái mở rộng của thửa trước. Nút "Xem chi tiết" trong drawerHeader
  // (chỉ hiện trên điện thoại) là cách duy nhất mở rộng/thu gọn.
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    setExpanded(false);
  }, [parcel?.id]);

  if (!parcel) return null;

  const dangNhom12 = isNhom12(parcel.dong_bo?.phan_loai_ke_hoach_2959);

  return (
    <aside className={`parcelDrawer${expanded ? " expanded" : " collapsed"}`}>
      <div className="drawerHeader">
        <div>
          <strong>Thông tin thửa đất</strong>
          <span>Chi tiết thửa đang chọn</span>
        </div>

        <button
          type="button"
          className="drawerExpandButton"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
        >
          {expanded ? "▴ Thu gọn" : "▾ Xem chi tiết"}
        </button>

        <button type="button" className="drawerCloseButton" onClick={onClose} aria-label="Đóng thông tin thửa đất">
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

        <div className="drawerDetails">
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
            <dt>Tên chủ ĐK (sổ mục kê cũ)</dt>
            <dd>
              <EmptyValue>{parcel.ten_chu_dk}</EmptyValue>
            </dd>
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

          {!dangNhom12 && (
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
          )}

          {isNgoaiDsGuiXa(parcel) && (
            <div>
              <dt>Danh sách gửi xã</dt>
              <dd>
                <span className="tag" style={{ color: "white", backgroundColor: NGOAI_DS_COLOR }}>
                  {NGOAI_DS_LABEL}
                </span>
              </dd>
            </div>
          )}

          {!dangNhom12 && parcel.thuoc_du_an && (
            <div>
              <dt>Ranh vùng dự án</dt>
              <dd>
                <span className="tag" style={{ color: "white", backgroundColor: DU_AN_COLOR }}>
                  {DU_AN_LABEL}
                </span>
              </dd>
            </div>
          )}
        </dl>

        <ParcelMissingInfo dongBo={parcel.dong_bo} />

        <button type="button" className="zoomButton" onClick={onZoom}>
          Phóng đến thửa
        </button>

        {!dangNhom12 && (
          <button type="button" className="zoomButton nhom4EntryButton" onClick={() => onNhapNhom4?.(parcel)}>
            📝 Nhập dữ liệu (biểu Nhóm 4)
          </button>
        )}

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
      </div>
    </aside>
  );
}

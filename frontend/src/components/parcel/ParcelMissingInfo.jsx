import { getMissingInfo } from "../../utils/constants";

export default function ParcelMissingInfo({ dongBo }) {
  const items = getMissingInfo(dongBo);

  return (
    <div className="missingInfo">
      <strong>Thông tin còn thiếu</strong>

      {items.length ? (
        <ul>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <span className="missingInfoOk">Đầy đủ thông tin đồng bộ</span>
      )}
    </div>
  );
}

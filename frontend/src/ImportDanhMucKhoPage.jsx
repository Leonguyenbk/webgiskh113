import { useState } from "react";

import { importDanhMucTrongKho } from "./services/adminService";

export default function ImportDanhMucKhoPage({ onNavigateHome }) {
  const [file, setFile] = useState(null);
  const [token, setToken] = useState("");
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!file) return;

    setStatus("uploading");
    setError("");
    setResult(null);

    try {
      const body = await importDanhMucTrongKho(file, token);
      setResult(body);
      setStatus("done");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  };

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Danh mục trong kho</h1>
          <p>Gửi file biểu tách dòng CSDL — cập nhật (upsert) danh mục hồ sơ trong kho</p>
        </div>
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

      <section className="importWrap">
        <form className="importCard" onSubmit={handleSubmit}>
          <label htmlFor="syncFile">File Excel biểu tách dòng</label>
          <input
            id="syncFile"
            type="file"
            accept=".xlsx,.xlsm"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
          <p className="importHint">
            Đọc theo tiêu đề cột: Mã xã, Tên xã, Năm, Cặp, STT hồ sơ, Tên người sử dụng đất,
            Thửa/Bản đồ số (cũ), Thửa/Bản đồ số (mới), Địa chỉ, Số seri GCN, Loại hồ sơ,
            Ngày biến động, GCN thu hồi, Xã cũ. Hồ sơ (Mã xã + Năm + Cặp + STT hồ sơ) đã
            có trong kho sẽ được thay bằng các dòng trong file mới (cập nhật tờ/thửa mới).
          </p>

          <label htmlFor="syncToken">Mã xác thực</label>
          <input
            id="syncToken"
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="Nhập mã do quản trị viên cấp (nếu có)"
          />

          <button
            type="submit"
            className="importButton"
            disabled={!file || status === "uploading"}
          >
            {status === "uploading" ? "Đang tải lên…" : "Đẩy vào cơ sở dữ liệu"}
          </button>

          {status === "done" && result && (
            <div className="notice">
              <strong>Hoàn tất</strong>
              <span>
                Đã ghi {result.so_dong} dòng của {result.so_ho_so} hồ sơ ({result.ho_so_moi} hồ sơ
                mới, {result.ho_so_cap_nhat} hồ sơ cập nhật, thay {result.dong_cu_da_thay} dòng cũ).
                {result.ho_so_giu_nguyen > 0 &&
                  ` Giữ nguyên ${result.ho_so_giu_nguyen} hồ sơ đã ứng tờ/thửa mới trong kho vì file để trống tờ/thửa mới.`}
                {result.so_dong_bo_qua > 0 &&
                  ` Bỏ qua ${result.so_dong_bo_qua} dòng thiếu Mã xã/Năm/Cặp/STT hồ sơ (dòng ${result.dong_bo_qua.join(", ")}${result.so_dong_bo_qua > result.dong_bo_qua.length ? ", …" : ""}).`}
              </span>
            </div>
          )}

          {status === "error" && (
            <div className="notice error">
              <strong>Có lỗi xảy ra</strong>
              <span>{error}</span>
            </div>
          )}
        </form>
      </section>
    </main>
  );
}

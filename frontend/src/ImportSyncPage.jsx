import { useState } from "react";

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

export default function ImportSyncPage({ onNavigateHome }) {
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

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_URL}/api/import-dong-bo`, {
        method: "POST",
        headers: token ? { "X-Import-Token": token } : undefined,
        body: formData,
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Nhập dữ liệu thất bại");
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
          <h1>Nhập dữ liệu đồng bộ</h1>
          <p>Đẩy file CSV/Excel trạng thái đồng bộ vào Supabase</p>
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
          <label htmlFor="syncFile">File CSV hoặc Excel</label>
          <input
            id="syncFile"
            type="file"
            accept=".csv,.xlsx,.xlsm"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
          <p className="importHint">
            Cột A bị bỏ qua, dữ liệu được đọc lần lượt từ cột B đến cột O
            (mã xã, số tờ, số thửa, các cờ đồng bộ, phân loại theo KH 2959).
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
            {status === "uploading" ? "Đang tải lên…" : "Đẩy vào Supabase"}
          </button>

          {status === "done" && result && (
            <div className="notice">
              <strong>Hoàn tất</strong>
              <span>
                Đã nhập {result.imported}/{result.total} dòng vào Supabase.
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

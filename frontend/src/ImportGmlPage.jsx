import { useState } from "react";

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

export default function ImportGmlPage({ onNavigateHome }) {
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
      const response = await fetch(`${API_URL}/api/import-gml`, {
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
          <h1>Nhập dữ liệu GML</h1>
          <p>Đẩy file thửa đất (.gml) vào Supabase</p>
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
          <label htmlFor="gmlFile">File GML</label>
          <input
            id="gmlFile"
            type="file"
            accept=".gml,.xml"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />

          <label htmlFor="importToken">Mã xác thực</label>
          <input
            id="importToken"
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
                Đã nhập {result.imported}/{result.total} thửa vào Supabase.
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

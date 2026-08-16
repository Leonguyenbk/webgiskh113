import { useState } from "react";

import { importRanhThon } from "./services/adminService";

export default function ImportRanhThonPage({ onNavigateHome }) {
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
      const body = await importRanhThon(file, token);
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
          <h1>Nhập ranh giới thôn</h1>
          <p>Đẩy file Shapefile (.zip gồm .shp/.shx/.dbf/.prj) vào Supabase</p>
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
          <label htmlFor="ranhThonFile">File Shapefile (.zip)</label>
          <input
            id="ranhThonFile"
            type="file"
            accept=".zip"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
          <p className="importHint">
            Nén cả .shp, .shx, .dbf (và .prj nếu có) vào 1 file .zip trước khi tải lên. Thuộc tính mỗi vùng phải có
            cột mã xã và tên thôn.
          </p>

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
                Đã nhập {result.imported}/{result.total} thôn vào Supabase.
                {result.deleted > 0 && (
                  <>
                    {" "}
                    Đã xóa {result.deleted} thôn không còn trong file (xã: {(result.xa || []).join(", ")}).
                  </>
                )}
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

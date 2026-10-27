import { useState } from "react";

import { importGml, importRanhThon } from "./services/adminService";

export default function ImportGmlPage({ onNavigateHome }) {
  const [file, setFile] = useState(null);
  const [token, setToken] = useState("");
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  // Ranh giới thôn — gộp chung trang này (trước đây chỉ có ở trang riêng
  // "Nhập ranh giới thôn") để nhập 1 chỗ cùng thửa đất, chấp nhận cả GML
  // (.gml/.xml) lẫn Shapefile (.zip) như trang gốc.
  const [thonFile, setThonFile] = useState(null);
  const [thonStatus, setThonStatus] = useState("idle");
  const [thonResult, setThonResult] = useState(null);
  const [thonError, setThonError] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!file) return;

    setStatus("uploading");
    setError("");
    setResult(null);

    try {
      const body = await importGml(file, token);
      setResult(body);
      setStatus("done");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  };

  const handleSubmitThon = async (event) => {
    event.preventDefault();
    if (!thonFile) return;

    setThonStatus("uploading");
    setThonError("");
    setThonResult(null);

    try {
      const body = await importRanhThon(thonFile, token);
      setThonResult(body);
      setThonStatus("done");
    } catch (err) {
      setThonError(err.message);
      setThonStatus("error");
    }
  };

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Nhập dữ liệu GML</h1>
          <p>Đẩy file thửa đất và ranh giới thôn vào cơ sở dữ liệu</p>
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
          <h2 className="nhom4SectionTitle">Thửa đất</h2>
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
            {status === "uploading" ? "Đang tải lên…" : "Đẩy vào cơ sở dữ liệu"}
          </button>

          {status === "done" && result && (
            <div className="notice">
              <strong>Hoàn tất</strong>
              <span>
                Đã nhập {result.imported}/{result.total} thửa vào cơ sở dữ liệu.
                {result.deleted > 0 && (
                  <>
                    {" "}
                    Đã xóa {result.deleted} thửa không còn trong file (xã: {(result.xa || []).join(", ")}).
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

        <form className="importCard" onSubmit={handleSubmitThon}>
          <h2 className="nhom4SectionTitle">Ranh giới thôn</h2>
          <label htmlFor="thonFile">File GML hoặc Shapefile (.zip)</label>
          <input
            id="thonFile"
            type="file"
            accept=".gml,.xml,.zip"
            onChange={(event) => setThonFile(event.target.files?.[0] || null)}
          />
          <p className="importHint">
            Nhận file .gml/.xml (đọc trực tiếp), hoặc .zip nén cả .shp/.shx/.dbf (+ .prj nếu có) — thuộc tính mỗi
            vùng phải có mã xã và tên thôn.
          </p>

          <label htmlFor="importTokenThon">Mã xác thực</label>
          <input
            id="importTokenThon"
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="Nhập mã do quản trị viên cấp (nếu có)"
          />

          <button
            type="submit"
            className="importButton"
            disabled={!thonFile || thonStatus === "uploading"}
          >
            {thonStatus === "uploading" ? "Đang tải lên…" : "Đẩy vào cơ sở dữ liệu"}
          </button>

          {thonStatus === "done" && thonResult && (
            <div className="notice">
              <strong>Hoàn tất</strong>
              <span>
                Đã nhập {thonResult.imported} thôn vào cơ sở dữ liệu
                {thonResult.so_vung > thonResult.total ? ` (từ ${thonResult.so_vung} vùng trong file)` : ""}.
                {thonResult.thon_gop?.length > 0 && (
                  <>
                    {" "}
                    Đã gộp các vùng cùng tên thành 1 thôn:{" "}
                    {thonResult.thon_gop.map((t) => `${t.ten_thon} (${t.so_vung} vùng)`).join(", ")}.
                  </>
                )}
                {thonResult.deleted > 0 && (
                  <>
                    {" "}
                    Đã xóa {thonResult.deleted} thôn không còn trong file (xã: {(thonResult.xa || []).join(", ")}).
                  </>
                )}
              </span>
            </div>
          )}

          {thonStatus === "error" && (
            <div className="notice error">
              <strong>Có lỗi xảy ra</strong>
              <span>{thonError}</span>
            </div>
          )}
        </form>
      </section>
    </main>
  );
}

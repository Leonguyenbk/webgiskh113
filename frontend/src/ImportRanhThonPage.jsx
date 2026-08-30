import { useState } from "react";

import { deleteRanhThon, importRanhThon } from "./services/adminService";
import { getRanhGioiThon } from "./services/ranhThonService";

export default function ImportRanhThonPage({ onNavigateHome }) {
  const [file, setFile] = useState(null);
  const [token, setToken] = useState("");
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  // Công cụ xóa ranh giới thôn theo mã xã (độc lập với phần nhập file).
  const [delMaXa, setDelMaXa] = useState("");
  const [delStatus, setDelStatus] = useState("idle");
  const [delPreview, setDelPreview] = useState(null);
  const [delResult, setDelResult] = useState(null);
  const [delError, setDelError] = useState("");

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

  const handlePreviewDelete = async () => {
    const maXa = delMaXa.trim();
    if (!maXa) return;

    setDelStatus("previewing");
    setDelError("");
    setDelResult(null);
    setDelPreview(null);

    try {
      const body = await getRanhGioiThon({ maXa });
      const tenThon = (body?.features || [])
        .map((f) => f.properties?.ten_thon)
        .filter(Boolean)
        .sort((a, b) => a.localeCompare(b, "vi"));
      setDelPreview({ maXa, tenThon });
      setDelStatus("idle");
    } catch (err) {
      setDelError(err.message);
      setDelStatus("error");
    }
  };

  const handleDelete = async () => {
    const maXa = delMaXa.trim();
    if (!maXa) return;

    const soThon = delPreview?.maXa === maXa ? delPreview.tenThon.length : null;
    const xacNhan = window.confirm(
      soThon != null
        ? `Xóa toàn bộ ${soThon} thôn của xã ${maXa}? Không thể hoàn tác.`
        : `Xóa toàn bộ ranh giới thôn của xã ${maXa}? Không thể hoàn tác.`,
    );
    if (!xacNhan) return;

    setDelStatus("deleting");
    setDelError("");
    setDelResult(null);

    try {
      const body = await deleteRanhThon(maXa, token);
      setDelResult(body);
      setDelPreview(null);
      setDelStatus("done");
    } catch (err) {
      setDelError(err.message);
      setDelStatus("error");
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

        <form
          className="importCard"
          onSubmit={(event) => {
            event.preventDefault();
            handleDelete();
          }}
        >
          <label htmlFor="delRanhThonMaXa">Xóa ranh giới thôn theo mã xã</label>
          <input
            id="delRanhThonMaXa"
            type="text"
            value={delMaXa}
            onChange={(event) => {
              setDelMaXa(event.target.value);
              setDelPreview(null);
              setDelResult(null);
              setDelError("");
            }}
            placeholder="Nhập mã xã, ví dụ 24235"
          />
          <p className="importHint">
            Xóa toàn bộ thôn của xã này khỏi Supabase. Dùng khi cần vẽ lại từ đầu. Bấm “Xem trước” để kiểm tra danh
            sách thôn sẽ bị xóa. Thao tác không thể hoàn tác.
          </p>

          <label htmlFor="delRanhThonToken">Mã xác thực</label>
          <input
            id="delRanhThonToken"
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="Nhập mã do quản trị viên cấp (nếu có)"
          />

          <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
            <button
              type="button"
              className="importButton"
              style={{ marginTop: 0, flex: 1, background: "#0f766e" }}
              onClick={handlePreviewDelete}
              disabled={!delMaXa.trim() || delStatus === "previewing" || delStatus === "deleting"}
            >
              {delStatus === "previewing" ? "Đang kiểm tra…" : "Xem trước"}
            </button>
            <button
              type="submit"
              className="importButton"
              style={{ marginTop: 0, flex: 1, background: "#b91c1c" }}
              disabled={!delMaXa.trim() || delStatus === "deleting" || delStatus === "previewing"}
            >
              {delStatus === "deleting" ? "Đang xóa…" : "Xóa"}
            </button>
          </div>

          {delPreview && (
            <div className="notice">
              <strong>
                Xã {delPreview.maXa}: {delPreview.tenThon.length} thôn
              </strong>
              <span>
                {delPreview.tenThon.length
                  ? delPreview.tenThon.join(", ")
                  : "Không có thôn nào — không có gì để xóa."}
              </span>
            </div>
          )}

          {delStatus === "done" && delResult && (
            <div className="notice">
              <strong>Đã xóa</strong>
              <span>
                Đã xóa {delResult.deleted} thôn của xã {delResult.ma_xa}.
                {delResult.deleted > 0 && ` (${(delResult.ten_thon || []).join(", ")})`}
              </span>
            </div>
          )}

          {delStatus === "error" && (
            <div className="notice error">
              <strong>Có lỗi xảy ra</strong>
              <span>{delError}</span>
            </div>
          )}
        </form>
      </section>
    </main>
  );
}

import { useCallback, useEffect, useState } from "react";

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

function formatSize(bytes) {
  if (!Number.isFinite(bytes)) return "?";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ManageMbtilesPage({ onNavigateHome }) {
  const [items, setItems] = useState([]);
  const [listError, setListError] = useState("");
  const [loadingList, setLoadingList] = useState(true);

  const [file, setFile] = useState(null);
  const [token, setToken] = useState("");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [deletingName, setDeletingName] = useState("");

  const loadList = useCallback(() => {
    setLoadingList(true);
    setListError("");

    return fetch(`${API_URL}/api/mbtiles`)
      .then((response) => response.json())
      .then((result) => {
        if (result?.error) throw new Error(result.error);
        setItems(result?.items || []);
      })
      .catch((err) => setListError(err.message))
      .finally(() => setLoadingList(false));
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!file) return;

    setStatus("uploading");
    setError("");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_URL}/api/mbtiles`, {
        method: "POST",
        headers: token ? { "X-Import-Token": token } : undefined,
        body: formData,
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Tải file lên thất bại");
      setStatus("done");
      setFile(null);
      await loadList();
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  };

  const handleDelete = async (filename) => {
    if (!window.confirm(`Xóa file "${filename}"? Không thể hoàn tác.`)) return;

    setDeletingName(filename);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/api/mbtiles/${encodeURIComponent(filename)}`,
        {
          method: "DELETE",
          headers: token ? { "X-Import-Token": token } : undefined,
        },
      );
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Xóa file thất bại");
      await loadList();
    } catch (err) {
      setError(err.message);
      setStatus("error");
    } finally {
      setDeletingName("");
    }
  };

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Quản lý MBTiles</h1>
          <p>Nhập hoặc xóa file lớp phủ raster địa chính (.mbtiles)</p>
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
          <label htmlFor="mbtilesFile">File .mbtiles</label>
          <input
            id="mbtilesFile"
            type="file"
            accept=".mbtiles"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
          <p className="importHint">
            File được lưu vào <code>backend/data</code> trên server. Trùng
            tên sẽ ghi đè file cũ. Bản đồ luôn dùng file đầu tiên theo tên
            (a-z) làm lớp địa chính đang hoạt động.
          </p>
          <p className="importHint">
            Lưu ý: nếu backend chạy trên gói Render không gắn ổ đĩa lâu dài
            (persistent disk), file tải lên qua trang này sẽ mất khi service
            khởi động lại/redeploy — chỉ dùng để cập nhật tạm thời hoặc thử
            nghiệm. Muốn giữ vĩnh viễn thì đưa file vào git như hiện tại.
          </p>

          <label htmlFor="mbtilesToken">Mã xác thực</label>
          <input
            id="mbtilesToken"
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
            {status === "uploading" ? "Đang tải lên…" : "Tải lên"}
          </button>

          {status === "done" && (
            <div className="notice">
              <strong>Hoàn tất</strong>
              <span>Đã lưu file vào backend/data.</span>
            </div>
          )}

          {status === "error" && (
            <div className="notice error">
              <strong>Có lỗi xảy ra</strong>
              <span>{error}</span>
            </div>
          )}
        </form>

        <div className="importCard">
          <label>File .mbtiles hiện có</label>

          {loadingList && <div className="notice">Đang tải danh sách…</div>}

          {listError && (
            <div className="notice error">
              <strong>Không tải được danh sách</strong>
              <span>{listError}</span>
            </div>
          )}

          {!loadingList && !listError && items.length === 0 && (
            <div className="notice">Chưa có file .mbtiles nào.</div>
          )}

          {items.length > 0 && (
            <div className="parcelList">
              {items.map((item) => (
                <div key={item.filename} className="parcelListItem">
                  <span
                    className="parcelListDot"
                    style={{
                      backgroundColor: item.active ? "#22c55e" : "#94a3b8",
                    }}
                    title={item.active ? "Đang dùng cho bản đồ" : "Không dùng"}
                  />
                  <span className="parcelListLabel">{item.filename}</span>
                  <span className="parcelListXa">
                    {formatSize(item.size_bytes)}
                  </span>
                  <button
                    type="button"
                    className="resetButton"
                    disabled={deletingName === item.filename}
                    onClick={() => handleDelete(item.filename)}
                  >
                    {deletingName === item.filename ? "Đang xóa…" : "Xóa"}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

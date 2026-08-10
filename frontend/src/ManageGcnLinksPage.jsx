import { Fragment, useCallback, useEffect, useState } from "react";

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

export default function ManageGcnLinksPage({ onNavigateHome }) {
  const [items, setItems] = useState([]);
  const [listError, setListError] = useState("");
  const [loadingList, setLoadingList] = useState(true);

  const [token, setToken] = useState("");

  const [maNguon, setMaNguon] = useState("");
  const [tenNguon, setTenNguon] = useState("");
  const [url, setUrl] = useState("");
  const [kichHoat, setKichHoat] = useState(true);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  const [editingMaNguon, setEditingMaNguon] = useState("");
  const [editTenNguon, setEditTenNguon] = useState("");
  const [editUrl, setEditUrl] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const [editError, setEditError] = useState("");

  const [busyMaNguon, setBusyMaNguon] = useState("");

  const [syncingMaNguon, setSyncingMaNguon] = useState("");
  const [syncResults, setSyncResults] = useState({});

  const loadList = useCallback(() => {
    setLoadingList(true);
    setListError("");

    return fetch(`${API_URL}/api/nguon-gcn`)
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

  const authHeaders = () => ({
    "Content-Type": "application/json",
    ...(token ? { "X-Import-Token": token } : {}),
  });

  const handleCreate = async (event) => {
    event.preventDefault();
    if (!maNguon.trim() || !url.trim()) return;

    setCreating(true);
    setCreateError("");

    try {
      const response = await fetch(`${API_URL}/api/nguon-gcn`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          ma_nguon: maNguon.trim(),
          ten_nguon: tenNguon.trim(),
          url: url.trim(),
          kich_hoat: kichHoat,
        }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Thêm nguồn thất bại");

      setMaNguon("");
      setTenNguon("");
      setUrl("");
      setKichHoat(true);
      await loadList();
    } catch (err) {
      setCreateError(err.message);
    } finally {
      setCreating(false);
    }
  };

  const startEdit = (item) => {
    setEditingMaNguon(item.ma_nguon);
    setEditTenNguon(item.ten_nguon || "");
    setEditUrl(item.url || "");
    setEditError("");
  };

  const cancelEdit = () => {
    setEditingMaNguon("");
    setEditError("");
  };

  const saveEdit = async (item) => {
    setSavingEdit(true);
    setEditError("");

    try {
      const response = await fetch(
        `${API_URL}/api/nguon-gcn/${encodeURIComponent(item.ma_nguon)}`,
        {
          method: "PATCH",
          headers: authHeaders(),
          body: JSON.stringify({
            ten_nguon: editTenNguon.trim(),
            url: editUrl.trim(),
          }),
        },
      );
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Cập nhật thất bại");

      setEditingMaNguon("");
      await loadList();
    } catch (err) {
      setEditError(err.message);
    } finally {
      setSavingEdit(false);
    }
  };

  const toggleKichHoat = async (item) => {
    setBusyMaNguon(item.ma_nguon);

    try {
      const response = await fetch(
        `${API_URL}/api/nguon-gcn/${encodeURIComponent(item.ma_nguon)}`,
        {
          method: "PATCH",
          headers: authHeaders(),
          body: JSON.stringify({ kich_hoat: !item.kich_hoat }),
        },
      );
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Cập nhật thất bại");
      await loadList();
    } catch (err) {
      setListError(err.message);
    } finally {
      setBusyMaNguon("");
    }
  };

  const handleSync = async (item) => {
    setSyncingMaNguon(item.ma_nguon);
    setSyncResults((prev) => ({ ...prev, [item.ma_nguon]: null }));

    try {
      const response = await fetch(
        `${API_URL}/api/nguon-gcn/${encodeURIComponent(item.ma_nguon)}/sync`,
        { method: "POST", headers: authHeaders() },
      );
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Đồng bộ thất bại");

      setSyncResults((prev) => ({
        ...prev,
        [item.ma_nguon]: {
          ok: true,
          message: `Đã nhập ${body.imported.toLocaleString("vi-VN")} dòng lúc ${new Date().toLocaleTimeString("vi-VN")}`,
        },
      }));
    } catch (err) {
      setSyncResults((prev) => ({
        ...prev,
        [item.ma_nguon]: { ok: false, message: err.message },
      }));
    } finally {
      setSyncingMaNguon("");
    }
  };

  const handleDelete = async (item) => {
    if (!window.confirm(`Xóa nguồn "${item.ma_nguon} - ${item.ten_nguon}"? Không thể hoàn tác.`)) {
      return;
    }

    setBusyMaNguon(item.ma_nguon);

    try {
      const response = await fetch(
        `${API_URL}/api/nguon-gcn/${encodeURIComponent(item.ma_nguon)}`,
        {
          method: "DELETE",
          headers: authHeaders(),
        },
      );
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Xóa nguồn thất bại");
      await loadList();
    } catch (err) {
      setListError(err.message);
    } finally {
      setBusyMaNguon("");
    }
  };

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Nhập đường link</h1>
          <p>Quản lý nguồn Google Sheet cho công cụ đồng bộ GCN</p>
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
        <form className="importCard" onSubmit={handleCreate}>
          <label htmlFor="gcnToken">Mã xác thực</label>
          <input
            id="gcnToken"
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="Nhập mã do quản trị viên cấp (nếu có)"
          />

          <label htmlFor="gcnMaNguon">Mã nguồn (duy nhất)</label>
          <input
            id="gcnMaNguon"
            className="filterInput"
            value={maNguon}
            onChange={(event) => setMaNguon(event.target.value)}
            placeholder="VD: 001"
          />

          <label htmlFor="gcnTenNguon">Tên nguồn</label>
          <input
            id="gcnTenNguon"
            className="filterInput"
            value={tenNguon}
            onChange={(event) => setTenNguon(event.target.value)}
            placeholder="VD: Xã A"
          />

          <label htmlFor="gcnUrl">Link Google Sheet</label>
          <input
            id="gcnUrl"
            className="filterInput"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://docs.google.com/spreadsheets/d/..."
          />

          <label className="nhomCheckbox">
            <input
              type="checkbox"
              checked={kichHoat}
              onChange={(event) => setKichHoat(event.target.checked)}
            />
            Kích hoạt (đưa vào lần đồng bộ tiếp theo)
          </label>

          <button
            type="submit"
            className="importButton"
            disabled={!maNguon.trim() || !url.trim() || creating}
          >
            {creating ? "Đang thêm…" : "Thêm nguồn"}
          </button>

          {createError && (
            <div className="notice error">
              <strong>Có lỗi xảy ra</strong>
              <span>{createError}</span>
            </div>
          )}

          <p className="importHint">
            Bấm <strong>Đồng bộ</strong> ở từng nguồn bên dưới để đọc lại
            Google Sheet và cập nhật ngay vào Supabase. Ngoài ra hệ thống tự
            động đồng bộ tất cả nguồn đang kích hoạt mỗi 30 phút (GitHub
            Actions). Vẫn có thể chạy <code>python main.py</code> trong
            <code> sync_gcn/</code> nếu muốn đồng bộ từ máy cá nhân, xem
            <code> sync_gcn/README.md</code>.
          </p>
        </form>

        <div className="importCard">
          <label>Danh sách nguồn</label>

          {loadingList && <div className="notice">Đang tải danh sách…</div>}

          {listError && (
            <div className="notice error">
              <strong>Không tải được danh sách</strong>
              <span>{listError}</span>
            </div>
          )}

          {!loadingList && !listError && items.length === 0 && (
            <div className="notice">Chưa có nguồn nào.</div>
          )}

          {items.length > 0 && (
            <div className="parcelList">
              {items.map((item) => {
                const isEditing = editingMaNguon === item.ma_nguon;
                const isBusy = busyMaNguon === item.ma_nguon;

                if (isEditing) {
                  return (
                    <div
                      key={item.ma_nguon}
                      className="parcelListItem"
                      style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}
                    >
                      <strong>{item.ma_nguon}</strong>
                      <input
                        className="filterInput"
                        style={{ marginBottom: 0 }}
                        value={editTenNguon}
                        onChange={(event) => setEditTenNguon(event.target.value)}
                        placeholder="Tên nguồn"
                      />
                      <input
                        className="filterInput"
                        style={{ marginBottom: 0 }}
                        value={editUrl}
                        onChange={(event) => setEditUrl(event.target.value)}
                        placeholder="Link Google Sheet"
                      />
                      {editError && <span className="empty">{editError}</span>}
                      <div style={{ display: "flex", gap: 8 }}>
                        <button
                          type="button"
                          className="searchButton"
                          disabled={savingEdit}
                          onClick={() => saveEdit(item)}
                        >
                          {savingEdit ? "Đang lưu…" : "Lưu"}
                        </button>
                        <button
                          type="button"
                          className="resetButton"
                          disabled={savingEdit}
                          onClick={cancelEdit}
                        >
                          Hủy
                        </button>
                      </div>
                    </div>
                  );
                }

                const isSyncing = syncingMaNguon === item.ma_nguon;
                const syncResult = syncResults[item.ma_nguon];

                return (
                  <Fragment key={item.ma_nguon}>
                    <div className="parcelListItem">
                      <span
                        className="parcelListDot"
                        style={{
                          backgroundColor: item.kich_hoat ? "#22c55e" : "#94a3b8",
                          cursor: "pointer",
                        }}
                        title={item.kich_hoat ? "Đang kích hoạt — bấm để tắt" : "Đang tắt — bấm để bật"}
                        onClick={() => !isBusy && toggleKichHoat(item)}
                      />
                      <span className="parcelListLabel" title={item.url}>
                        [{item.ma_nguon}] {item.ten_nguon || "(chưa đặt tên)"}
                      </span>
                      <button
                        type="button"
                        className="searchButton"
                        disabled={isBusy || isSyncing}
                        onClick={() => handleSync(item)}
                        title="Đọc lại Google Sheet và cập nhật dữ liệu GCN"
                      >
                        {isSyncing ? "Đang đồng bộ…" : "Đồng bộ"}
                      </button>
                      <button
                        type="button"
                        className="resetButton"
                        disabled={isBusy}
                        onClick={() => startEdit(item)}
                      >
                        Sửa
                      </button>
                      <button
                        type="button"
                        className="resetButton"
                        disabled={isBusy}
                        onClick={() => handleDelete(item)}
                      >
                        {isBusy ? "…" : "Xóa"}
                      </button>
                    </div>

                    {syncResult && (
                      <div
                        className="notice"
                        style={syncResult.ok ? undefined : { color: "#991b1b" }}
                      >
                        [{item.ma_nguon}] {syncResult.message}
                      </div>
                    )}
                  </Fragment>
                );
              })}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

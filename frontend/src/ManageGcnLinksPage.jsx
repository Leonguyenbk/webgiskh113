import { useCallback, useEffect, useState } from "react";

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
            Trang này chỉ quản lý danh sách link — muốn đọc dữ liệu vào
            Supabase phải chạy <code>python main.py</code> trong
            <code> sync_gcn/</code> (thủ công hoặc theo lịch), xem
            hướng dẫn trong <code>sync_gcn/README.md</code>.
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

                return (
                  <div key={item.ma_nguon} className="parcelListItem">
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
                );
              })}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

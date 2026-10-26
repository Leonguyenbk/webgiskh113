import { useEffect, useMemo, useState } from "react";

import { API_URL } from "./config/env";
import {
  deleteGcnChiTiet,
  getGcnChiTiet,
  getGcnDanhSach,
  getXaList,
  updateGcnChiTiet,
} from "./services/parcelService";

const PAGE_SIZE = 100;

// Nhóm trường cho modal "Xem/Sửa" — khớp đúng tên cột public.du_lieu_gcn
// (xem sync_gcn/create_du_lieu_gcn.sql) + nhãn tiếng Việt lấy theo đúng
// cách gọi đã dùng ở biểu Nhóm 4 (Nhom4FormPage.jsx) cho người dùng quen mắt.
const CHI_TIET_FIELD_GROUPS = [
  {
    title: "Thông tin GCN",
    fields: [
      ["sophathanhgcn", "Số phát hành GCN"],
      ["ngaycapgcn", "Ngày cấp GCN"],
      ["sovaosogcn", "Số vào sổ GCN"],
      ["soto_gcn", "Số tờ ghi trên GCN"],
      ["sothua_gcn", "Số thửa ghi trên GCN"],
      ["madinhdanhthuadat", "Mã định danh thửa đất"],
    ],
  },
  {
    title: "Chủ sử dụng / tổ chức",
    fields: [
      ["tentochuc", "Tên tổ chức"],
      ["madinhdanhtochuc", "Mã định danh tổ chức"],
      ["hovatenchusudung", "Họ và tên chủ sử dụng"],
      ["ngaythangnamsinh", "Ngày tháng năm sinh"],
      ["gioitinh", "Giới tính"],
      ["sodinhdanhcanhan", "Số CCCD"],
      ["diachithuongtru", "Địa chỉ thường trú"],
      ["phapnhantrengcn", "Pháp nhân"],
      ["vaitrophapnhan", "Vai trò pháp nhân"],
    ],
  },
  {
    title: "Người sử dụng hiện tại (nếu khác GCN)",
    fields: [
      ["tenchusudunghientai", "Tên người sử dụng hiện tại"],
      ["sodinhdanh_chusudunghientai", "Số định danh cá nhân"],
      ["diachi_chusudunghientai", "Địa chỉ thường trú"],
      ["lydothaydoi", "Lý do thay đổi"],
    ],
  },
  {
    title: "Thửa đất",
    fields: [
      ["diachi_thuadat", "Địa chỉ thửa đất"],
      ["dientichthuadat", "Diện tích thửa đất"],
    ],
  },
  {
    title: "Loại đất 1",
    fields: [
      ["loaidat1", "Loại đất"],
      ["dientich1", "Diện tích"],
      ["nguongoc1", "Nguồn gốc sử dụng"],
      ["hinhthucsudung1", "Hình thức sử dụng"],
      ["thoihansudung1", "Thời hạn sử dụng"],
    ],
  },
  {
    title: "Loại đất 2",
    fields: [
      ["loaidat2", "Loại đất"],
      ["dientich2", "Diện tích"],
      ["nguongoc2", "Nguồn gốc sử dụng"],
      ["hinhthucsudung2", "Hình thức sử dụng"],
      ["thoihansudung2", "Thời hạn sử dụng"],
    ],
  },
  {
    title: "Loại đất 3",
    fields: [
      ["loaidat3", "Loại đất"],
      ["dientich3", "Diện tích"],
      ["nguongoc3", "Nguồn gốc sử dụng"],
      ["hinhthucsudung3", "Hình thức sử dụng"],
      ["thoihansudung3", "Thời hạn sử dụng"],
    ],
  },
  {
    title: "Ghi chú",
    fields: [["ghichu", "Ghi chú"]],
  },
];

function formatSo(n) {
  return Number(n || 0).toLocaleString("vi-VN");
}

function formatNgay(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.toLocaleDateString("vi-VN")} ${d.toLocaleTimeString("vi-VN")}`;
}

export default function DanhSachThuaDatPage({ onNavigateHome }) {
  const [xaList, setXaList] = useState([]);
  const [xaLoading, setXaLoading] = useState(true);
  const [xaError, setXaError] = useState("");

  const [maXa, setMaXa] = useState("");
  const [xaQuery, setXaQuery] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [soToFilter, setSoToFilter] = useState("");
  const [soThuaFilter, setSoThuaFilter] = useState("");
  // Backend chỉ chấp nhận 'asc'/'desc' theo ngày nhập (created_at) trong
  // TỪNG nhóm nguồn — hàm list_du_lieu_gcn_da_nhap trong
  // supabase/schema.sql luôn xếp thửa nhập từ biểu Nhóm 4 lên trước thửa
  // chỉ đồng bộ từ Google Sheet (bất kể ngày nhập), rồi mới áp asc/desc
  // trong từng nhóm.
  const [sortDesc, setSortDesc] = useState(true);
  const [offset, setOffset] = useState(0);
  const [reloadTick, setReloadTick] = useState(0);

  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [totalForm, setTotalForm] = useState(0);
  const [totalKhac, setTotalKhac] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Modal "Xem/Sửa" — chiTietTarget = thửa đang xem (null = đóng modal).
  const [chiTietTarget, setChiTietTarget] = useState(null);
  const [chiTietData, setChiTietData] = useState(null);
  const [chiTietLoading, setChiTietLoading] = useState(false);
  const [chiTietError, setChiTietError] = useState("");
  const [chiTietEdits, setChiTietEdits] = useState({});
  const [chiTietSavingId, setChiTietSavingId] = useState(null);
  const [chiTietSavedAt, setChiTietSavedAt] = useState({});
  const [deletingKey, setDeletingKey] = useState(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    setXaLoading(true);
    setXaError("");
    getXaList()
      .then((result) => setXaList(result?.items || []))
      .catch((err) => setXaError(err.message))
      .finally(() => setXaLoading(false));
  }, []);

  useEffect(() => {
    if (!maXa) {
      setItems([]);
      setTotal(0);
      setTotalForm(0);
      setTotalKhac(0);
      return undefined;
    }

    const controller = new AbortController();
    setLoading(true);
    setError("");

    getGcnDanhSach(
      {
        ma_xa: maXa,
        sort: sortDesc ? "desc" : "asc",
        limit: PAGE_SIZE,
        offset,
        so_to: soToFilter.trim() || undefined,
        so_thua: soThuaFilter.trim() || undefined,
      },
      { signal: controller.signal },
    )
      .then((result) => {
        setItems(result?.items || []);
        setTotal(Number(result?.total) || 0);
        setTotalForm(Number(result?.total_form) || 0);
        setTotalKhac(Number(result?.total_khac) || 0);
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [maXa, sortDesc, offset, soToFilter, soThuaFilter, reloadTick]);

  const filteredXaOptions = useMemo(() => {
    const keyword = xaQuery.trim().toLocaleLowerCase("vi");
    if (!keyword) return xaList;
    return xaList.filter(({ ma_xa, ten_xa }) =>
      `${ten_xa} ${ma_xa}`.toLocaleLowerCase("vi").includes(keyword),
    );
  }, [xaList, xaQuery]);

  const handleSelectXa = (ma_xa, ten_xa) => {
    setMaXa(ma_xa);
    setXaQuery(ten_xa || ma_xa);
    setDropdownOpen(false);
    setOffset(0);
  };

  const handleChangeSoTo = (value) => {
    setSoToFilter(value);
    setOffset(0);
  };

  const handleChangeSoThua = (value) => {
    setSoThuaFilter(value);
    setOffset(0);
  };

  const handleToggleSort = () => {
    setSortDesc((prev) => !prev);
    setOffset(0);
  };

  const rangeFrom = total === 0 ? 0 : offset + 1;
  const rangeTo = Math.min(offset + PAGE_SIZE, total);
  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  const fetchChiTiet = (target) => {
    setChiTietLoading(true);
    setChiTietError("");
    getGcnChiTiet({ ma_xa: target.ma_xa, so_to: target.so_to, so_thua: target.so_thua })
      .then((result) => setChiTietData(result))
      .catch((err) => setChiTietError(err.message))
      .finally(() => setChiTietLoading(false));
  };

  const handleOpenChiTiet = (row) => {
    const target = { ma_xa: row.ma_xa, so_to: row.so_to, so_thua: row.so_thua, ten_xa: row.ten_xa };
    setChiTietTarget(target);
    setChiTietData(null);
    setChiTietError("");
    setChiTietEdits({});
    setChiTietSavedAt({});
    fetchChiTiet(target);
  };

  const handleCloseChiTiet = () => {
    setChiTietTarget(null);
    setChiTietData(null);
    setChiTietError("");
    setChiTietEdits({});
  };

  const handleChiTietFieldChange = (rowId, field, value) => {
    setChiTietEdits((prev) => ({
      ...prev,
      [rowId]: { ...(prev[rowId] || {}), [field]: value },
    }));
  };

  const handleSaveChiTietRow = (rowId) => {
    const edits = chiTietEdits[rowId];
    if (!edits || Object.keys(edits).length === 0 || !chiTietTarget) return;

    setChiTietSavingId(rowId);
    updateGcnChiTiet(
      rowId,
      { ma_xa: chiTietTarget.ma_xa, so_to: chiTietTarget.so_to, so_thua: chiTietTarget.so_thua },
      edits,
    )
      .then((result) => {
        setChiTietData((prev) => ({
          ...prev,
          items: prev.items.map((item) => (item.id === rowId ? { ...item, ...result.item } : item)),
        }));
        setChiTietEdits((prev) => {
          const next = { ...prev };
          delete next[rowId];
          return next;
        });
        setChiTietSavedAt((prev) => ({ ...prev, [rowId]: Date.now() }));
      })
      .catch((err) => setChiTietError(err.message))
      .finally(() => setChiTietSavingId(null));
  };

  // Xuất Excel toàn bộ thửa đã nhập của xã đang chọn (cùng bộ lọc số
  // tờ/số thửa + chiều sắp xếp), kèm ngày nhập và nguồn.
  const handleExportExcel = async () => {
    if (!maXa || exporting) return;
    setExporting(true);
    setError("");
    try {
      const params = new URLSearchParams({ ma_xa: maXa, sort: sortDesc ? "desc" : "asc" });
      if (soToFilter.trim()) params.set("so_to", soToFilter.trim());
      if (soThuaFilter.trim()) params.set("so_thua", soThuaFilter.trim());
      const res = await fetch(`${API_URL}/api/gcn-danh-sach/export?${params}`);
      if (!res.ok) {
        let message = `Xuất Excel thất bại (HTTP ${res.status})`;
        try {
          message = (await res.json())?.error || message;
        } catch {
          /* body không phải JSON */
        }
        throw new Error(message);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `danh_sach_da_nhap_${maXa}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    } finally {
      setExporting(false);
    }
  };

  const handleDeleteRow = (row) => {
    const xacNhan = window.confirm(
      `Xóa TOÀN BỘ dữ liệu đã nhập cho Tờ ${row.so_to}, Thửa ${row.so_thua} ` +
        `(${row.ten_xa || row.ma_xa}) để nhập lại từ đầu?\n\n` +
        "Hành động này không thể hoàn tác.",
    );
    if (!xacNhan) return;

    const rowKey = `${row.ma_xa}_${row.so_to}_${row.so_thua}`;
    setDeletingKey(rowKey);
    setError("");
    deleteGcnChiTiet({ ma_xa: row.ma_xa, so_to: row.so_to, so_thua: row.so_thua })
      .then(() => setReloadTick((prev) => prev + 1))
      .catch((err) => setError(err.message))
      .finally(() => setDeletingKey(null));
  };

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Danh sách thửa đã nhập</h1>
          <p>Tra cứu các thửa đã có dữ liệu GCN (du_lieu_gcn) theo xã/phường — mỗi thửa 1 dòng dù có nhiều chủ sử dụng</p>
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

      <section className="dashboardWrap">
        {xaError && (
          <div className="notice error">
            <strong>Không tải được danh sách xã/phường</strong>
            <span>{xaError}</span>
          </div>
        )}

        <div
          className="importCard statsTableCard"
          style={{ width: "80%", maxWidth: "80%", margin: "0 auto" }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-end",
              flexWrap: "wrap",
              gap: 12,
            }}
          >
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-end", gap: 12 }}>
              <div style={{ width: 280, maxWidth: "100%" }}>
                <label htmlFor="daNhapXa">Xã / phường</label>
                <div className="comboBox" style={{ marginBottom: 0 }}>
                  <input
                    id="daNhapXa"
                    type="text"
                    className="filterInput"
                    autoComplete="off"
                    disabled={xaLoading}
                    value={xaQuery}
                    placeholder="Nhập tên xã/phường để tìm…"
                    style={{ width: "100%" }}
                    onChange={(event) => {
                      setXaQuery(event.target.value);
                      setMaXa("");
                      setDropdownOpen(true);
                    }}
                    onFocus={() => setDropdownOpen(true)}
                    onBlur={() => setDropdownOpen(false)}
                  />

                  {dropdownOpen && (
                    <div className="comboBoxList">
                      {filteredXaOptions.length === 0 ? (
                        <div className="comboBoxEmpty">Không tìm thấy xã/phường</div>
                      ) : (
                        filteredXaOptions.map(({ ma_xa, ten_xa }) => (
                          <div
                            key={ma_xa}
                            className={`comboBoxItem${ma_xa === maXa ? " active" : ""}`}
                            onMouseDown={(event) => {
                              event.preventDefault();
                              handleSelectXa(ma_xa, ten_xa);
                            }}
                          >
                            {ten_xa || ma_xa}
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div style={{ width: 100 }}>
                <label htmlFor="daNhapSoTo">Số tờ</label>
                <input
                  id="daNhapSoTo"
                  type="text"
                  inputMode="numeric"
                  className="filterInput"
                  autoComplete="off"
                  value={soToFilter}
                  placeholder="Tất cả"
                  style={{ width: "100%", marginBottom: 0 }}
                  onChange={(event) => handleChangeSoTo(event.target.value)}
                />
              </div>

              <div style={{ width: 100 }}>
                <label htmlFor="daNhapSoThua">Số thửa</label>
                <input
                  id="daNhapSoThua"
                  type="text"
                  inputMode="numeric"
                  className="filterInput"
                  autoComplete="off"
                  value={soThuaFilter}
                  placeholder="Tất cả"
                  style={{ width: "100%", marginBottom: 0 }}
                  onChange={(event) => handleChangeSoThua(event.target.value)}
                />
              </div>
            </div>

            {maXa && (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <label style={{ margin: 0 }}>
                    {loading
                      ? "Đang tải…"
                      : `${formatSo(rangeFrom)}–${formatSo(rangeTo)} / ${formatSo(total)} thửa`}
                  </label>
                  <button
                    type="button"
                    className="downloadButton"
                    disabled={!canPrev || loading}
                    style={{ opacity: !canPrev || loading ? 0.5 : 1 }}
                    onClick={() => setOffset((prev) => Math.max(0, prev - PAGE_SIZE))}
                  >
                    ← Trang trước
                  </button>
                  <button
                    type="button"
                    className="downloadButton"
                    disabled={!canNext || loading}
                    style={{ opacity: !canNext || loading ? 0.5 : 1 }}
                    onClick={() => setOffset((prev) => prev + PAGE_SIZE)}
                  >
                    Trang sau →
                  </button>
                  <button
                    type="button"
                    className="downloadButton"
                    disabled={exporting || loading || total === 0}
                    style={{ opacity: exporting || loading || total === 0 ? 0.5 : 1 }}
                    onClick={handleExportExcel}
                  >
                    {exporting ? "Đang xuất…" : "⬇ Xuất Excel"}
                  </button>
                </div>
                {!loading && (
                  <span style={{ fontSize: 13, color: "#666" }}>
                    Nguồn: biểu Nhóm 4 {formatSo(totalForm)} thửa · nguồn khác (đồng bộ Sheet) {formatSo(totalKhac)} thửa
                  </span>
                )}
              </div>
            )}
          </div>

          {!maXa ? (
            <div className="emptyState" style={{ marginTop: 10 }}>
              <div>📋</div>
              <strong>Chưa chọn xã/phường</strong>
              <span>Chọn 1 xã/phường ở trên để xem danh sách đã nhập.</span>
            </div>
          ) : (
            <>
              {error && (
                <div className="notice error" style={{ marginTop: 10 }}>
                  <strong>Không tải được dữ liệu</strong>
                  <span>{error}</span>
                </div>
              )}

              <div className="statsTableWrap" style={{ marginTop: 10 }}>
                <table className="statsTable">
                  <thead>
                    <tr>
                      <th>Xã / phường</th>
                      <th>Số tờ</th>
                      <th>Số thửa</th>
                      <th>Mã định danh</th>
                      <th
                        onClick={handleToggleSort}
                        style={{ cursor: "pointer", userSelect: "none", whiteSpace: "nowrap" }}
                        title="Bấm để đổi chiều sắp xếp"
                      >
                        Ngày nhập
                        <span style={{ marginLeft: 4 }}>{sortDesc ? "▼" : "▲"}</span>
                      </th>
                      <th>Thao tác</th>
                    </tr>
                  </thead>
                  <tbody>
                    {!loading && items.length === 0 ? (
                      <tr>
                        <td colSpan={6}>Xã/phường này chưa có dữ liệu trong du_lieu_gcn</td>
                      </tr>
                    ) : (
                      items.map((row, index) => (
                        <tr key={`${row.ma_xa}_${row.so_to}_${row.so_thua}_${index}`}>
                          <td>{row.ten_xa || row.ma_xa}</td>
                          <td>{row.so_to}</td>
                          <td>{row.so_thua}</td>
                          <td>{row.ma_dinh_danh || ""}</td>
                          <td>{formatNgay(row.ngay_nhap)}</td>
                          <td>
                            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                              <button
                                type="button"
                                className="downloadButton"
                                onClick={() => handleOpenChiTiet(row)}
                              >
                                👁 Xem / Sửa
                              </button>
                              {row.is_form && (
                                <button
                                  type="button"
                                  className="downloadButton"
                                  disabled={deletingKey === `${row.ma_xa}_${row.so_to}_${row.so_thua}`}
                                  onClick={() => handleDeleteRow(row)}
                                >
                                  {deletingKey === `${row.ma_xa}_${row.so_to}_${row.so_thua}`
                                    ? "Đang xóa…"
                                    : "🗑 Xóa"}
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </section>

      {chiTietTarget && (
        <div className="modalOverlay" onMouseDown={handleCloseChiTiet}>
          <div className="chiTietModalCard" onMouseDown={(event) => event.stopPropagation()}>
            <div className="chiTietModalHeader">
              <div>
                <h2>Thông tin đã nhập</h2>
                <span>
                  {chiTietTarget.ten_xa || chiTietTarget.ma_xa} — Tờ {chiTietTarget.so_to}, Thửa{" "}
                  {chiTietTarget.so_thua}
                </span>
              </div>
              <button type="button" className="chiTietModalClose" onClick={handleCloseChiTiet}>
                ✕
              </button>
            </div>

            <div className="chiTietModalBody">
              {!chiTietData && chiTietLoading && <p style={{ marginTop: 6 }}>Đang tải…</p>}

              {!chiTietData && chiTietError && (
                <div className="notice error" style={{ marginTop: 6 }}>
                  <span>{chiTietError}</span>
                </div>
              )}

              {chiTietData && (
                <>
                  <span
                    className={`chiTietNguonBadge ${chiTietData.sua_duoc ? "suaDuoc" : "chiXem"}`}
                  >
                    Nguồn: {chiTietData.ten_nguon}
                    {chiTietData.sua_duoc ? " — sửa được" : " — chỉ xem"}
                  </span>
                  {!chiTietData.sua_duoc && (
                    <p style={{ fontSize: 12, color: "#9a6b0a", marginTop: -4 }}>
                      Dữ liệu đồng bộ từ Google Sheet — sửa trực tiếp trên Sheet nguồn, hệ thống sẽ tự
                      đồng bộ lại ở lần sau. Không sửa được ở đây.
                    </p>
                  )}
                  {chiTietError && (
                    <div className="notice error" style={{ marginTop: 10 }}>
                      <span>{chiTietError}</span>
                    </div>
                  )}

                  {chiTietData.items.map((item, ownerIndex) => {
                    const edits = chiTietEdits[item.id] || {};
                    const hasEdits = Object.keys(edits).length > 0;
                    const valueOf = (field) => (field in edits ? edits[field] : item[field] || "");
                    return (
                      <div className="chiTietOwnerCard" key={item.id}>
                        <div className="chiTietOwnerHeader">
                          <strong>
                            Chủ sử dụng #{ownerIndex + 1}
                            {item.hovatenchusudung ? `: ${item.hovatenchusudung}` : ""}
                          </strong>
                          {chiTietData.sua_duoc && (
                            <button
                              type="button"
                              className="downloadButton"
                              disabled={!hasEdits || chiTietSavingId === item.id}
                              onClick={() => handleSaveChiTietRow(item.id)}
                            >
                              {chiTietSavingId === item.id
                                ? "Đang lưu…"
                                : chiTietSavedAt[item.id]
                                  ? "💾 Đã lưu — lưu tiếp"
                                  : "💾 Lưu thay đổi"}
                            </button>
                          )}
                        </div>

                        {CHI_TIET_FIELD_GROUPS.map((group) => (
                          <div className="chiTietFieldGroup" key={group.title}>
                            <h4>{group.title}</h4>
                            <div className="chiTietFieldGrid">
                              {group.fields.map(([field, label]) => (
                                <div className="chiTietField" key={field}>
                                  <label htmlFor={`${item.id}_${field}`}>{label}</label>
                                  <input
                                    id={`${item.id}_${field}`}
                                    type="text"
                                    autoComplete="off"
                                    disabled={!chiTietData.sua_duoc}
                                    value={valueOf(field)}
                                    onChange={(event) =>
                                      handleChiTietFieldChange(item.id, field, event.target.value)
                                    }
                                  />
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    );
                  })}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

import { useCallback, useEffect, useRef, useState } from "react";

import { capNhatPhanLoai, getCapNhatPhanLoaiJob } from "./services/mplisService";

const POLL_INTERVAL_MS = 1500;

const STATUS_LABELS = {
  running: "Đang chạy",
  done: "Hoàn tất",
  error: "Lỗi",
  session_expired: "Phiên MPLIS đã hết hạn",
};

const SINGLE_RESULT_FIELDS = [
  { key: "phan_loai_ke_hoach_2959", label: "Phân loại" },
  {
    key: "da_xuat_so_dia_chinh_dien_tu",
    label: "Sổ địa chính điện tử",
    format: (v) => (v ? "Đã xuất" : "Chưa xuất"),
  },
  {
    key: "dong_bo_3_khoi",
    label: "Đồng bộ 3 khối",
    format: (v) => (v ? "Đã đồng bộ" : "Chưa đồng bộ"),
  },
  {
    key: "khop_csdlqg_dan_cu",
    label: "CSDLQG dân cư",
    format: (v, mapped) =>
      mapped.khong_xac_dinh_csdlqg_dan_cu
        ? "Không xác định"
        : v
          ? "Khớp"
          : "Chưa khớp",
  },
  {
    key: "van_hanh_24_7",
    label: "Vận hành 24/7",
    format: (v) => (v ? "Có" : "Không"),
  },
];

function computeMode(soTo, soThua) {
  const hasSoTo = soTo.trim() !== "";
  const hasSoThua = soThua.trim() !== "";
  if (hasSoTo && hasSoThua) return "single";
  if (!hasSoTo && !hasSoThua) return "ward";
  return "invalid";
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("vi-VN");
}

export default function MplisSyncPage({ onNavigateHome }) {
  const [maXa, setMaXa] = useState("");
  const [soTo, setSoTo] = useState("");
  const [soThua, setSoThua] = useState("");
  // Mã xác thực của chính trang quản trị này (IMPORT_TOKEN backend, header
  // X-Import-Token) — KHÁC với Request Verification Token của MPLIS bên
  // dưới, không được dùng lẫn.
  const [authToken, setAuthToken] = useState("");
  const [mplisToken, setMplisToken] = useState("");
  const [cookie, setCookie] = useState("");
  const [cookieVisible, setCookieVisible] = useState(false);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState("");

  const [singleResult, setSingleResult] = useState(null);

  const [job, setJob] = useState(null);
  const pollTimerRef = useRef(null);

  const mode = computeMode(soTo, soThua);
  const jobRunning = job?.status === "running";

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const pollJob = useCallback(
    (jobId) => {
      stopPolling();

      const tick = async () => {
        try {
          const body = await getCapNhatPhanLoaiJob(jobId, authToken);

          setJob(body);
          if (body.status !== "running") stopPolling();
        } catch (err) {
          setFormError(err.message);
          stopPolling();
        }
      };

      tick();
      pollTimerRef.current = setInterval(tick, POLL_INTERVAL_MS);
    },
    [stopPolling, authToken],
  );

  const startSingle = async () => {
    setSubmitting(true);
    setFormError("");
    setSingleResult(null);

    try {
      const body = await capNhatPhanLoai(
        {
          ma_xa: maXa.trim(),
          so_to: soTo.trim(),
          so_thua: soThua.trim(),
          request_verification_token: mplisToken,
          cookie,
        },
        authToken,
      );

      setSingleResult(body);
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const startWard = async () => {
    setConfirmOpen(false);
    setSubmitting(true);
    setFormError("");
    setJob(null);

    try {
      const body = await capNhatPhanLoai(
        {
          ma_xa: maXa.trim(),
          so_to: "",
          so_thua: "",
          request_verification_token: mplisToken,
          cookie,
        },
        authToken,
        { errorFallback: "Không khởi động được tiến trình" },
      );

      setJob({ status: body.status, job_id: body.job_id, ma_xa: maXa.trim() });
      pollJob(body.job_id);
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    setFormError("");

    if (!maXa.trim()) {
      setFormError("Chưa nhập mã xã.");
      return;
    }
    if (mode === "invalid") {
      setFormError("Phải nhập cả Số tờ và Số thửa hoặc để trống cả hai.");
      return;
    }
    if (!mplisToken.trim()) {
      setFormError("Chưa nhập Request Verification Token.");
      return;
    }
    if (!cookie.trim()) {
      setFormError("Chưa nhập Cookie MPLIS.");
      return;
    }

    if (mode === "single") {
      startSingle();
    } else {
      setConfirmOpen(true);
    }
  };

  const busy = submitting || jobRunning;

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Cập nhật MPLIS</h1>
          <p>Lấy trạng thái thửa đất từ MPLIS, cập nhật vào dong_bo_du_lieu</p>
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
        <form className="importCard mplisCard" onSubmit={handleSubmit}>
          <label htmlFor="mplisAuthToken">Mã xác thực</label>
          <input
            id="mplisAuthToken"
            type="password"
            value={authToken}
            onChange={(event) => setAuthToken(event.target.value)}
            placeholder="Nhập mã do quản trị viên cấp (nếu có)"
            disabled={busy}
          />

          <label htmlFor="mplisMaXa">Mã xã *</label>
          <input
            id="mplisMaXa"
            className="filterInput"
            value={maXa}
            onChange={(event) => setMaXa(event.target.value)}
            placeholder="VD: 24133"
            disabled={busy}
          />

          <div className="filterRow">
            <div>
              <label htmlFor="mplisSoTo">Số tờ</label>
              <input
                id="mplisSoTo"
                className="filterInput"
                value={soTo}
                onChange={(event) => setSoTo(event.target.value)}
                placeholder="VD: 84"
                disabled={busy}
              />
            </div>
            <div>
              <label htmlFor="mplisSoThua">Số thửa</label>
              <input
                id="mplisSoThua"
                className="filterInput"
                value={soThua}
                onChange={(event) => setSoThua(event.target.value)}
                placeholder="VD: 951"
                disabled={busy}
              />
            </div>
          </div>

          {mode === "single" && maXa.trim() && (
            <div className="notice">
              <strong>Chế độ: Cập nhật một thửa</strong>
              <span>
                Xã {maXa.trim()} · Tờ {soTo.trim()} · Thửa {soThua.trim()}
              </span>
            </div>
          )}
          {mode === "ward" && maXa.trim() && (
            <div className="notice">
              <strong>Chế độ: Cập nhật toàn bộ xã {maXa.trim()}</strong>
            </div>
          )}
          {mode === "invalid" && (
            <div className="notice error">
              <span>Phải nhập cả Số tờ và Số thửa hoặc để trống cả hai.</span>
            </div>
          )}

          <label htmlFor="mplisToken">Request Verification Token *</label>
          <textarea
            id="mplisToken"
            className="filterInput mplisTextarea"
            value={mplisToken}
            onChange={(event) => setMplisToken(event.target.value)}
            placeholder="__requestverificationtoken lấy từ trình duyệt MPLIS"
            disabled={busy}
          />

          <label htmlFor="mplisCookie">
            Cookie MPLIS *
            <button
              type="button"
              className="mplisToggleVisible"
              onClick={() => setCookieVisible((v) => !v)}
            >
              {cookieVisible ? "Ẩn" : "Hiện"}
            </button>
          </label>
          <textarea
            id="mplisCookie"
            className={`filterInput mplisTextarea${cookieVisible ? "" : " mplisMasked"}`}
            value={cookie}
            onChange={(event) => setCookie(event.target.value)}
            placeholder="Cookie đăng nhập MPLIS (dán nguyên văn)"
            disabled={busy}
          />

          <button type="submit" className="importButton" disabled={busy}>
            {busy ? "Đang xử lý…" : "CẬP NHẬT DỮ LIỆU"}
          </button>

          {formError && (
            <div className="notice error">
              <strong>Có lỗi xảy ra</strong>
              <span>{formError}</span>
            </div>
          )}

          <p className="importHint">
            Token và Cookie chỉ dùng cho lần cập nhật này — backend không lưu
            lại (không ghi Supabase, không ghi file, không ghi log). Mỗi lần
            cập nhật phải nhập lại.
          </p>
        </form>

        {singleResult && (
          <div className="importCard mplisCard">
            <label>Kết quả</label>

            {singleResult.status === "not_found_mplis" && (
              <div className="notice error">
                <span>Không tìm thấy thửa trên MPLIS.</span>
              </div>
            )}

            {(singleResult.status === "updated" || singleResult.status === "inserted") && (
              <div className="notice">
                <strong>
                  {singleResult.status === "inserted"
                    ? "ĐÃ THÊM MỚI"
                    : "CẬP NHẬT THÀNH CÔNG"}
                </strong>
                <span>
                  Mã xã: {singleResult.mapped.ma_xa} · Tờ {singleResult.mapped.so_to} ·
                  Thửa {singleResult.mapped.so_thua}
                </span>
                {SINGLE_RESULT_FIELDS.map(({ key, label, format }) => (
                  <span key={key}>
                    {label}: {format ? format(singleResult.mapped[key], singleResult.mapped) : String(singleResult.mapped[key])}
                  </span>
                ))}
              </div>
            )}

            {singleResult.status === "error" && (
              <div className="notice error">
                <span>Có lỗi khi ghi dữ liệu, thử lại sau.</span>
              </div>
            )}
          </div>
        )}

        {job && (
          <div className="importCard mplisCard">
            <label>
              {job.status === "running"
                ? "Đang cập nhật dữ liệu MPLIS"
                : `Xã ${job.ma_xa}: ${STATUS_LABELS[job.status] || job.status}`}
            </label>

            {job.status === "session_expired" && (
              <div className="notice error">
                <span>
                  Phiên MPLIS đã hết hạn. Vui lòng nhập Cookie và Token mới rồi
                  bấm "CẬP NHẬT DỮ LIỆU" lại.
                </span>
              </div>
            )}

            {job.status === "error" && (
              <div className="notice error">
                <span>{job.message || "Cập nhật thất bại."}</span>
              </div>
            )}

            {job.total > 0 && (
              <>
                <div className="mplisProgressTrack">
                  <div
                    className="mplisProgressFill"
                    style={{ width: `${Math.min(100, job.percent || 0)}%` }}
                  />
                </div>
                <span className="mplisProgressPercent">{job.percent?.toFixed(1) ?? 0}%</span>

                <div className="mplisStats">
                  <div>
                    <span>Tổng MPLIS</span>
                    <strong>{formatNumber(job.total)}</strong>
                  </div>
                  <div>
                    <span>Đã xử lý</span>
                    <strong>{formatNumber(job.processed)}</strong>
                  </div>
                  <div>
                    <span>Đã cập nhật</span>
                    <strong>{formatNumber(job.updated)}</strong>
                  </div>
                  <div>
                    <span>Đã thêm mới</span>
                    <strong>{formatNumber(job.inserted)}</strong>
                  </div>
                  <div>
                    <span>Trùng dữ liệu</span>
                    <strong>{formatNumber(job.duplicates)}</strong>
                  </div>
                  <div>
                    <span>Lỗi</span>
                    <strong>{formatNumber(job.errors)}</strong>
                  </div>
                </div>
              </>
            )}

            {job.status !== "running" && job.started_at && (
              <span className="importHint">
                Bắt đầu: {new Date(job.started_at).toLocaleString("vi-VN")}
                {job.finished_at &&
                  ` · Hoàn thành: ${new Date(job.finished_at).toLocaleString("vi-VN")}`}
              </span>
            )}
          </div>
        )}
      </section>

      {confirmOpen && (
        <div className="modalOverlay" role="dialog" aria-modal="true">
          <div className="modalCard">
            <h2>Cập nhật toàn bộ xã?</h2>
            <p>
              Hệ thống sẽ lấy toàn bộ dữ liệu MPLIS của xã <strong>{maXa.trim()}</strong>{" "}
              và cập nhật/thêm mới các thửa tương ứng trong cơ sở dữ liệu.
            </p>
            <p>Quá trình có thể mất một khoảng thời gian.</p>
            <div className="modalActions">
              <button
                type="button"
                className="resetButton"
                onClick={() => setConfirmOpen(false)}
              >
                HỦY
              </button>
              <button type="button" className="importButton" onClick={startWard}>
                BẮT ĐẦU CẬP NHẬT
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

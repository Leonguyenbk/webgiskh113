import { useEffect, useMemo, useState } from "react";

import { getThongKeKhuVuc } from "./services/parcelService";
import { NHOM3_PALETTE } from "./utils/nhom3ChartColors";

const KHU_VUC = "Đông Hòa";
// 7 ngày đang xét + 7 ngày liền trước + hôm nay (chưa trọn ngày, không tính).
const SO_NGAY_TAI = 15;

function formatSo(n) {
  return Math.round(Number(n || 0)).toLocaleString("vi-VN");
}

function formatPhanTram(v) {
  return `${(v * 100).toLocaleString("vi-VN", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

function formatThayDoi(v) {
  if (v === null) return "—";
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${formatPhanTram(Math.abs(v))}`;
}

function ngayTruoc(ngay, soNgay) {
  const d = new Date(`${ngay}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - soNgay);
  return d.toISOString().slice(0, 10);
}

function nhanNgay(ngay) {
  return `${ngay.slice(8, 10)}/${ngay.slice(5, 7)}`;
}

function tinhChiSo(thuaBayNgay, thuaTruoc, conThieu) {
  return {
    bq: thuaBayNgay / 7,
    thayDoi: thuaTruoc ? thuaBayNgay / thuaTruoc - 1 : null,
    ngayHet: thuaBayNgay ? Math.round(conThieu / (thuaBayNgay / 7)) : null,
  };
}

function tinhSoLieu(data) {
  const homNay = data.tao_luc.slice(0, 10);
  const ngayXet = Array.from({ length: 7 }, (_, i) => ngayTruoc(homNay, 7 - i));
  const ngayLienTruoc = ngayXet.map((ngay) => ngayTruoc(ngay, 7));

  const rows = [...data.theo_xa]
    .sort((a, b) => a.ma_xa.localeCompare(b.ma_xa))
    .map((x, i) => {
      const theoNgay = new Map(
        (data.nhap_bieu_web_theo_ngay[x.ma_xa] || []).map((r) => [r.ngay, Number(r.so_thua)]),
      );
      const daily = ngayXet.map((ngay) => theoNgay.get(ngay) || 0);
      const thuaBayNgay = daily.reduce((s, v) => s + v, 0);
      const thuaTruoc = ngayLienTruoc.reduce((s, ngay) => s + (theoNgay.get(ngay) || 0), 0);
      const daLam = (x.da_nhom_1_2_da_nhap || 0) + (x.da_thu_thap || 0);
      return {
        ...x,
        ...tinhChiSo(thuaBayNgay, thuaTruoc, x.con_thieu),
        color: NHOM3_PALETTE[i % NHOM3_PALETTE.length],
        daily,
        thuaBayNgay,
        thuaTruoc,
        homNay: theoNgay.get(homNay) || 0,
        daLam,
        dat: x.tong ? daLam / x.tong : 0,
        datKeHoach: x.tong_ke_hoach ? (daLam + (x.loai_123_da_lam || 0)) / x.tong_ke_hoach : 0,
      };
    });

  return { ngayXet, rows };
}

function tinhTong(rows) {
  const cong = (key) => rows.reduce((s, r) => s + (r[key] || 0), 0);
  const thuaBayNgay = cong("thuaBayNgay");
  const conThieu = cong("con_thieu");
  const daLam = cong("daLam");
  const tongKeHoach = cong("tong_ke_hoach");
  return {
    ...tinhChiSo(thuaBayNgay, cong("thuaTruoc"), conThieu),
    thuaBayNgay,
    conThieu,
    dat: cong("tong") ? daLam / cong("tong") : 0,
    datKeHoach: tongKeHoach ? (daLam + cong("loai_123_da_lam")) / tongKeHoach : 0,
  };
}

const PHAN_NHOM_3 = [
  { key: "daLamTruoc", label: "Đã làm trước đó", color: NHOM3_PALETTE[0] },
  { key: "thuaBayNgay", label: "Nhập trong 7 ngày", color: NHOM3_PALETTE[1] },
  { key: "con_thieu", label: "Còn lại", color: "#c9d6d3" },
];

// Biểu đồ bánh Nhóm 3 của 1 đơn vị, tính tất cả: tổng = tổng theo kế hoạch
// (gồm Loại 1+2+3) = đã làm + còn lại.
function BieuDoBanh({ row }) {
  const size = 120;
  const center = size / 2;
  const radius = 56;
  const daLam = row.daLam + (row.loai_123_da_lam || 0);
  const values = {
    daLamTruoc: Math.max(0, daLam - row.thuaBayNgay),
    thuaBayNgay: Math.min(row.thuaBayNgay, daLam),
    con_thieu: row.con_thieu || 0,
  };
  const total = PHAN_NHOM_3.reduce((s, p) => s + values[p.key], 0);

  let start = -Math.PI / 2;
  const slices = PHAN_NHOM_3.map((p) => {
    const share = total ? values[p.key] / total : 0;
    const end = start + share * 2 * Math.PI;
    const x1 = center + radius * Math.cos(start);
    const y1 = center + radius * Math.sin(start);
    const x2 = center + radius * Math.cos(end);
    const y2 = center + radius * Math.sin(end);
    const path = `M ${center} ${center} L ${x1} ${y1} A ${radius} ${radius} 0 ${share > 0.5 ? 1 : 0} 1 ${x2} ${y2} Z`;
    start = end;
    return { ...p, value: values[p.key], share, path };
  });

  return (
    <div className="kvPie">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`Tỷ lệ Nhóm 3 của ${row.ten_xa}`}>
        {slices.map(
          (s) =>
            s.share > 0 && (
              <path key={s.key} d={s.path} fill={s.color} stroke="#fff" strokeWidth={1.5}>
                <title>{`${s.label}: ${formatSo(s.value)} thửa (${formatPhanTram(s.share)})`}</title>
              </path>
            ),
        )}
      </svg>
      <div className="pieLegend">
        {slices.map((s) => (
          <div key={s.key}>
            <span style={{ background: s.color }} />
            <label>{s.label}</label>
            <strong>
              {formatSo(s.value)} <span style={{ fontWeight: 400 }}>({formatPhanTram(s.share)})</span>
            </strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function BieuDoTheoNgay({ ngayXet, rows }) {
  const w = 640;
  const h = 170;
  const m = { t: 22, r: 8, b: 24, l: 8 };
  const tongNgay = ngayXet.map((_, i) => rows.reduce((s, r) => s + r.daily[i], 0));
  const max = Math.max(1, ...tongNgay);
  const step = (w - m.l - m.r) / ngayXet.length;
  const barW = Math.min(44, step * 0.6);
  const scale = (v) => (v / max) * (h - m.t - m.b);

  return (
    <>
      <svg width="100%" viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Số thửa nhập theo ngày">
        <line x1={m.l} x2={w - m.r} y1={h - m.b} y2={h - m.b} stroke="#c9d6d3" />
        {ngayXet.map((ngay, i) => {
          const x = m.l + step * i + (step - barW) / 2;
          let y = h - m.b;
          return (
            <g key={ngay}>
              {rows.map((r) => {
                const bh = scale(r.daily[i]);
                y -= bh;
                return (
                  bh > 0 && (
                    <rect key={r.ma_xa} x={x} y={y} width={barW} height={bh} fill={r.color} stroke="#fff" strokeWidth={1.5}>
                      <title>{`${nhanNgay(ngay)} — ${r.ten_xa}: ${formatSo(r.daily[i])} thửa`}</title>
                    </rect>
                  )
                );
              })}
              <text x={x + barW / 2} y={y - 6} textAnchor="middle" fontSize={12} fill="#102a2b">
                {formatSo(tongNgay[i])}
              </text>
              <text x={x + barW / 2} y={h - 7} textAnchor="middle" fontSize={12} fill="#6a817e">
                {nhanNgay(ngay)}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="kvLegend">
        {rows.map((r) => (
          <span key={r.ma_xa}>
            <i style={{ background: r.color }} />
            {r.ten_xa}
          </span>
        ))}
      </div>
    </>
  );
}

export default function KhuVucDongHoaPage({ onNavigateHome }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [maXaChon, setMaXaChon] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    getThongKeKhuVuc({ khu_vuc: KHU_VUC, so_ngay: SO_NGAY_TAI }, { signal: controller.signal })
      .then((result) => setData(result))
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const soLieu = useMemo(() => (data ? tinhSoLieu(data) : null), [data]);
  const rowsChon = useMemo(
    () => (soLieu ? soLieu.rows.filter((r) => !maXaChon || r.ma_xa === maXaChon) : []),
    [soLieu, maXaChon],
  );
  const tong = useMemo(() => tinhTong(rowsChon), [rowsChon]);
  const kyXet = soLieu ? `${nhanNgay(soLieu.ngayXet[0])}–${nhanNgay(soLieu.ngayXet[6])}` : "";
  const capNhat = data?.cap_nhat_luc ? new Date(data.cap_nhat_luc).toLocaleString("vi-VN") : "";

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Tiến độ nhập biểu khu vực Đông Hòa</h1>
          <p>Phường Đông Hòa, Phường Hòa Hiệp, Xã Hòa Xuân — tốc độ nhập biểu và tỷ lệ Nhóm 3</p>
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
        {loading && <div className="notice">Đang tải dữ liệu thống kê…</div>}

        {error && (
          <div className="notice error">
            <strong>Không tải được dữ liệu</strong>
            <span>{error}</span>
          </div>
        )}

        {soLieu && (
          <>
            <div className="kvFilter">
              <label htmlFor="kv-don-vi">Đơn vị</label>
              <select id="kv-don-vi" value={maXaChon} onChange={(event) => setMaXaChon(event.target.value)}>
                <option value="">Cả khu vực</option>
                {soLieu.rows.map((r) => (
                  <option key={r.ma_xa} value={r.ma_xa}>
                    {r.ten_xa}
                  </option>
                ))}
              </select>
            </div>

            <div className="statTiles">
              <div className="statTile">
                <span>Tốc độ nhập biểu (thửa/ngày)</span>
                <strong>{formatSo(tong.bq)}</strong>
                <span>
                  {formatSo(tong.thuaBayNgay)} thửa 7 ngày, {formatThayDoi(tong.thayDoi)} so với 7 ngày trước
                </span>
              </div>
              <div className="statTile">
                <span>Còn lại</span>
                <strong>{formatSo(tong.conThieu)}</strong>
                <span>{formatPhanTram(1 - tong.datKeHoach)} khối lượng Nhóm 3</span>
              </div>
              <div className="statTile">
                <span>Tỷ lệ Nhóm 3 đã làm</span>
                <strong>{formatPhanTram(tong.datKeHoach)}</strong>
                <span>Gồm Loại 1+2+3; riêng Loại 4 {formatPhanTram(tong.dat)}</span>
              </div>
              <div className="statTile">
                <span>Số ngày để hết (ước tính)</span>
                <strong>{tong.ngayHet === null ? "—" : formatSo(tong.ngayHet)}</strong>
              </div>
            </div>

            <div className="kvGrid">
              {rowsChon.map((r) => (
                <div className="importCard statsTableCard" key={r.ma_xa}>
                  <label>{r.ten_xa}</label>
                  <p className="kvSpeed">
                    <strong>{formatSo(r.bq)}</strong> thửa/ngày · đạt {formatPhanTram(r.datKeHoach)}
                  </p>
                  <BieuDoBanh row={r} />
                </div>
              ))}
            </div>

            <div className="kvPair">
            <div className="importCard statsTableCard">
              <label>Số thửa nhập theo ngày ({kyXet})</label>
              <BieuDoTheoNgay ngayXet={soLieu.ngayXet} rows={rowsChon} />
            </div>

            <div className="importCard statsTableCard">
              <label>So sánh các đơn vị</label>
              <div className="statsTableWrap">
                <table className="statsTable">
                  <thead>
                    <tr>
                      <th>Xã/phường</th>
                      <th>Thửa/ngày</th>
                      <th>Thửa 7 ngày</th>
                      <th>7 ngày trước</th>
                      <th>Thay đổi</th>
                      <th>Hôm nay</th>
                      <th>Còn lại</th>
                      <th>Tỷ lệ Nhóm 3</th>
                      <th>Riêng Loại 4</th>
                      <th>Số ngày để hết</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rowsChon.map((r) => (
                      <tr key={r.ma_xa}>
                        <td>{r.ten_xa}</td>
                        <td>{formatSo(r.bq)}</td>
                        <td>{formatSo(r.thuaBayNgay)}</td>
                        <td>{formatSo(r.thuaTruoc)}</td>
                        <td>{formatThayDoi(r.thayDoi)}</td>
                        <td>{formatSo(r.homNay)}</td>
                        <td>{formatSo(r.con_thieu)}</td>
                        <td>{formatPhanTram(r.datKeHoach)}</td>
                        <td>{formatPhanTram(r.dat)}</td>
                        <td>{r.ngayHet === null ? "—" : formatSo(r.ngayHet)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            </div>

            <p className="kvNote">
              Tốc độ chỉ đếm thửa nhập qua biểu web, chưa gồm dữ liệu từ Google Sheet. Phần còn lại còn giảm khi
              thửa lên Nhóm 1, 2, nên số ngày để hết chỉ là ước tính.
              {capNhat && ` Số liệu Nhóm 3 cập nhật lúc ${capNhat}.`}
            </p>
          </>
        )}
      </section>
    </main>
  );
}

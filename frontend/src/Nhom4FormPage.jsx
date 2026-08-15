import { useEffect, useMemo, useState } from "react";

import { getXaList, searchParcels } from "./services/parcelService";
import { checkTrungThua, submitHoSo } from "./services/nhom4Service";
import {
  HINH_THUC_SU_DUNG_OPTIONS,
  LOAI_CHU_OPTIONS,
  LOAI_DAT_OPTIONS,
  NGUON_GOC_OPTIONS,
  SO_NGUOI_MAC_DINH,
  taoChuRong,
  taoDatRong,
  taoThuaRong,
} from "./utils/nhom4Constants";

const LOAI_DAT_LAU_DAI = new Set(["ONT", "ODT"]);
const DATE_DDMMYYYY = /^\d{2}\/\d{2}\/\d{4}$/;
const NAM_ONLY = /^\d{4}$/;

// Chỉ gõ năm (VD "2050") thì tự hiểu là hết hạn ngày 31/12 năm đó.
function chuanHoaThoiHan(value) {
  const s = String(value ?? "").trim();
  return NAM_ONLY.test(s) ? `31/12/${s}` : s;
}

function parseSoVN(value) {
  const s = String(value ?? "").trim().replace(/\s/g, "");
  if (!s) return null;
  const normalized = s.includes(",") && s.includes(".") ? s.replace(/\./g, "").replace(",", ".") : s.replace(",", ".");
  const n = Number(normalized);
  return Number.isNaN(n) ? null : n;
}

export default function Nhom4FormPage({ onNavigateHome, prefill }) {
  const [xaList, setXaList] = useState([]);
  const [maXa, setMaXa] = useState("");
  const [doiTuong, setDoiTuong] = useState("Hộ gia đình, cá nhân");
  const [cheDo, setCheDo] = useState("Chưa được cấp GCN");
  const [gcn, setGcn] = useState({ soPhatHanh: "", ngayCap: "", soVaoSo: "" });

  const [loaiChu, setLoaiChu] = useState("Cá nhân");
  const [owners, setOwners] = useState([taoChuRong()]);
  const [toChuc, setToChuc] = useState({
    tenToChuc: "",
    maDinhDanhToChuc: "",
    hoTenDaiDien: "",
    ngaySinhDaiDien: "",
    gioiTinhDaiDien: "",
    maDinhDanhCaNhanDaiDien: "",
    diaChiThuongTruDaiDien: "",
  });

  const [thua, setThua] = useState(taoThuaRong());
  const [dat1, setDat1] = useState(taoDatRong());
  const [coDat2, setCoDat2] = useState(false);
  const [dat2, setDat2] = useState(taoDatRong());
  const [thuaList, setThuaList] = useState([]);
  const [trungThuaStatus, setTrungThuaStatus] = useState("");

  const [fileChinh, setFileChinh] = useState(null);
  const [filePhu, setFilePhu] = useState(null);
  const [token, setToken] = useState("");
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getXaList()
      .then((body) => setXaList(body?.items || []))
      .catch(() => setXaList([]));
  }, []);

  useEffect(() => {
    const soNguoi = SO_NGUOI_MAC_DINH[loaiChu] || 1;
    setOwners(Array.from({ length: soNguoi }, taoChuRong));
  }, [loaiChu]);

  // Nhận dữ liệu thửa từ bản đồ khi bấm "Nhập dữ liệu (biểu Nhóm 4)" ở
  // ParcelInfoPanel — điền sẵn xã/số tờ/số thửa/diện tích/địa chỉ, rồi kiểm
  // tra trùng thửa ngay (parcel từ bản đồ đã có sẵn dữ liệu, không cần gọi
  // lại /api/parcels/search như khi người dùng tự gõ số tờ/thửa).
  useEffect(() => {
    if (!prefill) return;

    const maXaValue = String(prefill.ma_xa ?? "");
    const soTo = String(prefill.so_to ?? "");
    const soThua = String(prefill.so_thua ?? "");

    setMaXa(maXaValue);
    setThua((prev) => ({
      ...prev,
      soTo,
      soThua,
      dienTichThuaDat: prefill.dien_tich != null ? String(prefill.dien_tich) : prev.dienTichThuaDat,
      diaChiThuaDat: prefill.dia_chi || prev.diaChiThuaDat,
    }));

    if (prefill.ten_chu) {
      setOwners((prev) => {
        const next = prev.length ? [...prev] : [taoChuRong()];
        next[0] = { ...next[0], hoTen: next[0].hoTen || prefill.ten_chu };
        return next;
      });
    }

    if (maXaValue && soTo && soThua) {
      setTrungThuaStatus("checking");
      checkTrungThua({ maXa: maXaValue, soTo, soThua })
        .then((trung) => setTrungThuaStatus(trung?.trung ? "trung" : "ok"))
        .catch(() => setTrungThuaStatus(""));
    }
  }, [prefill]);

  const dat2DienTichTinh = useMemo(() => {
    if (!coDat2) return "";
    const tong = parseSoVN(thua.dienTichThuaDat);
    const dt1 = parseSoVN(dat1.dienTich);
    if (tong === null || dt1 === null) return "";
    return String(Math.max(tong - dt1, 0));
  }, [coDat2, thua.dienTichThuaDat, dat1.dienTich]);

  const handleBlurSoToThua = async () => {
    if (!maXa || !thua.soTo || !thua.soThua) return;

    setTrungThuaStatus("checking");
    try {
      const trung = await checkTrungThua({ maXa, soTo: thua.soTo, soThua: thua.soThua });
      setTrungThuaStatus(trung?.trung ? "trung" : "ok");
    } catch {
      setTrungThuaStatus("");
    }

    try {
      // /api/parcels/search chưa trả ma_thua_dat trong properties (RPC hiện
      // tại chỉ có ma_xa/so_to/so_thua/muc_dich_su_dung/dien_tich/ten_chu/
      // dia_chi) — chỉ auto-fill diện tích/địa chỉ, mã định danh nhập tay.
      const found = await searchParcels({ ma_xa: maXa, so_to: thua.soTo, so_thua: thua.soThua });
      const feature = found?.features?.[0];
      if (feature) {
        const props = feature.properties || {};
        setThua((prev) => ({
          ...prev,
          dienTichThuaDat: prev.dienTichThuaDat || (props.dien_tich ? String(props.dien_tich) : prev.dienTichThuaDat),
          diaChiThuaDat: prev.diaChiThuaDat || props.dia_chi || prev.diaChiThuaDat,
        }));
      }
    } catch {
      // Không auto-fill được thì người dùng tự nhập tay — không chặn luồng nhập.
    }
  };

  // ONT/ODT (đất ở) mặc định thời hạn sử dụng "Lâu dài" và không cho sửa;
  // loại đất khác bắt buộc nhập ngày hết hạn dạng dd/mm/yyyy — nếu vừa đổi
  // từ ONT/ODT sang loại khác thì xóa "Lâu dài" cũ để buộc nhập lại ngày.
  const chonLoaiDat1 = (loaiDat) => {
    setDat1((prev) => ({
      ...prev,
      loaiDat,
      thoiHanSuDung: LOAI_DAT_LAU_DAI.has(loaiDat)
        ? "Lâu dài"
        : prev.thoiHanSuDung === "Lâu dài"
          ? ""
          : prev.thoiHanSuDung,
    }));
  };

  const chonLoaiDat2 = (loaiDat) => {
    setDat2((prev) => ({
      ...prev,
      loaiDat,
      thoiHanSuDung: LOAI_DAT_LAU_DAI.has(loaiDat)
        ? "Lâu dài"
        : prev.thoiHanSuDung === "Lâu dài"
          ? ""
          : prev.thoiHanSuDung,
    }));
  };

  const themThuaVaoDanhSach = () => {
    if (!thua.soTo || !thua.soThua || !thua.dienTichThuaDat || !dat1.loaiDat) {
      setError("Vui lòng nhập đủ số tờ, số thửa, diện tích và loại đất 1 trước khi thêm thửa.");
      return;
    }
    setError("");
    setThuaList((prev) => [...prev, { thua, dat1, dat2: coDat2 ? { ...dat2, dienTich: dat2DienTichTinh } : null }]);
    setThua(taoThuaRong());
    setDat1(taoDatRong());
    setDat2(taoDatRong());
    setCoDat2(false);
    setTrungThuaStatus("");
  };

  const xoaThua = (index) => setThuaList((prev) => prev.filter((_, i) => i !== index));
  const xoaDanhSachThua = () => setThuaList([]);

  const themNguoi = () => setOwners((prev) => [...prev, taoChuRong()]);
  const xoaNguoi = (index) => setOwners((prev) => prev.filter((_, i) => i !== index));
  const capNhatNguoi = (index, field, value) =>
    setOwners((prev) => prev.map((o, i) => (i === index ? { ...o, [field]: value } : o)));

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");

    const parcels =
      thuaList.length > 0
        ? thuaList
        : thua.soTo && thua.soThua
          ? [{ thua, dat1, dat2: coDat2 ? { ...dat2, dienTich: dat2DienTichTinh } : null }]
          : [];

    if (!maXa) return setError("Vui lòng chọn xã/phường.");
    if (!parcels.length) return setError("Chưa có thông tin thửa đất.");
    if (!fileChinh) {
      return setError(
        `Vui lòng chọn file PDF ${cheDo === "Đã có GCN" ? "Giấy chứng nhận" : "Đơn đăng ký"}.`,
      );
    }

    const payload = {
      ma_xa: maXa,
      doi_tuong: doiTuong,
      che_do: cheDo,
      gcn: {
        so_phat_hanh: gcn.soPhatHanh,
        ngay_cap: gcn.ngayCap,
        so_vao_so: gcn.soVaoSo,
      },
      owners: owners.map((o) => ({
        ho_ten: o.hoTen,
        ngay_sinh: o.ngaySinh,
        gioi_tinh: o.gioiTinh,
        cccd: o.cccd,
        dia_chi_thuong_tru: o.diaChiThuongTru,
        phap_nhan: o.phapNhan,
        vai_tro_phap_nhan: o.vaiTroPhapNhan,
      })),
      to_chuc: {
        ten_to_chuc: toChuc.tenToChuc,
        ma_dinh_danh_to_chuc: toChuc.maDinhDanhToChuc,
        ho_ten_dai_dien: toChuc.hoTenDaiDien,
        ngay_sinh_dai_dien: toChuc.ngaySinhDaiDien,
        gioi_tinh_dai_dien: toChuc.gioiTinhDaiDien,
        ma_dinh_danh_ca_nhan_dai_dien: toChuc.maDinhDanhCaNhanDaiDien,
        dia_chi_thuong_tru_dai_dien: toChuc.diaChiThuongTruDaiDien,
      },
      thua_list: parcels.map((p) => ({
        thua: {
          so_to: p.thua.soTo,
          so_thua: p.thua.soThua,
          so_to_gcn: p.thua.soToGCN,
          so_thua_gcn: p.thua.soThuaGCN,
          ma_dinh_danh: p.thua.maDinhDanh,
          dien_tich_thua_dat: p.thua.dienTichThuaDat,
          dia_chi_thua_dat: p.thua.diaChiThuaDat,
          ghi_chu: p.thua.ghiChu,
        },
        dat1: {
          loai_dat: p.dat1.loaiDat,
          dien_tich: p.dat1.dienTich,
          nguon_goc_su_dung: p.dat1.nguonGocSuDung,
          hinh_thuc_su_dung: p.dat1.hinhThucSuDung,
          thoi_han_su_dung: p.dat1.thoiHanSuDung,
        },
        dat2: p.dat2
          ? {
              loai_dat: p.dat2.loaiDat,
              dien_tich: p.dat2.dienTich,
              nguon_goc_su_dung: p.dat2.nguonGocSuDung,
              hinh_thuc_su_dung: p.dat2.hinhThucSuDung,
              thoi_han_su_dung: p.dat2.thoiHanSuDung,
            }
          : null,
      })),
    };

    setStatus("submitting");
    try {
      const body = await submitHoSo(payload, fileChinh, filePhu, token);
      setResult(body);
      setStatus("done");
      setThuaList([]);
      setThua(taoThuaRong());
      setDat1(taoDatRong());
      setDat2(taoDatRong());
      setCoDat2(false);
      setFileChinh(null);
      setFilePhu(null);
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
          <h1>Nhập biểu Nhóm 4</h1>
          <p>Nhập dữ liệu thu thập thửa đất, lưu vào Supabase, hồ sơ quét lên Google Drive</p>
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
        <form className="importCard nhom4Card" onSubmit={handleSubmit}>
          <h2 className="nhom4SectionTitle">Đơn vị hành chính</h2>
          <label htmlFor="nhom4Xa">Chọn xã/phường *</label>
          <select id="nhom4Xa" value={maXa} onChange={(e) => setMaXa(e.target.value)} required>
            <option value="">-- Chọn --</option>
            {xaList.map((x) => (
              <option key={x.ma_xa} value={x.ma_xa}>
                {x.ten_xa}
              </option>
            ))}
          </select>

          <h2 className="nhom4SectionTitle">Đối tượng sử dụng đất</h2>
          <div className="nhom4Tabs">
            {["Hộ gia đình, cá nhân", "Tổ chức"].map((v) => (
              <button
                type="button"
                key={v}
                className={"nhom4Tab" + (doiTuong === v ? " active" : "")}
                onClick={() => setDoiTuong(v)}
              >
                {v}
              </button>
            ))}
          </div>

          <h2 className="nhom4SectionTitle">Chế độ hồ sơ</h2>
          <div className="nhom4Tabs">
            {["Chưa được cấp GCN", "Đã có GCN"].map((v) => (
              <button
                type="button"
                key={v}
                className={"nhom4Tab" + (cheDo === v ? " active" : "")}
                onClick={() => setCheDo(v)}
              >
                {v}
              </button>
            ))}
          </div>

          {cheDo === "Đã có GCN" && (
            <>
              <h2 className="nhom4SectionTitle">Thông tin GCN</h2>
              <label htmlFor="soPhatHanh">Số phát hành GCN *</label>
              <input
                id="soPhatHanh"
                value={gcn.soPhatHanh}
                onChange={(e) => setGcn({ ...gcn, soPhatHanh: e.target.value })}
              />
              <label htmlFor="ngayCap">Ngày cấp GCN *</label>
              <input
                id="ngayCap"
                placeholder="dd/mm/yyyy"
                value={gcn.ngayCap}
                onChange={(e) => setGcn({ ...gcn, ngayCap: e.target.value })}
              />
              <label htmlFor="soVaoSo">Số vào sổ GCN *</label>
              <input
                id="soVaoSo"
                value={gcn.soVaoSo}
                onChange={(e) => setGcn({ ...gcn, soVaoSo: e.target.value })}
              />
            </>
          )}

          <h2 className="nhom4SectionTitle">Thông tin chủ sử dụng</h2>
          {doiTuong === "Hộ gia đình, cá nhân" ? (
            <>
              <div className="nhom4Tabs">
                {LOAI_CHU_OPTIONS.map((v) => (
                  <button
                    type="button"
                    key={v}
                    className={"nhom4Tab" + (loaiChu === v ? " active" : "")}
                    onClick={() => setLoaiChu(v)}
                  >
                    {v}
                  </button>
                ))}
              </div>

              {owners.map((owner, index) => (
                <div className="nhom4Subcard" key={index}>
                  <div className="nhom4OwnerHead">
                    <strong>Chủ sử dụng {index + 1}</strong>
                    {owners.length > 1 && (
                      <button type="button" className="nhom4MiniBtn danger" onClick={() => xoaNguoi(index)}>
                        Xóa
                      </button>
                    )}
                  </div>
                  <div className="nhom4Grid2">
                    <div>
                      <label>Họ và tên *</label>
                      <input value={owner.hoTen} onChange={(e) => capNhatNguoi(index, "hoTen", e.target.value)} />
                    </div>
                    <div>
                      <label>Ngày sinh *</label>
                      <input
                        placeholder="yyyy hoặc dd/mm/yyyy"
                        value={owner.ngaySinh}
                        onChange={(e) => capNhatNguoi(index, "ngaySinh", e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="nhom4Grid2">
                    <div>
                      <label>Giới tính *</label>
                      <select value={owner.gioiTinh} onChange={(e) => capNhatNguoi(index, "gioiTinh", e.target.value)}>
                        <option value="">-- Chọn --</option>
                        <option>Nam</option>
                        <option>Nữ</option>
                      </select>
                    </div>
                    <div>
                      <label>Số CCCD *</label>
                      <input
                        maxLength={12}
                        value={owner.cccd}
                        onChange={(e) => capNhatNguoi(index, "cccd", e.target.value)}
                      />
                    </div>
                  </div>
                  <label>Địa chỉ thường trú *</label>
                  <input
                    value={owner.diaChiThuongTru}
                    onChange={(e) => capNhatNguoi(index, "diaChiThuongTru", e.target.value)}
                  />
                  <div className="nhom4Grid2">
                    <div>
                      <label>Pháp nhân</label>
                      <input value={owner.phapNhan} onChange={(e) => capNhatNguoi(index, "phapNhan", e.target.value)} />
                    </div>
                    <div>
                      <label>Vai trò pháp nhân</label>
                      <input
                        value={owner.vaiTroPhapNhan}
                        onChange={(e) => capNhatNguoi(index, "vaiTroPhapNhan", e.target.value)}
                      />
                    </div>
                  </div>
                </div>
              ))}
              <button type="button" className="nhom4SecondaryBtn" onClick={themNguoi}>
                + Thêm người
              </button>
            </>
          ) : (
            <div className="nhom4Subcard">
              <div className="nhom4Grid2">
                <div>
                  <label>Tên tổ chức *</label>
                  <input value={toChuc.tenToChuc} onChange={(e) => setToChuc({ ...toChuc, tenToChuc: e.target.value })} />
                </div>
                <div>
                  <label>Mã định danh tổ chức</label>
                  <input
                    value={toChuc.maDinhDanhToChuc}
                    onChange={(e) => setToChuc({ ...toChuc, maDinhDanhToChuc: e.target.value })}
                  />
                </div>
              </div>
              <div className="nhom4Grid2">
                <div>
                  <label>Họ tên người đại diện</label>
                  <input
                    value={toChuc.hoTenDaiDien}
                    onChange={(e) => setToChuc({ ...toChuc, hoTenDaiDien: e.target.value })}
                  />
                </div>
                <div>
                  <label>Ngày sinh người đại diện</label>
                  <input
                    value={toChuc.ngaySinhDaiDien}
                    onChange={(e) => setToChuc({ ...toChuc, ngaySinhDaiDien: e.target.value })}
                  />
                </div>
              </div>
              <div className="nhom4Grid2">
                <div>
                  <label>Giới tính</label>
                  <select
                    value={toChuc.gioiTinhDaiDien}
                    onChange={(e) => setToChuc({ ...toChuc, gioiTinhDaiDien: e.target.value })}
                  >
                    <option value="">-- Chọn --</option>
                    <option>Nam</option>
                    <option>Nữ</option>
                  </select>
                </div>
                <div>
                  <label>Mã định danh cá nhân</label>
                  <input
                    maxLength={12}
                    value={toChuc.maDinhDanhCaNhanDaiDien}
                    onChange={(e) => setToChuc({ ...toChuc, maDinhDanhCaNhanDaiDien: e.target.value })}
                  />
                </div>
              </div>
              <label>Địa chỉ thường trú</label>
              <input
                value={toChuc.diaChiThuongTruDaiDien}
                onChange={(e) => setToChuc({ ...toChuc, diaChiThuongTruDaiDien: e.target.value })}
              />
            </div>
          )}

          <h2 className="nhom4SectionTitle">Thông tin thửa đất</h2>
          <div className="nhom4Grid2">
            <div>
              <label>Số hiệu tờ bản đồ *</label>
              <input
                value={thua.soTo}
                onChange={(e) => setThua({ ...thua, soTo: e.target.value })}
                onBlur={handleBlurSoToThua}
              />
            </div>
            <div>
              <label>Số thứ tự thửa *</label>
              <input
                value={thua.soThua}
                onChange={(e) => setThua({ ...thua, soThua: e.target.value })}
                onBlur={handleBlurSoToThua}
              />
            </div>
          </div>
          {trungThuaStatus === "checking" && <div className="notice">Đang kiểm tra trùng thửa…</div>}
          {trungThuaStatus === "trung" && <div className="notice error">Thửa này đã được nhập rồi.</div>}
          {trungThuaStatus === "ok" && <div className="notice">Thửa này chưa có trong dữ liệu đã nhập.</div>}

          {cheDo === "Đã có GCN" && (
            <div className="nhom4Grid2">
              <div>
                <label>Số tờ ghi trên GCN</label>
                <input value={thua.soToGCN} onChange={(e) => setThua({ ...thua, soToGCN: e.target.value })} />
              </div>
              <div>
                <label>Số thửa ghi trên GCN</label>
                <input value={thua.soThuaGCN} onChange={(e) => setThua({ ...thua, soThuaGCN: e.target.value })} />
              </div>
            </div>
          )}

          <div className="nhom4Grid2">
            <div>
              <label>Mã định danh thửa đất</label>
              <input readOnly value={thua.maDinhDanh} />
            </div>
            <div>
              <label>Diện tích thửa đất *</label>
              <input value={thua.dienTichThuaDat} onChange={(e) => setThua({ ...thua, dienTichThuaDat: e.target.value })} />
            </div>
          </div>
          <label>Địa chỉ thửa đất</label>
          <input value={thua.diaChiThuaDat} onChange={(e) => setThua({ ...thua, diaChiThuaDat: e.target.value })} />

          <div className="nhom4Subcard">
            <strong>Loại đất 1</strong>
            <div className="nhom4Grid2">
              <div>
                <label>Loại đất *</label>
                <select value={dat1.loaiDat} onChange={(e) => chonLoaiDat1(e.target.value)}>
                  <option value="">-- Chọn --</option>
                  {LOAI_DAT_OPTIONS.map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </div>
              <div>
                <label>Diện tích loại đất 1 *</label>
                <input
                  value={coDat2 ? dat1.dienTich : thua.dienTichThuaDat}
                  onChange={(e) => setDat1({ ...dat1, dienTich: e.target.value })}
                  readOnly={!coDat2}
                />
              </div>
            </div>
            <div className="nhom4Grid2">
              <div>
                <label>Nguồn gốc sử dụng</label>
                <select
                  value={dat1.nguonGocSuDung}
                  onChange={(e) => setDat1({ ...dat1, nguonGocSuDung: e.target.value })}
                >
                  <option value="">-- Chọn --</option>
                  {NGUON_GOC_OPTIONS.map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </div>
              <div>
                <label>Hình thức sử dụng</label>
                <select
                  value={dat1.hinhThucSuDung}
                  onChange={(e) => setDat1({ ...dat1, hinhThucSuDung: e.target.value })}
                >
                  <option value="">-- Chọn --</option>
                  {HINH_THUC_SU_DUNG_OPTIONS.map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </div>
            </div>
            <label>Thời hạn sử dụng *</label>
            <input
              value={dat1.thoiHanSuDung}
              placeholder={LOAI_DAT_LAU_DAI.has(dat1.loaiDat) ? "" : "dd/mm/yyyy"}
              readOnly={LOAI_DAT_LAU_DAI.has(dat1.loaiDat)}
              onChange={(e) => setDat1({ ...dat1, thoiHanSuDung: e.target.value })}
              onBlur={() => setDat1((prev) => ({ ...prev, thoiHanSuDung: chuanHoaThoiHan(prev.thoiHanSuDung) }))}
            />
            {!LOAI_DAT_LAU_DAI.has(dat1.loaiDat) && dat1.thoiHanSuDung && !DATE_DDMMYYYY.test(dat1.thoiHanSuDung) && (
              <p className="nhom4FieldError">Nhập ngày hết hạn theo định dạng dd/mm/yyyy.</p>
            )}
          </div>

          <label className="nhom4Check">
            <input type="checkbox" checked={coDat2} onChange={(e) => setCoDat2(e.target.checked)} />
            Có loại đất 2
          </label>

          {coDat2 && (
            <div className="nhom4Subcard">
              <strong>Loại đất 2</strong>
              <div className="nhom4Grid2">
                <div>
                  <label>Loại đất 2 *</label>
                  <select value={dat2.loaiDat} onChange={(e) => chonLoaiDat2(e.target.value)}>
                    <option value="">-- Chọn --</option>
                    {LOAI_DAT_OPTIONS.map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label>Diện tích loại đất 2</label>
                  <input readOnly value={dat2DienTichTinh} />
                </div>
              </div>
              <div className="nhom4Grid2">
                <div>
                  <label>Nguồn gốc sử dụng 2</label>
                  <select
                    value={dat2.nguonGocSuDung}
                    onChange={(e) => setDat2({ ...dat2, nguonGocSuDung: e.target.value })}
                  >
                    <option value="">-- Chọn --</option>
                    {NGUON_GOC_OPTIONS.map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label>Hình thức sử dụng 2</label>
                  <select
                    value={dat2.hinhThucSuDung}
                    onChange={(e) => setDat2({ ...dat2, hinhThucSuDung: e.target.value })}
                  >
                    <option value="">-- Chọn --</option>
                    {HINH_THUC_SU_DUNG_OPTIONS.map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </div>
              </div>
              <label>Thời hạn sử dụng 2 *</label>
              <input
                value={dat2.thoiHanSuDung}
                placeholder={LOAI_DAT_LAU_DAI.has(dat2.loaiDat) ? "" : "dd/mm/yyyy"}
                readOnly={LOAI_DAT_LAU_DAI.has(dat2.loaiDat)}
                onChange={(e) => setDat2({ ...dat2, thoiHanSuDung: e.target.value })}
                onBlur={() => setDat2((prev) => ({ ...prev, thoiHanSuDung: chuanHoaThoiHan(prev.thoiHanSuDung) }))}
              />
              {!LOAI_DAT_LAU_DAI.has(dat2.loaiDat) && dat2.thoiHanSuDung && !DATE_DDMMYYYY.test(dat2.thoiHanSuDung) && (
                <p className="nhom4FieldError">Nhập ngày hết hạn theo định dạng dd/mm/yyyy.</p>
              )}
            </div>
          )}

          <label>Ghi chú</label>
          <textarea
            rows={2}
            value={thua.ghiChu}
            onChange={(e) => setThua({ ...thua, ghiChu: e.target.value })}
          />

          <div className="nhom4Subcard">
            <div className="nhom4OwnerHead">
              <strong>Danh sách thửa đất nhập kèm ({thuaList.length})</strong>
              <div style={{ display: "flex", gap: 8 }}>
                <button type="button" className="nhom4MiniBtn" onClick={themThuaVaoDanhSach}>
                  + Thêm thửa đất
                </button>
                {thuaList.length > 0 && (
                  <button type="button" className="nhom4MiniBtn danger" onClick={xoaDanhSachThua}>
                    Xóa toàn bộ
                  </button>
                )}
              </div>
            </div>
            {thuaList.length === 0 ? (
              <p className="importHint">Chưa có thửa nào trong danh sách. Nếu chỉ nhập 1 thửa, có thể lưu trực tiếp.</p>
            ) : (
              <ul className="nhom4ParcelList">
                {thuaList.map((p, index) => (
                  <li key={index}>
                    <span>
                      Tờ {p.thua.soTo} / Thửa {p.thua.soThua} — {p.thua.dienTichThuaDat} m²
                    </span>
                    <button type="button" className="nhom4MiniBtn danger" onClick={() => xoaThua(index)}>
                      Xóa
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <h2 className="nhom4SectionTitle">Hồ sơ quét</h2>
          <label>{cheDo === "Đã có GCN" ? "File PDF Giấy chứng nhận *" : "File PDF Đơn đăng ký *"}</label>
          <input type="file" accept="application/pdf" onChange={(e) => setFileChinh(e.target.files?.[0] || null)} />
          <label>File PDF Giấy tờ (tùy chọn)</label>
          <input type="file" accept="application/pdf" onChange={(e) => setFilePhu(e.target.files?.[0] || null)} />

          <label htmlFor="nhom4Token">Mã xác thực</label>
          <input
            id="nhom4Token"
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Nhập mã do quản trị viên cấp (nếu có)"
          />

          <button type="submit" className="importButton" disabled={status === "submitting"}>
            {status === "submitting" ? "Đang lưu…" : "Lưu hồ sơ"}
          </button>

          {status === "done" && result && (
            <div className="notice">
              <strong>Hoàn tất</strong>
              <span>{result.message}</span>
            </div>
          )}
          {(status === "error" || error) && (
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

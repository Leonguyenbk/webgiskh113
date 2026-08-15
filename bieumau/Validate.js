/**
 * Validate + row builder
 */

function validatePayload_(payload) {
  var cheDo = payload.cheDo || "";
  var hsq = payload.hsq || {};
  var parcels = getParcelsFromPayload_(payload);
  if (!parcels.length) throw new Error("Chưa có thông tin thửa đất.");

  var owners = filterOwners_(payload.chuSuDung || []);
  var doiTuong = payload.doiTuong || "Hộ gia đình, cá nhân";
  var toChuc = payload.toChuc || {};
  if (doiTuong === "Tổ chức") {
    if (!toChuc.tenToChuc) throw new Error("Vui lòng nhập Tên tổ chức.");
    if (toChuc.maDinhDanhCaNhanDaiDien && !/^\d{12}$/.test(String(toChuc.maDinhDanhCaNhanDaiDien))) {
      throw new Error("Mã định danh cá nhân phải đủ 12 số.");
    }
  } else {
    if (!owners.length) throw new Error("Chưa có thông tin chủ sử dụng.");
  }

  if (cheDo === "Đã có GCN") {
    if (!payload.gcn || !payload.gcn.soPhatHanh || !payload.gcn.ngayCap || !payload.gcn.soVaoSo) {
      throw new Error("Vui lòng nhập đủ thông tin GCN.");
    }
    if (!validateSoPhatHanhGCN_(payload.gcn.soPhatHanh)) {
      throw new Error("nhập không đúng!");
    }
    if (!hsq.giayChungNhan) throw new Error("Giấy chứng nhận là bắt buộc.");
  } else {
    if (!hsq.donDangKy) throw new Error("Đơn đăng ký là bắt buộc.");
  }

  var cccd = {};
  for (var i = 0; i < owners.length; i++) {
    var o = owners[i];
    if (doiTuong === "Tổ chức") {
      if (o.cccd && !/^\d{12}$/.test(String(o.cccd))) throw new Error("Mã định danh cá nhân phải đủ 12 số.");
      continue;
    }

    if (!o.hoTen || !o.ngaySinh || !o.gioiTinh || !o.cccd || !o.diaChiThuongTru) {
      throw new Error("Vui lòng nhập đủ thông tin chủ sử dụng thứ " + (i + 1) + ".");
    }
    if (!/^\d{12}$/.test(String(o.cccd))) throw new Error("Số CCCD người thứ " + (i + 1) + " phải đủ 12 số.");
    if (cccd[o.cccd]) throw new Error("Số CCCD người thứ " + (i + 1) + " bị trùng trong hồ sơ.");
    cccd[o.cccd] = true;
  }

  for (var p = 0; p < parcels.length; p++) {
    var parcel = parcels[p];
    var thua = parcel.thuaDat || parcel;
    var dat1 = parcel.dat1 || payload.dat1 || {};
    var dat2 = parcel.dat2 || payload.dat2 || {};

    if (!thua.soTo || !thua.soThua) throw new Error("Vui lòng nhập số tờ và số thửa cho thửa thứ " + (p + 1) + ".");
    if (!thua.dienTichTong) throw new Error("Vui lòng nhập diện tích thửa đất cho thửa thứ " + (p + 1) + ".");

    if (!dat1.loaiDat || !dat1.dienTich || !dat1.nguonGocSuDung || !dat1.hinhThucSuDung || !dat1.thoiHanSuDung) {
      throw new Error("Vui lòng nhập đủ thông tin loại đất 1 cho thửa thứ " + (p + 1) + ".");
    }

    var hasDat2 = !!(dat2.loaiDat2 || dat2.dienTich2 || dat2.nguonGocSuDung2 || dat2.hinhThucSuDung2 || dat2.thoiHanSuDung2);
    if (hasDat2) {
      if (!dat2.loaiDat2 || !dat2.dienTich2 || !dat2.nguonGocSuDung2 || !dat2.hinhThucSuDung2 || !dat2.thoiHanSuDung2) {
        throw new Error("Vui lòng nhập đủ thông tin loại đất 2 cho thửa thứ " + (p + 1) + ".");
      }
      var tong = parseNumberVN_(thua.dienTichTong);
      var dt1 = parseNumberVN_(dat1.dienTich);
      var dt2 = parseNumberVN_(dat2.dienTich2);
      if (isNaN(tong) || isNaN(dt1) || isNaN(dt2)) throw new Error("Diện tích phải là số ở thửa thứ " + (p + 1) + ".");
      if (Math.abs((dt1 + dt2) - tong) > 0.0001) {
        throw new Error("Diện tích loại đất 1 + loại đất 2 phải bằng diện tích thửa đất ở thửa thứ " + (p + 1) + ".");
      }
    }
  }

  validateRequiredFiles_(payload);
}

function validateRequiredFiles_(payload) {
  var files = payload.files || [];
  function has(kind) {
    for (var i = 0; i < files.length; i++) if (files[i].kind === kind && files[i].base64) return true;
    return false;
  }

  if (payload.cheDo === "Chưa được cấp GCN") {
    if (payload.hsq.donDangKy && !has("DDK")) throw new Error("Vui lòng chọn file PDF Đơn đăng ký.");
    if (payload.hsq.giayTo && !has("GT_CHUA_CO")) throw new Error("Vui lòng chọn file PDF Giấy tờ.");
  } else {
    if (payload.hsq.giayChungNhan && !has("GCN")) throw new Error("Vui lòng chọn file PDF Giấy chứng nhận.");
    if (payload.hsq.giayTo && !has("GT_DA_CO")) throw new Error("Vui lòng chọn file PDF Giấy tờ.");
  }
}

function filterOwners_(owners) {
  var out = [];
  for (var i = 0; i < owners.length; i++) {
    var o = owners[i] || {};
    if (o.optional && !(o.hoTen || o.ngaySinh || o.gioiTinh || o.cccd || o.diaChiThuongTru)) continue;
    out.push(o);
  }
  return out;
}

function buildRow_(payload, owner, stt, firstOfParcel) {
  var row = Array(COL_NHOM).fill("");
  var maXa = String(payload.maXa || DEFAULT_MA_XA);
  var cheDo = payload.cheDo || "";
  var gcn = payload.gcn || {};
  var thua = payload.thuaDat || {};
  var dat1 = payload.dat1 || {};
  var dat2 = payload.dat2 || {};

  row[0] = stt;
  row[1] = maXa;
  row[2] = cheDo === "Chưa được cấp GCN" ? makeDefaultSoPhatHanh_(payload) : String(gcn.soPhatHanh || "");
  row[3] = cheDo === "Đã có GCN" ? (gcn.ngayCap || "") : "";
  row[4] = cheDo === "Đã có GCN" ? (gcn.soVaoSo || "") : "";
  if ((payload.doiTuong || "") === "Tổ chức") {
    var tc = payload.toChuc || {};
    row[5] = tc.tenToChuc || "";                              // F: Tên tổ chức
    row[6] = String(tc.maDinhDanhToChuc || "");                // G: Mã định danh tổ chức
    row[7] = tc.hoTenDaiDien || owner.hoTen || "";             // H
    row[8] = tc.ngaySinhDaiDien || owner.ngaySinh || "";       // I
    row[9] = tc.gioiTinhDaiDien || owner.gioiTinh || "";       // J
    row[10] = String(tc.maDinhDanhCaNhanDaiDien || owner.cccd || ""); // K
    row[11] = tc.diaChiThuongTruDaiDien || owner.diaChiThuongTru || ""; // L
    row[12] = "Tổ chức";                                       // M
    row[13] = "";                                              // N
  } else {
    row[5] = "";
    row[6] = "";

    row[7] = owner.hoTen || "";
    row[8] = owner.ngaySinh || "";
    row[9] = owner.gioiTinh || "";
    row[10] = String(owner.cccd || "");
    row[11] = owner.diaChiThuongTru || "";
    row[12] = owner.phapNhan || "";
    row[13] = owner.vaiTroPhapNhan || "";
  }

  row[18] = String(thua.maDinhDanh || "");
  row[19] = cheDo === "Đã có GCN" ? String(gcn.soToGCN || "") : "";
  row[20] = cheDo === "Đã có GCN" ? String(gcn.soThuaGCN || "") : "";
  row[21] = String(thua.soTo || "");
  row[22] = String(thua.soThua || "");
  row[23] = thua.diaChiThua || getDiaChiXa_(maXa);
  row[24] = thua.dienTichTong || "";

  row[25] = dat1.loaiDat || "";
  row[26] = dat1.dienTich || "";
  row[27] = dat1.nguonGocSuDung || "";
  row[28] = dat1.hinhThucSuDung || "";
  row[29] = dat1.thoiHanSuDung || "";

  row[30] = dat2.loaiDat2 || "";
  row[31] = dat2.dienTich2 || "";
  row[32] = dat2.nguonGocSuDung2 || "";
  row[33] = dat2.hinhThucSuDung2 || "";
  row[34] = dat2.thoiHanSuDung2 || "";

  var names = makeTenFileHsq_(payload);
  var links = ""; // V39: không ghi link Drive vào Excel

  row[49] = names;         // AX tên file HSQ
  row[54] = "";            // BC bỏ trống
  row[55] = "";            // BD bỏ trống, không ghi link Drive
  row[56] = firstOfParcel ? DEFAULT_NHOM : "";

  return row;
}

function makeDefaultSoPhatHanh_(payload) {
  var thua = payload.thuaDat || {};
  return "CHUACOGIAY_" + (payload.maXa || DEFAULT_MA_XA) + "_" + thua.soTo + "_" + thua.soThua;
}


function makeTenFileHsq_(payload) {
  var cheDo = payload.cheDo || "";
  var hsq = payload.hsq || {};
  var gcn = payload.gcn || {};
  var thua = payload.thuaDat || {};
  var maXa = payload.maXa || DEFAULT_MA_XA;
  var names = [];

  if (cheDo === "Chưa được cấp GCN") {
    var base = "CHUACOGIAY_" + maXa + "_" + (thua.soTo || "") + "_" + (thua.soThua || "");
    if (hsq.donDangKy) names.push(base + "-DDK.pdf");
    if (hsq.giayTo) names.push(base + "-GT.pdf");
  } else {
    var sph = String(gcn.soPhatHanh || "").trim();
    if (hsq.giayChungNhan) names.push(sph + "-GCN.pdf");
    if (hsq.giayTo) names.push(sph + "-GT.pdf");
  }

  return names.join(", ");
}

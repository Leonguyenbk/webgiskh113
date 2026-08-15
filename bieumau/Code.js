/**
 * Code.gs - Entry points
 */

function doGet() {
  return HtmlService.createTemplateFromFile("Index")
    .evaluate()
    .setTitle("Biểu mẫu nhập Nhóm 4")
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}

function getBootstrap() {
  var danhSach = getDanhSachXaForClient_();
  return {
    version: APP_VERSION,
    defaultMaXa: DEFAULT_MA_XA,
    danhSachXa: danhSach,
    isAdmin: isAdmin_()
  };
}

function xoaCacheCauHinhXa() {
  CacheService.getScriptCache().remove("DANH_SACH_XA_CONFIG");
  return "Đã xóa cache cấu hình xã. Mở lại Web App để tải cấu hình mới.";
}

/**
 * Lưu hồ sơ và upload PDF theo từng loại.
 * payload gồm dữ liệu form và files: [{kind,label,targetName,mimeType,base64}]
 */

function saveHoSoWithFiles(payload) {
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(30000);

    if (!payload) throw new Error("Không nhận được dữ liệu.");
    var maXa = String(payload.maXa || DEFAULT_MA_XA).trim();
    var cfg = getXaConfig(maXa);
    if (!cfg.spreadsheetId) throw new Error("Chưa cấu hình Google Sheet cho mã xã " + maXa + ".");

    var sh = openSheet_(maXa, SHEET_NHAP);
    ensureSupportSheets_(maXa);

    var parcels = getParcelsFromPayload_(payload);
    if (!parcels.length) throw new Error("Chưa có thông tin thửa đất.");

    // Kiểm tra trùng toàn bộ trước khi upload/ghi dữ liệu
    var seenKeys = {};
    for (var p = 0; p < parcels.length; p++) {
      var thuaCheck = getThuaFromParcel_(parcels[p]);
      var soToCheck = thuaCheck.soTo;
      var soThuaCheck = thuaCheck.soThua;

      if (!soToCheck || !soThuaCheck) {
        throw new Error("Thửa thứ " + (p + 1) + " chưa có số tờ hoặc số thửa.");
      }

      var keyCheck = makeThuaKey_(maXa, soToCheck, soThuaCheck);
      if (seenKeys[keyCheck]) throw new Error("Danh sách thửa nhập bị trùng: " + soToCheck + "_" + soThuaCheck);
      seenKeys[keyCheck] = true;

      if (indexHasKey_(maXa, keyCheck)) throw new Error("Thửa này đã được nhập rồi: " + soToCheck + "_" + soThuaCheck);

      var trung = kiemTraTrungThuaTrongTrangTinh1(soToCheck, soThuaCheck, maXa);
      if (trung.trung) throw new Error("Thửa này đã được nhập rồi: " + soToCheck + "_" + soThuaCheck);
    }

    validatePayload_(payload);

    // Upload PDF bảo mật. Không ghi link Drive vào Excel.
    var uploadResult = uploadFilesSecure_(payload, cfg.folderId);
    if (!uploadResult.ok) throw new Error(uploadResult.message);
    payload.uploadedFiles = uploadResult.files;

    var owners = filterOwners_(payload.chuSuDung || []);
    payload.chuSuDung = owners;

    var nextRow = getNextAppendRow_(sh);
    var startStt = getMaxStt_(sh) + 1;
    var rows = [];
    var indexRows = [];

    for (var t = 0; t < parcels.length; t++) {
      var parcelPayload = clonePayloadForParcel_(payload, parcels[t]);
      var firstRowForParcel = nextRow + rows.length;
      for (var i = 0; i < owners.length; i++) {
        rows.push(buildRow_(parcelPayload, owners[i], startStt + rows.length, i === 0));
      }
      var thuaForIndex = getThuaFromParcel_(parcels[t]);
      var key = makeThuaKey_(maXa, thuaForIndex.soTo, thuaForIndex.soThua);
      indexRows.push({key:key, startRow:firstRowForParcel, count:owners.length});
    }

    formatTextColumns_(sh, nextRow, rows.length);
    sh.getRange(nextRow, 1, rows.length, COL_NHOM).setValues(rows);

    for (var ix = 0; ix < indexRows.length; ix++) {
      addIndexKey_(maXa, indexRows[ix].key, indexRows[ix].startRow, indexRows[ix].count);
      addLog_(maXa, "CREATE", indexRows[ix].key, "Lưu " + indexRows[ix].count + " dòng; upload " + uploadResult.files.length + " file.");
    }

    return {
      ok: true,
      message: "Đã lưu thành công " + parcels.length + " thửa, tổng " + rows.length + " dòng liền nhau.",
      uploadedFiles: uploadResult.files.map(function(f) {
        return {label: f.label, name: f.name};
      })
    };
  } catch (err) {
    return {ok: false, message: err.message || String(err)};
  } finally {
    try { lock.releaseLock(); } catch (e) {}
  }
}

function getParcelsFromPayload_(payload) {
  if (payload.thuaList && payload.thuaList.length) return payload.thuaList;
  if (payload.thuaDat && payload.thuaDat.soTo && payload.thuaDat.soThua) {
    return [{
      thuaDat: payload.thuaDat,
      dat1: payload.dat1 || {},
      dat2: payload.dat2 || {},
      gcnThua: {
        soToGCN: payload.gcn ? payload.gcn.soToGCN : "",
        soThuaGCN: payload.gcn ? payload.gcn.soThuaGCN : ""
      }
    }];
  }
  return [];
}

function getThuaFromParcel_(parcel) {
  return (parcel && parcel.thuaDat) ? parcel.thuaDat : (parcel || {});
}

function clonePayloadForParcel_(payload, parcel) {
  var copy = JSON.parse(JSON.stringify(payload));
  copy.thuaDat = parcel.thuaDat || parcel;
  copy.dat1 = parcel.dat1 || payload.dat1 || {};
  copy.dat2 = parcel.dat2 || payload.dat2 || {};

  // Với trường hợp Đã có GCN, mỗi thửa có thể có số tờ/số thửa ghi trên GCN riêng
  copy.gcn = copy.gcn || {};
  if (parcel.gcnThua) {
    copy.gcn.soToGCN = parcel.gcnThua.soToGCN || "";
    copy.gcn.soThuaGCN = parcel.gcnThua.soThuaGCN || "";
  }
  return copy;
}


function kiemTraTrungNhanh(soTo, soThua, maXa) {
  try {
    soTo = String(soTo || "").trim();
    soThua = String(soThua || "").trim();
    maXa = String(maXa || DEFAULT_MA_XA).trim();

    if (!soTo || !soThua) {
      return {ok: true, trung: false, message: ""};
    }

    var result = kiemTraTrungThuaTrongTrangTinh1(soTo, soThua, maXa);
    if (result.trung) {
      return {ok: true, trung: true, message: "Thửa này đã được nhập rồi"};
    }

    return {ok: true, trung: false, message: "Thửa này chưa có trong dữ liệu đã nhập."};
  } catch (err) {
    return {ok: false, trung: false, message: err.message || String(err)};
  }
}

function kiemTraThuaDat(soTo, soThua, maXa) {
  soTo = normKeyPart_(soTo);
  soThua = normKeyPart_(soThua);
  maXa = String(maXa || DEFAULT_MA_XA).trim();

  if (!soTo || !soThua) {
    return { ok: false, message: "Vui lòng nhập số tờ và số thửa." };
  }

  var dup = kiemTraTrungThuaTrongTrangTinh1(soTo, soThua, maXa);
  if (dup.trung) {
    return { ok: false, duplicate: true, message: "Thửa này đã được nhập rồi" };
  }

  var map = getMapThuaCanThuThapCached_(maXa);
  var key = soTo + "_" + soThua;

  if (map[key]) {
    return {
      ok: true,
      message: "Tìm thấy thửa đất.",
      data: {
        maDinhDanh: map[key].maDinhDanh || "",
        dienTich: map[key].dienTich || "",
        diaChiThua: getDiaChiXa_(maXa)
      }
    };
  }

  return {
    ok: false,
    message: "Số tờ/số thửa này không nằm trong danh sách cần thu thập."
  };
}

function kiemTraTrungThuaTrongTrangTinh1(soTo, soThua, maXa) {
  var key = makeThuaKey_(maXa, soTo, soThua);
  if (indexHasKey_(maXa, key)) return {ok:true, trung:true, message:"Thửa này đã được nhập rồi"};

  soTo = normKeyPart_(soTo);
  soThua = normKeyPart_(soThua);
  var sh = openSheet_(maXa, SHEET_NHAP);
  var lastRow = sh.getLastRow();
  if (lastRow < 2) return {ok:true, trung:false};

  var values = sh.getRange(2, COL_SO_TO, lastRow - 1, 2).getDisplayValues();
  for (var i = 0; i < values.length; i++) {
    if (normKeyPart_(values[i][0]) === soTo && normKeyPart_(values[i][1]) === soThua) {
      return {ok:true, trung:true, message:"Thửa này đã được nhập rồi", row:i+2};
    }
  }
  return {ok:true, trung:false};
}

function testUploadDriveEaKar() {
  var cfg = getXaConfig_("24373");
  var folder = DriveApp.getFolderById(cfg.folderId);
  var f = folder.createFile("TEST_UPLOAD_EAKAR_V20.txt", "Apps Script đã có quyền ghi vào thư mục.");
  return f.getUrl();
}

function testCauHinhEaKar() {
  return getXaConfig_("24373");
}

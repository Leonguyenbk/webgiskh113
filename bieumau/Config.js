/**
 * Database + Config helpers
 */

function getXaConfig(maXa) {
  return getXaConfig_(maXa);
}

function getXaConfig_(maXa) {
  maXa = String(maXa || DEFAULT_MA_XA).trim();

  var all = readAllConfigXaCached_();
  if (all && all.length) {
    for (var a = 0; a < all.length; a++) {
      if (String(all[a].maXa) === maXa) {
        return {
          maXa: maXa,
          tenXa: all[a].tenXa || "",
          spreadsheetId: all[a].spreadsheetId || (maXa === "24373" ? DEFAULT_SPREADSHEET_ID : ""),
          folderId: all[a].folderId || (maXa === "24373" ? DEFAULT_FOLDER_EAKAR : "")
        };
      }
    }
  }

  var fromConfigSheet = readConfigSheet_(maXa);
  if (fromConfigSheet && (fromConfigSheet.spreadsheetId || fromConfigSheet.folderId)) return fromConfigSheet;

  // Fallback chắc chắn cho Ea Kar để test ngay
  if (maXa === "24373") {
    return {
      maXa: "24373",
      tenXa: "Xã Ea Kar",
      spreadsheetId: DEFAULT_SPREADSHEET_ID,
      folderId: DEFAULT_FOLDER_EAKAR
    };
  }

  for (var i = 0; i < STATIC_XA.length; i++) {
    if (String(STATIC_XA[i].maXa) === maXa) {
      return {
        maXa: maXa,
        tenXa: STATIC_XA[i].tenXa,
        spreadsheetId: STATIC_XA[i].spreadsheetId || "",
        folderId: STATIC_XA[i].folderId || ""
      };
    }
  }

  return {
    maXa: maXa,
    tenXa: "",
    spreadsheetId: "",
    folderId: ""
  };
}

function readConfigSheet_(maXa) {
  try {
    var ss = SpreadsheetApp.openById(CONFIG_SPREADSHEET_ID);
    var sh = ss.getSheets()[0];
    var values = sh.getDataRange().getValues();
    if (values.length < 2) return null;

    var headers = values[0].map(normalizeHeader_);
    var idxMa = findCol_(headers, ["maxa","ma","madonvihanhchinh"]);
    var idxTen = findCol_(headers, ["tenxa","tenxaphuong","xaphuong","tendonvi"]);
    var idxSheet = findCol_(headers, ["linkgooglesheet","googlesheet","linksheet","spreadsheetid","sheet"]);
    var idxDrive = findCol_(headers, ["linkdrive","folderdrive","thumucdrive","folderid","driver"]);
    if (idxMa < 0) return null;

    for (var r = 1; r < values.length; r++) {
      if (String(values[r][idxMa] || "").trim() === maXa) {
        return {
          maXa: maXa,
          tenXa: idxTen >= 0 ? String(values[r][idxTen] || "").trim() : "",
          spreadsheetId: idxSheet >= 0 ? extractSpreadsheetId_(values[r][idxSheet]) : "",
          folderId: idxDrive >= 0 ? extractFolderId_(values[r][idxDrive]) : ""
        };
      }
    }
  } catch (err) {
    return null;
  }
  return null;
}

function openSpreadsheet_(maXa) {
  var cfg = getXaConfig_(maXa);
  return SpreadsheetApp.openById(cfg.spreadsheetId || DEFAULT_SPREADSHEET_ID);
}

function openSheet_(maXa, sheetName) {
  var ss = openSpreadsheet_(maXa);
  var sh = ss.getSheetByName(sheetName);
  if (sh) return sh;

  // Riêng sheet danh sách cần thu thập: tìm linh hoạt theo tên,
  // tránh lỗi do khác VPĐK/VPDK, dấu tiếng Việt, khoảng trắng hoặc phần mô tả trong ngoặc.
  if (sheetName === SHEET_THUA) {
    var found = timSheetCanThuThapManh_(ss);
    if (found) return found;
  }

  throw new Error('Không tìm thấy sheet "' + sheetName + '" cho mã xã ' + maXa + ".");
}

function timSheetCanThuThap_(ss) {
  var sheets = ss.getSheets();

  for (var i = 0; i < sheets.length; i++) {
    var name = sheets[i].getName();
    var clean = normalizeHeader_(name);

    // Nhận các tên như:
    // DSCanThuThap,DangKy (Do VPĐK giao)
    // DSCanThuThap,DangKy (Do VPDK giao)
    // DSCanThuThap,DangKy
    // DSCanThuThap
    if (clean.indexOf("dscanthuthap") >= 0) {
      return sheets[i];
    }
  }

  return null;
}

function ensureSupportSheets_(maXa) {
  var ss = openSpreadsheet_(maXa);
  if (!ss.getSheetByName(SHEET_INDEX)) {
    var idx = ss.insertSheet(SHEET_INDEX);
    idx.getRange(1,1,1,6).setValues([["KEY","Mã xã","Số tờ","Số thửa","Dòng bắt đầu","Số dòng"]]);
    try { idx.hideSheet(); } catch(e) {}
  }
  if (!ss.getSheetByName(SHEET_LOG)) {
    var log = ss.insertSheet(SHEET_LOG);
    log.getRange(1,1,1,6).setValues([["Thời gian","Email","Hành động","KEY","Ghi chú","Phiên bản"]]);
    try { log.hideSheet(); } catch(e) {}
  }
}

function getNextAppendRow_(sh) {
  var lastRow = Math.max(sh.getLastRow(), 1);
  var lastCol = Math.max(sh.getLastColumn(), COL_NHOM);
  if (lastRow < 2) return 2;

  var values = sh.getRange(2, 1, lastRow - 1, lastCol).getDisplayValues();
  var lastData = 1;
  for (var i = 0; i < values.length; i++) {
    var has = false;
    for (var j = 0; j < values[i].length; j++) {
      if (String(values[i][j] || "").trim() !== "") { has = true; break; }
    }
    if (has) lastData = i + 2;
  }
  return lastData + 1;
}

function getMaxStt_(sh) {
  var lastRow = sh.getLastRow();
  if (lastRow < 2) return 0;
  var vals = sh.getRange(2, 1, lastRow - 1, 1).getValues();
  var max = 0;
  for (var i = 0; i < vals.length; i++) {
    var n = Number(vals[i][0]);
    if (!isNaN(n) && n > max) max = n;
  }
  return max;
}

function formatTextColumns_(sh, row, numRows) {
  [COL_SO_PHAT_HANH, 6, 7, 11, COL_MA_DINH_DANH, COL_TO_GCN, COL_THUA_GCN, COL_SO_TO, COL_SO_THUA, COL_TEN_HSQ, COL_LINK_HSQ].forEach(function(col) {
    sh.getRange(row, col, numRows, 1).setNumberFormat("@");
  });
}


function getDanhSachXaForClient_() {
  var list = readAllConfigXaCached_();
  if (list && list.length) {
    return list.map(function(x) {
      return {
        tenXa: x.tenXa || "",
        maXa: String(x.maXa || ""),
        coSheet: !!x.spreadsheetId,
        coThuMucDrive: !!x.folderId
      };
    });
  }

  return STATIC_XA.map(function(x) {
    var cfg = getXaConfig_(x.maXa);
    return {
      tenXa: x.tenXa,
      maXa: String(x.maXa),
      coSheet: !!cfg.spreadsheetId,
      coThuMucDrive: !!cfg.folderId
    };
  });
}

function readAllConfigXaCached_() {
  var cache = CacheService.getScriptCache();
  var cached = cache.get("DANH_SACH_XA_CONFIG");
  if (cached) {
    try { return JSON.parse(cached); } catch (e) {}
  }

  var list = readAllConfigXa_();
  if (list && list.length) {
    cache.put("DANH_SACH_XA_CONFIG", JSON.stringify(list), CONFIG_CACHE_SECONDS);
  }
  return list;
}

function readAllConfigXa_() {
  try {
    var ss = SpreadsheetApp.openById(CONFIG_SPREADSHEET_ID);
    var sh = ss.getSheets()[0];
    var values = sh.getDataRange().getValues();
    if (values.length < 2) return [];

    var headers = values[0].map(normalizeHeader_);
    var idxMa = findCol_(headers, ["maxa","ma","madonvihanhchinh"]);
    var idxTen = findCol_(headers, ["tenxa","tenxaphuong","xaphuong","tendonvi"]);
    var idxSheet = findCol_(headers, ["linkgooglesheet","googlesheet","linksheet","spreadsheetid","sheet"]);
    var idxDrive = findCol_(headers, ["linkdrive","folderdrive","thumucdrive","folderid","driver"]);
    if (idxMa < 0) return [];

    var out = [];
    for (var r = 1; r < values.length; r++) {
      var maXa = String(values[r][idxMa] || "").trim();
      if (!maXa) continue;

      out.push({
        maXa: maXa,
        tenXa: idxTen >= 0 ? String(values[r][idxTen] || "").trim() : "",
        spreadsheetId: idxSheet >= 0 ? extractSpreadsheetId_(values[r][idxSheet]) : "",
        folderId: idxDrive >= 0 ? extractFolderId_(values[r][idxDrive]) : ""
      });
    }
    return out;
  } catch (err) {
    return [];
  }
}


function getMapThuaCanThuThapCached_(maXa) {
  maXa = String(maXa || DEFAULT_MA_XA).trim();
  var cacheKey = "MAP_THUA_CAN_THU_THAP_" + maXa;
  var cache = CacheService.getScriptCache();
  var cached = cache.get(cacheKey);

  if (cached) {
    try {
      return JSON.parse(cached);
    } catch (e) {}
  }

  var map = buildMapThuaCanThuThap_(maXa);

  // CacheService giới hạn dung lượng; nếu quá lớn thì không cache nhưng vẫn trả kết quả.
  try {
    var text = JSON.stringify(map);
    if (text.length < 95000) {
      cache.put(cacheKey, text, CACHE_THUA_SECONDS);
    }
  } catch (e) {}

  return map;
}


function buildMapThuaCanThuThap_(maXa) {
  var sh = openSheetThuaCanThuThap_(maXa);
  var lastRow = sh.getLastRow();
  var lastCol = sh.getLastColumn();
  if (lastRow < 2) return {};

  var rawHeader = sh.getRange(1, 1, 1, lastCol).getDisplayValues()[0];
  var header = rawHeader.map(normalizeHeader_);

  // Đọc theo TIÊU ĐỀ CỘT, không theo thứ tự cột.
  // Các tiêu đề chính theo mẫu:
  // - "Số hiệu tờ bản đồ"
  // - "Số thứ tự thửa"
  // - "maDinhdanh"
  var idxTo = findColExactFirst_(header, [
    "sohieutobando",
    "sohieutobandodiachinh",
    "soto",
    "tobando"
  ]);

  var idxThua = findColExactFirst_(header, [
    "sothututhua",
    "sothututhuatrendobandodiachinh",
    "sothua"
  ]);

  var idxMa = findColExactFirst_(header, [
    "madinhdanh",
    "madinhdanhthuadat"
  ]);

  var idxDt = findColExactFirst_(header, [
    "dientich",
    "dientichthuadat"
  ]);

  if (idxTo < 0 || idxThua < 0) {
    throw new Error(
      'Không nhận diện được cột "Số hiệu tờ bản đồ" hoặc "Số thứ tự thửa" trong sheet "' +
      sh.getName() +
      '". Tiêu đề hiện có: ' + rawHeader.join(" | ")
    );
  }

  var values = sh.getRange(2, 1, lastRow - 1, lastCol).getDisplayValues();
  var map = {};

  for (var r = 0; r < values.length; r++) {
    var row = values[r];
    var soTo = normKeyPart_(row[idxTo]);
    var soThua = normKeyPart_(row[idxThua]);
    if (!soTo || !soThua) continue;

    var key = soTo + "_" + soThua;
    map[key] = {
      maDinhDanh: idxMa >= 0 ? String(row[idxMa] || "").trim() : "",
      dienTich: idxDt >= 0 ? String(row[idxDt] || "").trim() : ""
    };
  }

  return map;
}

function findColExactFirst_(headers, candidates) {
  // Ưu tiên khớp chính xác tiêu đề sau chuẩn hóa
  for (var i = 0; i < candidates.length; i++) {
    var c = normalizeHeader_(candidates[i]);
    for (var j = 0; j < headers.length; j++) {
      if (headers[j] === c) return j;
    }
  }

  // Sau đó mới khớp chứa nhau để dự phòng
  for (var a = 0; a < candidates.length; a++) {
    var ca = normalizeHeader_(candidates[a]);
    for (var b = 0; b < headers.length; b++) {
      if (headers[b].indexOf(ca) >= 0 || ca.indexOf(headers[b]) >= 0) return b;
    }
  }

  return -1;
}


function xoaCacheThuaCanThuThap_CU(maXa) {
  maXa = String(maXa || DEFAULT_MA_XA).trim();
  CacheService.getScriptCache().remove("MAP_THUA_CAN_THU_THAP_" + maXa);
  return "Đã xóa cache danh sách thửa cần thu thập cho mã xã " + maXa;
}


function timSheetCanThuThapManh_(ss) {
  var sheets = ss.getSheets();

  // 1) Tìm chính xác trước
  var exact = ss.getSheetByName(SHEET_THUA);
  if (exact) return exact;

  // 2) Tìm theo tên đã chuẩn hóa
  for (var i = 0; i < sheets.length; i++) {
    var name = sheets[i].getName();
    var clean = normalizeHeader_(name);

    if (clean.indexOf("dscanthuthap") >= 0) return sheets[i];
    if (clean.indexOf("dscanthuthapdangky") >= 0) return sheets[i];
    if (clean.indexOf("thuthap") >= 0 && clean.indexOf("dangky") >= 0) return sheets[i];
  }

  // 3) Fallback: nếu file chỉ có Trang tính1 và một sheet dữ liệu nữa thì lấy sheet không phải Trang tính1
  for (var j = 0; j < sheets.length; j++) {
    var n = normalizeHeader_(sheets[j].getName());
    if (n !== normalizeHeader_(SHEET_NHAP) && n !== normalizeHeader_(SHEET_INDEX) && n !== normalizeHeader_(SHEET_LOG)) {
      return sheets[j];
    }
  }

  return null;
}

function openSheetThuaCanThuThap_(maXa) {
  var ss = openSpreadsheet_(maXa);
  var sh = timSheetCanThuThapManh_(ss);
  if (sh) return sh;

  var names = ss.getSheets().map(function(s) { return s.getName(); }).join(", ");
  throw new Error('Không tìm thấy sheet danh sách cần thu thập cho mã xã ' + maXa + '. Các sheet hiện có: ' + names);
}



/**
 * V40 CORE - ĐỌC DANH SÁCH THỬA CẦN THU THẬP
 * Không phụ thuộc tên sheet cố định hoặc thứ tự cột.
 */

function traCuuThuaCanThuThap_(maXa, soTo, soThua) {
  maXa = String(maXa || DEFAULT_MA_XA).trim();
  soTo = normKeyPart_(soTo);
  soThua = normKeyPart_(soThua);

  var map = getMapThuaCanThuThapV40_(maXa);
  return map[soTo + "_" + soThua] || null;
}

function getMapThuaCanThuThapV40_(maXa) {
  maXa = String(maXa || DEFAULT_MA_XA).trim();
  var cacheKey = "V40_MAP_THUA_" + maXa;
  var cache = CacheService.getScriptCache();
  var cached = cache.get(cacheKey);

  if (cached) {
    try {
      return JSON.parse(cached);
    } catch (e) {}
  }

  var built = buildMapThuaCanThuThapV40_(maXa);
  try {
    var text = JSON.stringify(built.map);
    // CacheService giới hạn khoảng 100KB/value.
    if (text.length < 95000) {
      cache.put(cacheKey, text, CACHE_THUA_SECONDS || 600);
    }
  } catch (e) {}

  return built.map;
}

function buildMapThuaCanThuThapV40_(maXa) {
  var ss = openSpreadsheet_(maXa);
  var sh = findSheetThuaCanThuThapV40_(ss);
  if (!sh) {
    throw new Error("Không tìm thấy sheet danh sách cần thu thập. Các sheet hiện có: " + ss.getSheets().map(function(s){return s.getName();}).join(" | "));
  }

  var lastRow = sh.getLastRow();
  var lastCol = sh.getLastColumn();
  if (lastRow < 2 || lastCol < 1) {
    return { map: {}, sheetName: sh.getName() };
  }

  var headers = sh.getRange(1, 1, 1, lastCol).getDisplayValues()[0];
  var idx = detectColumnsThuaV40_(headers, sh.getName());

  var values = sh.getRange(2, 1, lastRow - 1, lastCol).getDisplayValues();
  var map = {};

  for (var r = 0; r < values.length; r++) {
    var row = values[r];
    var soTo = normKeyPart_(row[idx.soTo]);
    var soThua = normKeyPart_(row[idx.soThua]);
    if (!soTo || !soThua) continue;

    map[soTo + "_" + soThua] = {
      soTo: soTo,
      soThua: soThua,
      maDinhDanh: idx.maDinhDanh >= 0 ? String(row[idx.maDinhDanh] || "").trim() : "",
      dienTich: idx.dienTich >= 0 ? String(row[idx.dienTich] || "").trim() : "",
      sheetName: sh.getName()
    };
  }

  return { map: map, sheetName: sh.getName(), columns: idx };
}

function findSheetThuaCanThuThapV40_(ss) {
  var sheets = ss.getSheets();

  // 1. Tên chính xác nếu có.
  var exact = ss.getSheetByName(SHEET_THUA);
  if (exact) return exact;

  // 2. Tên có DSCanThuThap.
  for (var i = 0; i < sheets.length; i++) {
    var clean = normalizeHeader_(sheets[i].getName());
    if (clean.indexOf("dscanthuthap") >= 0) return sheets[i];
  }

  // 3. Tên có ThuThap và DangKy.
  for (var j = 0; j < sheets.length; j++) {
    var c = normalizeHeader_(sheets[j].getName());
    if (c.indexOf("thuthap") >= 0 && c.indexOf("dangky") >= 0) return sheets[j];
  }

  // 4. Dò sheet theo tiêu đề cột bắt buộc.
  for (var k = 0; k < sheets.length; k++) {
    var sh = sheets[k];
    if (sh.getLastRow() < 1 || sh.getLastColumn() < 2) continue;
    var headers = sh.getRange(1, 1, 1, sh.getLastColumn()).getDisplayValues()[0];
    try {
      var idx = detectColumnsThuaV40_(headers, sh.getName(), true);
      if (idx.soTo >= 0 && idx.soThua >= 0) return sh;
    } catch (e) {}
  }

  return null;
}

function detectColumnsThuaV40_(headers, sheetName, silent) {
  var clean = headers.map(normalizeHeader_);

  var soToCandidates = [
    "sohieutobando",
    "sohieutobandodiachinh",
    "sotobando",
    "soto",
    "tobando"
  ];

  var soThuaCandidates = [
    "sothututhua",
    "sothututhuatrendobandodiachinh",
    "sothuathuadat",
    "sothua",
    "thua"
  ];

  var maDinhDanhCandidates = [
    "madinhdanh",
    "madinhdanhthuadat",
    "madinhdanhthua"
  ];

  var dienTichCandidates = [
    "dientich",
    "dientichthuadat",
    "dientichthua"
  ];

  var idxSoTo = findHeaderIndexV40_(clean, soToCandidates);
  var idxSoThua = findHeaderIndexV40_(clean, soThuaCandidates);
  var idxMa = findHeaderIndexV40_(clean, maDinhDanhCandidates);
  var idxDt = findHeaderIndexV40_(clean, dienTichCandidates);

  if ((idxSoTo < 0 || idxSoThua < 0) && !silent) {
    throw new Error(
      'Không nhận diện được cột "Số hiệu tờ bản đồ" hoặc "Số thứ tự thửa" trong sheet "' +
      sheetName + '". Tiêu đề hiện có: ' + headers.join(" | ")
    );
  }

  return {
    soTo: idxSoTo,
    soThua: idxSoThua,
    maDinhDanh: idxMa,
    dienTich: idxDt
  };
}

function findHeaderIndexV40_(cleanHeaders, candidates) {
  // Ưu tiên khớp chính xác.
  for (var c = 0; c < candidates.length; c++) {
    var target = normalizeHeader_(candidates[c]);
    for (var i = 0; i < cleanHeaders.length; i++) {
      if (cleanHeaders[i] === target) return i;
    }
  }

  // Sau đó khớp chứa nhau, nhưng tránh tiêu đề quá ngắn gây nhầm.
  for (var c2 = 0; c2 < candidates.length; c2++) {
    var t = normalizeHeader_(candidates[c2]);
    for (var j = 0; j < cleanHeaders.length; j++) {
      var h = cleanHeaders[j];
      if (!h) continue;
      if (h.indexOf(t) >= 0) return j;
      if (t.length >= 5 && t.indexOf(h) >= 0) return j;
    }
  }

  return -1;
}

function xoaCacheThuaCanThuThap(maXa) {
  maXa = String(maXa || DEFAULT_MA_XA).trim();
  var cache = CacheService.getScriptCache();
  cache.remove("V40_MAP_THUA_" + maXa);
  cache.remove("MAP_THUA_CAN_THU_THAP_" + maXa);
  return "Đã xóa cache danh sách thửa cần thu thập cho mã xã " + maXa;
}

function testTraCuuThuaV40() {
  return traCuuThuaCanThuThap_(DEFAULT_MA_XA, "87", "26");
}

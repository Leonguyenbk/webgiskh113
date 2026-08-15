/**
 * Utils
 */

function isAdmin_() {
  var email = getUserEmail_();
  if (!email) return false;
  for (var i = 0; i < ADMIN_EMAILS.length; i++) {
    if (String(ADMIN_EMAILS[i]).toLowerCase() === email.toLowerCase()) return true;
  }
  return false;
}

function getUserEmail_() {
  try {
    return Session.getActiveUser().getEmail() || Session.getEffectiveUser().getEmail() || "";
  } catch (e) {
    return "";
  }
}

function getDiaChiXa_(maXa) {
  return (getXaConfig_(maXa).tenXa || DEFAULT_TEN_XA) + ", tỉnh Đắk Lắk";
}

function extractSpreadsheetId_(value) {
  var s = String(value || "").trim();
  if (!s) return "";
  var m = s.match(/\/spreadsheets\/d\/([a-zA-Z0-9-_]+)/);
  return m ? m[1] : s;
}

function extractFolderId_(value) {
  var s = String(value || "").trim();
  if (!s) return "";
  var m = s.match(/\/folders\/([a-zA-Z0-9-_]+)/);
  return m ? m[1] : s;
}

function cleanPdfName_(name) {
  var s = String(name || "HSQ.pdf").trim();
  var idx = s.toLowerCase().indexOf(".pdf");
  if (idx >= 0) s = s.substring(0, idx + 4);
  s = s.replace(/[\\:*?"<>|]/g, "_").trim();
  if (!s.toLowerCase().endsWith(".pdf")) s += ".pdf";
  return s;
}

function normKeyPart_(v) {
  var s = String(v === null || v === undefined ? "" : v).trim();
  if (!s) return "";
  if (/^\d+\.0+$/.test(s)) s = s.replace(/\.0+$/, "");
  return s;
}

function normalizeHeader_(s) {
  return String(s || "")
    .toLowerCase()
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/[^a-z0-9]/g, "");
}

function findCol_(headers, candidates) {
  for (var i = 0; i < candidates.length; i++) {
    var c = normalizeHeader_(candidates[i]);
    for (var j = 0; j < headers.length; j++) {
      if (headers[j] === c || headers[j].indexOf(c) >= 0 || c.indexOf(headers[j]) >= 0) return j;
    }
  }
  return -1;
}

function parseNumberVN_(v) {
  var s = String(v || "").trim().replace(/\s/g, "");
  if (!s) return NaN;
  if (s.indexOf(",") >= 0 && s.indexOf(".") >= 0) s = s.replace(/\./g, "").replace(",", ".");
  else s = s.replace(",", ".");
  return Number(s);
}


/**
 * Kiểm tra Số phát hành GCN.
 *
 * Quy tắc:
 * 1) Nếu chỉ gồm số: bắt buộc đúng 10 chữ số, không dấu cách.
 * 2) Nếu gồm chữ + số: bắt buộc có đúng 1 dấu cách giữa phần chữ và phần số.
 *    - Phần chữ: 1 hoặc 2 ký tự chữ.
 *    - Nếu phần chữ có 1 ký tự: phần số dài 8 hoặc 9 số.
 *    - Nếu phần chữ có 2 ký tự: phần số dài 9 hoặc 11 số.
 */
function validateSoPhatHanhGCN_(value) {
  var s = String(value || "").trim().toUpperCase();
  if (!s) return false;

  // Chỉ gồm số: đúng 10 số, không dấu cách
  if (/^\d{10}$/.test(s)) return true;

  // Có chữ + số: bắt buộc có đúng 1 khoảng trắng giữa phần chữ và phần số
  if (!/^[A-ZĐ]{1,2} \d+$/.test(s)) return false;

  var parts = s.split(" ");
  if (parts.length !== 2) return false;

  var letters = parts[0];

  // Tính tổng độ dài cả chữ + khoảng trắng + số
  // 1 ký tự chữ phía trước: tổng độ dài cho phép 8 hoặc 9
  if (letters.length === 1) {
    return s.length === 8 || s.length === 9;
  }

  // 2 ký tự chữ phía trước: tổng độ dài cho phép 9 hoặc 11
  if (letters.length === 2) {
    return s.length === 9 || s.length === 11;
  }

  return false;
}

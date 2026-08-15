/**
 * Index + Drive helpers
 */

function makeThuaKey_(maXa, soTo, soThua) {
  return [String(maXa || DEFAULT_MA_XA).trim(), normKeyPart_(soTo), normKeyPart_(soThua)].join("_");
}

function indexHasKey_(maXa, key) {
  try {
    ensureSupportSheets_(maXa);
    var sh = openSpreadsheet_(maXa).getSheetByName(SHEET_INDEX);
    var lastRow = sh.getLastRow();
    if (lastRow < 2) return false;

    var finder = sh.getRange(2, 1, lastRow - 1, 1)
      .createTextFinder(key)
      .matchEntireCell(true)
      .findNext();
    return !!finder;
  } catch (err) {
    return false;
  }
}

function addIndexKey_(maXa, key, startRow, rowCount) {
  ensureSupportSheets_(maXa);
  var sh = openSpreadsheet_(maXa).getSheetByName(SHEET_INDEX);
  var parts = key.split("_");
  sh.appendRow([key, parts[0], parts[1], parts[2], startRow, rowCount]);
}

function addLog_(maXa, action, key, note) {
  try {
    ensureSupportSheets_(maXa);
    var sh = openSpreadsheet_(maXa).getSheetByName(SHEET_LOG);
    sh.appendRow([new Date(), getUserEmail_(), action, key, note || "", APP_VERSION]);
  } catch (e) {}
}

function uploadFilesSecure_(payload, folderId) {
  var files = payload.files || [];
  if (!files.length) return {ok:true, files:[]};

  if (!folderId) return {ok:false, message:"Chưa cấu hình thư mục Drive cho mã xã " + payload.maXa + "."};

  var folder = DriveApp.getFolderById(folderId);
  var uploaded = [];

  for (var i = 0; i < files.length; i++) {
    var f = files[i];
    if (!f.base64) continue;
    if (String(f.mimeType || "") !== "application/pdf") {
      return {ok:false, message:(f.label || "File") + ": chỉ cho phép PDF."};
    }

    var fileName = cleanPdfName_(f.targetName || f.name || "HSQ.pdf");
    var bytes = Utilities.base64Decode(f.base64);
    var blob = Utilities.newBlob(bytes, "application/pdf", fileName);
    var driveFile = folder.createFile(blob).setName(fileName);

    // Không share file cho người nhập. File giữ nguyên quyền theo thư mục/chủ sở hữu.
    uploaded.push({
      kind: f.kind || "",
      label: f.label || "",
      name: driveFile.getName(),
      fileId: driveFile.getId(),
      url: "" // V39 không trả link Drive về giao diện/Excel
    });
  }

  return {ok:true, files:uploaded};
}

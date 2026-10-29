"""Đọc hồ sơ quét Nhóm 4 bằng AI (Google Gemini) cho trang ẩn /nhom-4-ai —
port phần prompt/schema/chuẩn hoá từ tool desktop (thuadatgml/nhom4_ai.py,
PROMPT_VERSION 19) sang web: người dùng chọn file quét trên form, bấm
"Kiểm tra", backend gửi AI đọc rồi trả dữ liệu để frontend tự điền vào biểu
(Nhom4FormPage.jsx, aiMode). KHÔNG ghi gì vào CSDL — người dùng vẫn soát
lại, nhập số tờ/số thửa theo bản đồ địa chính hiện tại rồi bấm Lưu hồ sơ như
form Nhóm 4 thường.

Khác tool: không có tên file/thư mục mang số tờ/thửa mới (người dùng tự nhập
trên form), nên bỏ hết phần suy tờ/thửa từ tên file; phần bổ sung từ dữ liệu
bản đồ (diện tích, mã định danh, địa chỉ, loại đất) do frontend làm khi người
dùng nhập số tờ/thửa (giống form Nhóm 4 thường). AI có thể đọc sai (nhất là
CCCD, số phát hành, diện tích) — luôn hiện cảnh báo cho người dùng soát lại.
"""

from __future__ import annotations

import base64
import difflib
import json
import re
import threading
import time
import unicodedata
from collections import defaultdict, deque
from datetime import date

import requests
from flask import jsonify

from ..config import Config

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MODEL_MAC_DINH = "gemini-2.5-flash"
MAX_BYTES_MOI_LAN = 18 * 1024 * 1024  # Gemini inline tối đa ~20MB/request
# Cloudflare Tunnel cắt request quá ~100s — giới hạn tổng thời gian chờ AI
# dưới mức đó (1 lần gọi + tối đa 1 lần thử lại ngắn).
AI_TIMEOUT_GIAY = 80

# Trang chưa công khai nhưng API vẫn gọi được từ ngoài, mỗi lượt tốn phí
# Gemini — chặn lạm dụng bằng giới hạn số lượt/giờ theo IP (bộ nhớ tiến
# trình, restart service thì đếm lại).
GIOI_HAN_MOI_GIO = 60
_luot_theo_ip: dict[str, deque] = defaultdict(deque)
_khoa_luot = threading.Lock()

NGUON_GOC_OPTIONS = [
    "Nhà nước giao đất có thu tiền sử dụng đất",
    "Nhà nước giao đất không thu tiền sử dụng đất",
    "Nhà nước cho thuê đất trả tiền hàng năm",
    "Nhà nước cho thuê đất trả tiền một lần",
    "Nhà nước công nhận quyền sử dụng đất như Nhà nước giao đất có thu tiền sử dụng đất",
    "Nhà nước công nhận quyền sử dụng đất như Nhà nước giao đất không thu tiền sử dụng đất",
    "Nhận chuyển nhượng quyền sử dụng đất",
    "Thừa kế quyền sử dụng đất",
    "Tặng cho quyền sử dụng đất",
]
HINH_THUC_SU_DUNG_OPTIONS = ["Sử dụng riêng", "Sử dụng chung"]
LOAI_CHU_OPTIONS = ["Cá nhân", "Đồng sử dụng", "Vợ chồng", "Hộ gia đình"]

# Quy tắc nghiệp vụ Nhóm 4 (giống tool): điền theo loại đất/số người sử dụng
# thay vì tin chữ trên giấy, vì form chỉ nhận đúng các giá trị trong danh sách.
NGUON_CO_THU = NGUON_GOC_OPTIONS[4]
NGUON_KHONG_THU = NGUON_GOC_OPTIONS[5]
LOAI_DAT_O = {"ONT", "ODT"}
LOAI_DAT_LAU_DAI = {"ONT", "ODT", "TSC", "CQP", "CAN", "RPH"}
LOAI_DAT_50_NAM = {"CLN", "LUC", "LUK", "BHK", "NHK", "NTS"}
_SO_NAM_RE = re.compile(r"^\d{1,3}\s*(?:năm)?$", re.IGNORECASE)

MO_TA_LOAI_FILE = {
    "chinh": "File chính — Giấy chứng nhận hoặc Đơn đăng ký cấp GCN (hãy tự xác định là loại nào)",
    "phu": "Giấy tờ kèm theo (CCCD, giấy tờ nguồn gốc...)",
    "tbxn": "Thông báo xác nhận",
}


def _s(desc: str = "") -> dict:
    return {"type": "STRING", "description": desc} if desc else {"type": "STRING"}


def _obj(props: dict) -> dict:
    return {"type": "OBJECT", "properties": props}


_DAT = _obj({
    "loai_dat": _s("Mã loại đất (VD ONT, ODT, CLN, LUC...)"),
    "dien_tich": _s("Diện tích m2 của loại đất này, số thập phân dùng dấu chấm"),
    "nguon_goc_su_dung": _s("Nguồn gốc sử dụng — chọn ĐÚNG 1 giá trị trong danh sách cho phép"),
    "hinh_thuc_su_dung": _s("Sử dụng riêng hoặc Sử dụng chung"),
    "thoi_han_su_dung": _s("ONT/ODT: Lâu dài. Loại khác: số năm (VD 50)"),
})

SCHEMA = _obj({
    "che_do": _s("'Đã có GCN' CHỈ khi trong các tệp có bản quét Giấy chứng nhận ĐÃ CẤP cho chính thửa này; "
                 "'Chưa được cấp GCN' nếu chỉ có đơn đăng ký/hợp đồng/giấy tờ khác, không có GCN"),
    "bang_chung_cap_giay": _s("Căn cứ cho che_do: tệp nào, trang nào, tiêu đề in trên giấy + số phát hành + ngày cấp nếu là GCN đã cấp; "
                              "hoặc 'Không có GCN: Tệp N là Đơn đăng ký/hợp đồng...'"),
    "doi_tuong": _s("'Tổ chức' nếu người đứng tên trên GCN là cơ quan/đơn vị/doanh nghiệp/UBND...; ngược lại 'Hộ gia đình, cá nhân'"),
    "loai_chu": _s("Cá nhân | Đồng sử dụng | Vợ chồng | Hộ gia đình (bỏ trống nếu là tổ chức)"),
    "to_chuc": _obj({
        "ten_to_chuc": _s(), "ma_dinh_danh_to_chuc": _s(), "ho_ten_dai_dien": _s(),
        "ngay_sinh_dai_dien": _s(), "gioi_tinh_dai_dien": _s(),
        "ma_dinh_danh_ca_nhan_dai_dien": _s(), "dia_chi_thuong_tru_dai_dien": _s(),
    }),
    "owners": {"type": "ARRAY", "items": _obj({
        "ho_ten": _s(), "ngay_sinh": _s("yyyy hoặc dd/mm/yyyy"), "gioi_tinh": _s("Nam hoặc Nữ"),
        "cccd": _s("Số CCCD/định danh cá nhân, chỉ chữ số"), "dia_chi_thuong_tru": _s(),
    })},
    "gcn": _obj({
        "so_phat_hanh": _s("Số phát hành (serial) của GCN, giữ nguyên dạng 'CS 12345678'"),
        "so_vao_so": _s(), "ngay_cap": _s("dd/mm/yyyy"),
    }),
    "nguoi_su_dung_hien_tai": _obj({
        "ho_ten": _s("MỘT người: người nhận MỚI NHẤT theo trang 'Những thay đổi sau khi cấp GCN'; nếu nhận cả vợ chồng/nhiều người thì ghi người ĐẦU TIÊN (ông/chủ hộ); rỗng nếu chưa có thay đổi"),
        "cccd": _s(), "dia_chi_thuong_tru": _s(),
        "ly_do_thay_doi": _s("Nội dung thay đổi mới nhất: chuyển nhượng, thừa kế, tặng cho..."),
    }),
    "chinh_ly": _s("Tóm tắt TẤT CẢ các dòng chỉnh lý/biến động ở trang 'Những thay đổi sau khi cấp GCN' "
                   "(ngày - nội dung), theo thứ tự thời gian; rỗng nếu GCN không có chỉnh lý"),
    "thua_list": {"type": "ARRAY", "items": _obj({
        "so_to_gcn": _s("Số tờ bản đồ IN TRÊN GCN/đơn (số cũ, có thể khác số trong tên file)"),
        "so_thua_gcn": _s("Số thửa IN TRÊN GCN/đơn (số cũ, có thể khác số trong tên file)"),
        "ma_dinh_danh": _s("Mã định danh thửa đất"), "dia_chi_thua_dat": _s(),
        "dien_tich_thua_dat": _s("Diện tích RIÊNG của thửa này (m2, số thập phân dùng dấu chấm). Nếu giấy chỉ ghi 1 TỔNG diện tích chung "
                                 "cho nhiều thửa thì để rỗng — tuyệt đối không gán tổng đó cho một thửa"),
        "dat1": _DAT, "dat2": _DAT,
        "loai_dat_khac": _s("CHỈ khi thửa có HƠN 2 loại đất: liệt kê các loại đất còn lại ngoài dat1/dat2, dạng 'MÃ diện_tích; MÃ diện_tích'. Không có thì để rỗng"),
    })},
    "tai_lieu": {"type": "ARRAY", "items": _obj({
        "tep": _s("Số thứ tự tệp, đúng như đã liệt kê: 'Tệp 1', 'Tệp 2'..."),
        "loai": _s("GCN (giấy chứng nhận) | DDK (đơn đăng ký) | GT (giấy tờ kèm: CCCD, nguồn gốc...) | TBXN (thông báo xác nhận)"),
    })},
    "co_chuyen_quyen": _s("'Có' nếu trang chỉnh lý/biến động có đính chính chuyển nhượng/thừa kế/tặng cho; 'Không' nếu không có (hoặc không có trang chỉnh lý)"),
    "nguoi_co_cccd": {"type": "ARRAY", "items": _obj({
        "ho_ten": _s("Họ tên in trên thẻ"), "ngay_sinh": _s("dd/mm/yyyy"), "gioi_tinh": _s("Nam hoặc Nữ"),
        "cccd": _s("Số CCCD 12 chữ số"), "dia_chi_thuong_tru": _s("Nơi thường trú in trên thẻ"), "tep": _s("Tệp nào, VD 'Tệp 2'"),
    })},
    "ghi_chu": _s("Nêu các chỗ đọc không chắc chắn / mờ / thiếu — để người soát lại"),
})


def tao_prompt(loai_files: list[str], ten_xa: str, ma_xa: str) -> str:
    ds_file = "\n".join(f"- Tệp {i}: {MO_TA_LOAI_FILE.get(loai, 'chưa rõ loại — hãy tự xác định')}"
                        for i, loai in enumerate(loai_files, 1))
    bo_cuc_xa = (f"\nHồ sơ này thuộc {ten_xa} (mã xã {ma_xa}): thửa đất và địa chỉ thường trú thường nằm trong xã/phường này — "
                 "dùng để đối chiếu tên thôn/tổ/khu phố khi chữ khó đọc, nhưng vẫn CHỈ ghi những gì thấy trên giấy, không tự thêm tên xã nếu giấy không ghi.\n"
                 if ten_xa else "")
    return f"""Bạn là trợ lý nhập liệu hồ sơ đất đai Việt Nam. Đọc các file quét đính kèm rồi trích xuất thông tin thành JSON đúng schema.
{bo_cuc_xa}
Các file:
{ds_file}

QUY TẮC (rất quan trọng):
- ĐÃ CẤP GIẤY HAY CHƯA (quan trọng nhất): 'Đã có GCN' CHỈ KHI có bản quét GIẤY CHỨNG NHẬN đã cấp (tiêu đề "Giấy chứng nhận quyền sử dụng đất..." hoặc "Giấy chứng nhận quyền sử dụng đất, quyền sở hữu nhà ở và tài sản khác gắn liền với đất", có SỐ PHÁT HÀNH/seri, có ngày cấp và cơ quan cấp) của chính thửa đang xét. Đơn đăng ký cấp GCN, tờ khai, hợp đồng, biên bản, CCCD, giấy tờ nguồn gốc KHÔNG phải GCN. Chỉ có các giấy đó => 'Chưa được cấp GCN' và để gcn.so_phat_hanh rỗng. Bản GCN của thửa/chủ khác (chỉ đính kèm làm giấy tờ) không tính. Nêu căn cứ vào bang_chung_cap_giay.
- Có thể có NHIỀU file cho cùng 1 thửa (nhiều trang/nhiều loại giấy): đọc tất cả, gộp thông tin. Liệt kê từng tệp vào tai_lieu (Tệp 1, Tệp 2...) kèm loại.
- so_to_gcn / so_thua_gcn: CHỈ chép số in trong ô "Tờ bản đồ số" / "Thửa đất số" trên chính tờ GCN/đơn (số cũ theo hồ sơ địa chính lúc cấp giấy). Giấy đời cũ có thể KHÔNG có ô "Thửa đất số"/"Tờ bản đồ số" mà chỉ ghi "Lô đất số: NN" (kèm "Khu"): khi đó lấy số lô làm so_thua_gcn, để so_to_gcn rỗng và nêu rõ trong ghi_chu rằng đây là số lô. Không thấy số nào thì để rỗng — tuyệt đối không suy ra từ tên tệp hay nơi khác.
- CHỈ ghi thông tin THẤY RÕ trong tài liệu. Không đoán, không bịa. Không đọc được/không có thì để chuỗi rỗng "" và nêu trong "ghi_chu".
- loai_chu: 'Cá nhân' = 1 người đứng tên; 'Vợ chồng' = ông và bà cùng đứng tên (ghi ông trước, bà sau); 'Hộ gia đình' = ghi "Hộ ông/bà ..." hoặc liệt kê các thành viên hộ (chủ hộ trước); 'Đồng sử dụng' = nhiều người không phải vợ chồng/hộ. owners liệt kê theo đúng thứ tự trên giấy. Tổ chức (UBND, sở/ban/ngành, công ty, hợp tác xã, trường học, bệnh viện, nhà thờ/chùa/cơ sở tôn giáo... — không phải người thật đứng tên) thì doi_tuong='Tổ chức', điền to_chuc (tên tổ chức, mã định danh/mã số thuế, người đại diện nếu có), để owners và loai_chu rỗng.
- CHỈNH LÝ / BIẾN ĐỘNG: GCN có trang "Những thay đổi sau khi cấp Giấy chứng nhận" (thường trang 3-4, có dấu/chữ ký, có thể viết tay). Nếu có: (1) TRANG CHỈNH LÝ MỚI NHẤT LÀ NGUỒN ƯU TIÊN: nếu dòng chỉnh lý mới nhất (theo ngày) cho thấy quyền sử dụng đã chuyển sang người khác (chuyển nhượng/thừa kế/tặng cho...) thì owners = TẤT CẢ những người nhận mới nhất đó, theo thứ tự ghi trên giấy (VD vợ chồng nhận chuyển nhượng -> 2 phần tử, loai_chu='Vợ chồng', ông trước bà sau); TUYỆT ĐỐI KHÔNG đưa người đã chuyển nhượng/để lại (chủ cũ, người đứng tên ở trang 1) vào owners hay bất kỳ trường nào — không cần thông tin của họ. nguoi_su_dung_hien_tai để RỖNG hoàn toàn trong trường hợp này (chủ mới đã nằm ở owners). Chưa có chỉnh lý đổi người thì owners là người đứng tên trên GCN (trang trong); (2) chỉ dùng nguoi_su_dung_hien_tai khi thực tế có người đang sử dụng đất KHÁC với chủ được ghi (không phải do chuyển quyền), kèm ly_do_thay_doi; (3) nếu chỉnh lý làm đổi diện tích, mục đích/loại đất, số tờ, số thửa (tách/hợp thửa...) thì thua_list dùng giá trị MỚI NHẤT sau chỉnh lý; (4) tóm tắt mọi dòng chỉnh lý vào chinh_ly và ghi chú chỗ không rõ vào ghi_chu. Không có trang chỉnh lý trong file thì để nguoi_su_dung_hien_tai và chinh_ly rỗng, KHÔNG suy đoán.
- CCCD TRONG HỒ SƠ: liệt kê MỌI thẻ căn cước công dân (CCCD 12 số) có trong bất kỳ tệp nào vào nguoi_co_cccd, mỗi thẻ 1 phần tử (mặt trước và mặt sau của cùng 1 thẻ gộp làm 1), chép nguyên văn từ thẻ: họ tên, ngày sinh dd/mm/yyyy, giới tính, số CCCD (đủ 12 chữ số), nơi thường trú, tệp. Kể cả thẻ của người KHÔNG phải chủ sử dụng. Không có thẻ nào thì để rỗng.
- HỌ TÊN: chép ĐÚNG từng chữ và DẤU tiếng Việt (VD Trí/Trị, Loan/Loạn khác nhau hoàn toàn). Tên in hoa trên CCCD là chuẩn nhất; nếu chỉ có chữ viết tay/dấu mộc mờ thì đối chiếu với các nơi khác trong hồ sơ (CCCD, hợp đồng, đơn) và nêu trong ghi_chu chỗ còn nghi ngờ dấu.
- AI LÀ CHỦ SỬ DỤNG ĐẤT (quy tắc nghiệp vụ): (1) trang chỉnh lý (thường trang 4, 'Những thay đổi sau khi cấp Giấy chứng nhận') có đính chính chuyển nhượng/thừa kế/tặng cho -> chủ là những người nhận MỚI NHẤT, co_chuyen_quyen='Có'; (2) không có đính chính chuyển quyền nào -> NGƯỜI ĐỨNG TÊN TRÊN GCN chính là chủ, co_chuyen_quyen='Không'. owners chép theo GIẤY GỐC (GCN/chỉnh lý/đơn) của những người đó: họ tên, số CMND/CCCD in cạnh tên (VD 'số CMND: 012345678' — BẮT BUỘC chép vào cccd, kể cả 9 số, không bỏ trống nếu giấy có ghi), năm sinh, giới tính ('Hộ bà'/'bà' = Nữ; 'ông' = Nam), địa chỉ. KHÔNG tự thay bằng thông tin trên CCCD và KHÔNG đưa người không phải chủ vào owners — việc đối chiếu/thay bằng CCCD mới nhất do chương trình làm từ nguoi_co_cccd.
- ngay_sinh: 'yyyy' hoặc 'dd/mm/yyyy'. ngay_cap: 'dd/mm/yyyy'. CCCD chỉ gồm chữ số (12 số).
- Mã loại đất viết hoa (ONT, ODT, CLN, LUC, LUK, BHK, NHK, NTS, RSX, RPH, SKC, TMD, TSC, CQP, CAN...). Nếu 1 thửa có 2 loại đất thì điền lần lượt dat1, dat2 (theo thứ tự trên giấy) kèm diện tích riêng từng loại; nếu chỉ 1 loại thì dat2 để rỗng. Nếu thửa có HƠN 2 loại đất thì dat1, dat2 là 2 loại đầu theo thứ tự trên giấy và các loại còn lại KHÔNG được bỏ đi mà ghi vào loai_dat_khac (mã + diện tích). Diện tích các loại đất cộng lại phải bằng diện tích thửa; nếu giấy không khớp thì nêu trong ghi_chu.
- nguon_goc_su_dung phải chọn ĐÚNG 1 trong: {' | '.join(NGUON_GOC_OPTIONS)}. hinh_thuc_su_dung: {' | '.join(HINH_THUC_SU_DUNG_OPTIONS)}.
- thoi_han_su_dung: đất ONT/ODT ghi 'Lâu dài'; loại đất khác ghi SỐ NĂM (VD '50'); nếu giấy chỉ ghi ngày hết hạn thì để rỗng.
- Diện tích: số theo m2, dùng dấu chấm thập phân, KHÔNG dùng dấu phân cách hàng nghìn.
- so_phat_hanh: chuỗi in trên GCN (VD 'CS 12345678', 'DA 123456'); hồ sơ chưa cấp GCN thì để rỗng.
- Nếu hồ sơ/đơn có nhiều thửa thì MỖI thửa là 1 phần tử riêng trong thua_list (kể cả khi đơn viết gộp "thửa 46, 53, 68, 69" hoặc chỉ ghi 1 tổng diện tích chung). Diện tích từng thửa chỉ điền khi giấy ghi riêng cho thửa đó; chỉ có tổng chung thì để rỗng và nêu trong ghi_chu."""


class LoiAI(Exception):
    pass


def _bo_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise LoiAI("AI trả về không phải JSON hợp lệ") from exc
    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict):
        raise LoiAI("AI trả về JSON không đúng cấu trúc")
    return data


def goi_gemini(api_key: str, model: str, prompt: str, files: list[tuple[str, bytes]]) -> dict:
    """files: [(mime, nội dung)]. Hết AI_TIMEOUT_GIAY thì báo lỗi thay vì thử
    lại mãi (request web phải trả về trước khi Cloudflare cắt)."""
    parts: list[dict] = [{"text": prompt}]
    for mime, data in files:
        parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}})

    url = GEMINI_URL.format(model=model)
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    cau_hinh = {"temperature": 0, "responseMimeType": "application/json", "responseSchema": SCHEMA}
    het_han = time.monotonic() + AI_TIMEOUT_GIAY
    da_bo_schema = False
    while True:
        con_lai = het_han - time.monotonic()
        if con_lai < 5:
            raise LoiAI("AI phản hồi quá lâu — thử lại sau ít phút")
        body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": cau_hinh}
        try:
            r = requests.post(url, headers=headers, json=body, timeout=con_lai)
        except requests.Timeout as exc:
            raise LoiAI("AI phản hồi quá lâu — thử lại sau ít phút") from exc
        except requests.RequestException as exc:
            raise LoiAI("Máy chủ không kết nối được tới AI") from exc

        if r.status_code == 200:
            data = r.json()
            try:
                return _bo_json(data["candidates"][0]["content"]["parts"][0]["text"])
            except (KeyError, IndexError, TypeError) as exc:
                ly_do = (data.get("promptFeedback") or {}).get("blockReason") if isinstance(data, dict) else None
                raise LoiAI(f"AI không trả kết quả (blockReason={ly_do})") from exc
        if r.status_code == 400 and not da_bo_schema:
            # Schema bị từ chối (VD model không hỗ trợ) -> gửi lại chỉ với JSON mode.
            da_bo_schema = True
            cau_hinh = {"temperature": 0, "responseMimeType": "application/json"}
            parts[0] = {"text": prompt + "\n\nTrả về DUY NHẤT 1 JSON có các khóa: " + ", ".join(SCHEMA["properties"])}
            continue
        if r.status_code in (429, 500, 502, 503, 504) and het_han - time.monotonic() > 20:
            time.sleep(5)
            continue
        try:
            loi = r.json().get("error", {}).get("message", "")
        except ValueError:
            loi = r.text[:200]
        raise LoiAI(f"AI báo lỗi HTTP {r.status_code}: {loi}")


# ---------------------------------------------------------------------
# Chuẩn hoá kết quả AI -> dữ liệu điền form (giống nhom4_ai.ai_sang_payload)
# ---------------------------------------------------------------------

def _parse_so(value) -> float | None:
    s = str(value if value is not None else "").strip().replace(" ", "")
    if not s:
        return None
    s = s.replace(".", "").replace(",", ".") if "," in s and "." in s else s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _so(value) -> str:
    n = _parse_so(value)
    return "" if n is None else (str(int(n)) if float(n).is_integer() else repr(round(n, 4)))


def _cccd(value) -> str:
    s = re.sub(r"\D", "", str(value or ""))
    return s.zfill(12) if len(s) == 11 else s  # CCCD mất số 0 đầu khi AI đọc thành số


_SO_PHAT_HANH_CHU_SO = re.compile(r"([A-ZĐ]{1,2})\s*(\d{5,11})")


def _so_phat_hanh(value) -> str:
    """Bỏ chữ 'Số'/'Seri' AI hay chép thừa: 'SỐAB 113951' -> 'AB 113951'; 10 số giữ nguyên."""
    s = str(value or "").upper().strip()
    if re.fullmatch(r"\d{10}", re.sub(r"\D", "", s)) and not re.search(r"[A-ZĐ]\s*\d", s):
        return re.sub(r"\D", "", s)
    m = _SO_PHAT_HANH_CHU_SO.search(s)
    return f"{m.group(1)} {m.group(2)}" if m else s


def _gioi_tinh(value) -> str:
    v = str(value or "").strip().lower()
    return "Nam" if v in ("nam", "ông", "ong") else "Nữ" if v in ("nữ", "nu", "bà", "ba") else ""


def _str(value) -> str:
    return str(value or "").strip()


def _dat(d: dict | None) -> dict:
    d = d if isinstance(d, dict) else {}
    return {
        "loai_dat": _str(d.get("loai_dat")).upper(),
        "dien_tich": _so(d.get("dien_tich")),
        "nguon_goc_su_dung": _str(d.get("nguon_goc_su_dung")),
        "hinh_thuc_su_dung": _str(d.get("hinh_thuc_su_dung")),
        "thoi_han_su_dung": _str(d.get("thoi_han_su_dung")),
    }


def _gan_gia_tri(value: str, options: list[str], cutoff: float = 0.6) -> str:
    v = (value or "").strip()
    if not v or v in options:
        return v
    khop = difflib.get_close_matches(v.lower(), [o.lower() for o in options], n=1, cutoff=cutoff)
    return next((o for o in options if o.lower() == khop[0]), v) if khop else v


def suy_ra_tu_cccd(cccd) -> tuple[str | None, str | None]:
    """Giới tính + NĂM sinh từ CCCD 12 số: ký tự thứ 4 (chẵn = Nam, lẻ = Nữ;
    0/1 = 19xx, 2/3 = 20xx...), ký tự thứ 5-6 = 2 số cuối năm sinh."""
    s = re.sub(r"\D", "", str(cccd or ""))
    if len(s) != 12:
        return None, None
    d4 = int(s[3])
    nam = 1900 + 100 * (d4 // 2) + int(s[4:6])
    return ("Nam" if d4 % 2 == 0 else "Nữ"), (str(nam) if nam <= date.today().year else None)


def _bo_sung_tu_cccd(o: dict, k_ten: str, k_gt: str, k_ns: str, k_cccd: str, canh_bao: list[str]) -> None:
    gt, nam = suy_ra_tu_cccd(o.get(k_cccd))
    ten = o.get(k_ten) or "Chủ sử dụng"
    if gt:
        if not o.get(k_gt):
            o[k_gt] = gt
            canh_bao.append(f"{ten}: giới tính '{gt}' suy từ CCCD (ký tự thứ 4)")
        elif o[k_gt] != gt:
            canh_bao.append(f"{ten}: giới tính ghi '{o[k_gt]}' nhưng CCCD cho thấy '{gt}' (ký tự thứ 4) — nên đối chiếu")
    if nam:
        if not o.get(k_ns):
            o[k_ns] = nam
            canh_bao.append(f"{ten}: năm sinh {nam} suy từ CCCD (ký tự thứ 5-6)")
        elif not o[k_ns].endswith(nam):
            canh_bao.append(f"{ten}: năm sinh ghi '{o[k_ns]}' nhưng CCCD cho thấy {nam} (ký tự thứ 5-6) — nên đối chiếu")


def _token_ten(text) -> list[str]:
    t = unicodedata.normalize("NFD", str(text or "").lower().replace("đ", "d"))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", " ", t).split()


def _giong_ten(a, b) -> bool:
    ta, tb = _token_ten(a), _token_ten(b)
    if not ta or not tb:
        return False
    if difflib.SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio() >= 0.8:
        return True
    return min(len(ta), len(tb)) >= 2 and (set(ta) <= set(tb) or set(tb) <= set(ta))


def _doi_chieu_cccd(owners: list[dict], ai: dict, loai_chu: str, canh_bao: list[str]) -> list[dict]:
    """Thay thông tin từng chủ bằng thẻ CCCD 12 số (mới nhất) của chính người
    đó nếu hồ sơ có (khớp họ tên). Ngoại lệ: GCN cấp cho HỘ, 1 chủ, không
    chuyển quyền, hồ sơ có đúng 1 thẻ khác tên -> người trên thẻ là chủ hộ."""
    the = []
    for t in ai.get("nguoi_co_cccd") or []:
        if isinstance(t, dict) and len(_cccd(t.get("cccd"))) == 12 and _str(t.get("ho_ten")):
            the.append({"ho_ten": _str(t["ho_ten"]), "ngay_sinh": _str(t.get("ngay_sinh")),
                        "gioi_tinh": _gioi_tinh(t.get("gioi_tinh")), "cccd": _cccd(t["cccd"]),
                        "dia_chi_thuong_tru": _str(t.get("dia_chi_thuong_tru")), "tep": _str(t.get("tep"))})
    if not the or not owners:
        return owners

    keys = ("ho_ten", "ngay_sinh", "gioi_tinh", "cccd", "dia_chi_thuong_tru")
    con_lai, ket_qua, da_khop = list(the), [], 0
    for o in owners:
        khop = next((t for t in con_lai if _giong_ten(o["ho_ten"], t["ho_ten"])), None)
        if khop:
            con_lai.remove(khop)
            da_khop += 1
            moi = {**o, **{k: khop[k] for k in keys if khop[k]}}
            canh_bao.append(f"{moi['ho_ten']}: dùng thông tin từ CCCD {khop['tep']} (CCCD mới nhất) thay cho giấy gốc".replace("  ", " "))
            ket_qua.append(moi)
        else:
            ket_qua.append(o)

    if (not da_khop and len(owners) == 1 and len(the) == 1 and loai_chu == "Hộ gia đình"
            and _str(ai.get("co_chuyen_quyen")).lower() != "có"):
        t = the[0]
        canh_bao.append(f"GCN cấp cho hộ '{owners[0]['ho_ten']}' nhưng hồ sơ chỉ có CCCD của {t['ho_ten']} — theo quy tắc lấy người trên CCCD làm "
                        "chủ hộ hiện nay; nên đối chiếu quan hệ với hộ trên GCN")
        return [{**owners[0], **{k: t[k] for k in keys if t[k]}}]
    for t in con_lai:
        canh_bao.append(f"CCCD của {t['ho_ten']} {t['tep']} không khớp chủ sử dụng nào — không dùng".replace("  ", " "))
    return ket_qua


def _nhan_dien_cap_giay(loai_files: list[str], ai: dict) -> tuple[str, bool, str]:
    """'Đã có GCN'/'Chưa được cấp GCN' từ nhiều dấu hiệu độc lập (AI kết
    luận, có số phát hành, AI xếp tệp nào vào loại GCN) -> (kết luận, chắc
    chắn?, lý do khi không chắc)."""
    tai_lieu = [_str(t.get("loai")).upper() for t in ai.get("tai_lieu") or [] if isinstance(t, dict)]
    dau_hieu = {
        "AI kết luận": {"Đã có GCN": True, "Chưa được cấp GCN": False}.get(ai.get("che_do")),
        "có số phát hành": bool(_so_phat_hanh((ai.get("gcn") or {}).get("so_phat_hanh"))),
        "có tệp loại GCN": "GCN" in tai_lieu if tai_lieu else None,
    }
    if ai.get("che_do") not in ("Đã có GCN", "Chưa được cấp GCN") and not tai_lieu:
        return "Chưa được cấp GCN", False, "AI không nhận diện được loại hồ sơ"
    co = [k for k, v in dau_hieu.items() if v is True]
    khong = [k for k, v in dau_hieu.items() if v is False]
    if not khong:
        return ("Đã có GCN", True, "") if co else ("Chưa được cấp GCN", True, "")
    if not co:
        return "Chưa được cấp GCN", True, ""
    ket_luan = "Đã có GCN" if len(co) > len(khong) else "Chưa được cấp GCN"
    return ket_luan, False, f"dấu hiệu 'đã có': {', '.join(co)}; dấu hiệu 'chưa': {', '.join(khong)}"


def ap_quy_tac_mac_dinh(ket_qua: dict, canh_bao: list[str]) -> None:
    """Nguồn gốc / hình thức / thời hạn theo quy tắc Nhóm 4 (sửa thẳng ket_qua):
    ONT/ODT -> công nhận như giao đất CÓ thu tiền, loại khác -> KHÔNG thu
    tiền; 1 người (hoặc tổ chức) -> Sử dụng riêng, từ 2 người -> chung; đất
    ở/cơ quan/quốc phòng/an ninh/phòng hộ -> Lâu dài, nông nghiệp -> số năm
    (mặc định 50). Frontend áp lại đúng quy tắc này khi loại đất được điền
    thêm từ dữ liệu bản đồ (xem apQuyTacDat trong Nhom4FormPage.jsx)."""
    la_to_chuc = ket_qua["doi_tuong"] == "Tổ chức"
    so_nguoi = 1 if la_to_chuc else len([o for o in ket_qua["owners"] if o.get("ho_ten")])
    hinh_thuc = "Sử dụng chung" if so_nguoi >= 2 else "Sử dụng riêng"

    doi: dict[str, set] = defaultdict(set)
    for t in ket_qua["thua_list"]:
        for d in (t["dat1"], t["dat2"]):
            loai = d["loai_dat"]
            if not loai:
                continue
            nguon = NGUON_CO_THU if loai in LOAI_DAT_O else NGUON_KHONG_THU
            if d["nguon_goc_su_dung"] and d["nguon_goc_su_dung"] != nguon:
                doi["Nguồn gốc"].add(f"'{d['nguon_goc_su_dung']}' -> '{nguon}' ({loai})")
            d["nguon_goc_su_dung"] = nguon
            if d["hinh_thuc_su_dung"] and d["hinh_thuc_su_dung"] != hinh_thuc:
                doi["Hình thức"].add(f"'{d['hinh_thuc_su_dung']}' -> '{hinh_thuc}' ({so_nguoi} người sử dụng)")
            d["hinh_thuc_su_dung"] = hinh_thuc
            th = d["thoi_han_su_dung"]
            if loai in LOAI_DAT_LAU_DAI:
                moi = "Lâu dài"
            elif loai in LOAI_DAT_50_NAM:
                moi = th if _SO_NAM_RE.match(th) else "50"
            else:
                moi = th  # RSX/SKC/TMD...: quy tắc không rõ -> giữ chữ trên giấy, người kiểm tra xem
            if th and th != moi:
                doi["Thời hạn"].add(f"'{th}' -> '{moi}' ({loai})")
            d["thoi_han_su_dung"] = moi
    for ten, cac in doi.items():
        canh_bao.append(f"{ten} trên giấy đã quy về theo quy tắc Nhóm 4: " + "; ".join(sorted(cac)))


def ai_sang_form(loai_files: list[str], ai: dict) -> tuple[dict, list[str]]:
    canh_bao: list[str] = []
    if ai.get("chinh_ly"):
        canh_bao.append(f"Hồ sơ CÓ CHỈNH LÝ — nên soát lại người sử dụng hiện tại/diện tích: {ai['chinh_ly']}")
    if ai.get("ghi_chu"):
        canh_bao.append(f"AI ghi chú: {ai['ghi_chu']}")

    che_do, chac_chan, ly_do = _nhan_dien_cap_giay(loai_files, ai)
    if not chac_chan:
        canh_bao.insert(0, f"NHẬN DIỆN ĐÃ CẤP GIẤY/CHƯA KHÔNG CHẮC CHẮN (chọn '{che_do}'): {ly_do} — xem lại hồ sơ")

    ai_tc = ai.get("to_chuc") if isinstance(ai.get("to_chuc"), dict) else {}
    doi_tuong = "Tổ chức" if ai.get("doi_tuong") == "Tổ chức" or _str(ai_tc.get("ten_to_chuc")) else "Hộ gia đình, cá nhân"
    to_chuc = {
        "ten_to_chuc": _str(ai_tc.get("ten_to_chuc")),
        "ma_dinh_danh_to_chuc": _str(ai_tc.get("ma_dinh_danh_to_chuc")),
        "ho_ten_dai_dien": _str(ai_tc.get("ho_ten_dai_dien")),
        "ngay_sinh_dai_dien": _str(ai_tc.get("ngay_sinh_dai_dien")),
        "gioi_tinh_dai_dien": _gioi_tinh(ai_tc.get("gioi_tinh_dai_dien")),
        "ma_dinh_danh_ca_nhan_dai_dien": _cccd(ai_tc.get("ma_dinh_danh_ca_nhan_dai_dien")),
        "dia_chi_thuong_tru_dai_dien": _str(ai_tc.get("dia_chi_thuong_tru_dai_dien")),
    }
    if doi_tuong == "Tổ chức":
        _bo_sung_tu_cccd(to_chuc, "ho_ten_dai_dien", "gioi_tinh_dai_dien", "ngay_sinh_dai_dien",
                         "ma_dinh_danh_ca_nhan_dai_dien", canh_bao)

    owners = [
        {"ho_ten": _str(o.get("ho_ten")), "ngay_sinh": _str(o.get("ngay_sinh")),
         "gioi_tinh": _gioi_tinh(o.get("gioi_tinh")), "cccd": _cccd(o.get("cccd")),
         "dia_chi_thuong_tru": _str(o.get("dia_chi_thuong_tru"))}
        for o in (ai.get("owners") or []) if isinstance(o, dict)
    ]
    owners = [o for o in owners if o["ho_ten"] or o["cccd"]]
    loai_chu = _gan_gia_tri(_str(ai.get("loai_chu")), LOAI_CHU_OPTIONS, cutoff=0.8)
    if loai_chu not in LOAI_CHU_OPTIONS:
        loai_chu = "Cá nhân" if len(owners) <= 1 else "Đồng sử dụng"
    owners = _doi_chieu_cccd(owners, ai, loai_chu, canh_bao)
    for o in owners:
        _bo_sung_tu_cccd(o, "ho_ten", "gioi_tinh", "ngay_sinh", "cccd", canh_bao)
    if doi_tuong != "Tổ chức" and not owners:
        canh_bao.append("Không đọc được chủ sử dụng — hãy nhập tay")
    for o in owners:
        if o["cccd"] and len(o["cccd"]) != 12:
            canh_bao.append(f"{o['ho_ten'] or 'Chủ sử dụng'}: số giấy tờ '{o['cccd']}' không phải CCCD 12 số (có thể là CMND cũ) — cần nhập CCCD")

    ai_gcn = ai.get("gcn") if isinstance(ai.get("gcn"), dict) else {}
    gcn = {"so_phat_hanh": _so_phat_hanh(ai_gcn.get("so_phat_hanh")),
           "so_vao_so": _str(ai_gcn.get("so_vao_so")), "ngay_cap": _str(ai_gcn.get("ngay_cap"))}

    ai_ht = ai.get("nguoi_su_dung_hien_tai") if isinstance(ai.get("nguoi_su_dung_hien_tai"), dict) else {}
    nguoi_ht = {"ho_ten": _str(ai_ht.get("ho_ten")), "cccd": _cccd(ai_ht.get("cccd")),
                "dia_chi_thuong_tru": _str(ai_ht.get("dia_chi_thuong_tru")),
                "ly_do_thay_doi": _str(ai_ht.get("ly_do_thay_doi"))}

    thua_list = []
    ds_thua_ai = [t for t in (ai.get("thua_list") or []) if isinstance(t, dict)]
    if not ds_thua_ai:
        canh_bao.append("Không đọc được thông tin thửa đất trên giấy — nhập tay loại đất/diện tích")
        ds_thua_ai = [{}]
    for t in ds_thua_ai:
        so_to_gcn, so_thua_gcn = _so(t.get("so_to_gcn")), _so(t.get("so_thua_gcn"))
        dat1, dat2 = _dat(t.get("dat1")), _dat(t.get("dat2"))
        nhan = f"Thửa trên giấy tờ {so_to_gcn or '?'}/thửa {so_thua_gcn or '?'}"
        loai_khac = _str(t.get("loai_dat_khac"))
        dien_tich = _so(t.get("dien_tich_thua_dat"))
        if loai_khac:
            canh_bao.append(f"{nhan} có HƠN 2 loại đất — form Nhóm 4 chỉ nhận 2 loại; CHƯA nhập: {loai_khac}")
        elif dat1["loai_dat"] and dat2["loai_dat"]:
            d1, d2, tong = _parse_so(dat1["dien_tich"]), _parse_so(dat2["dien_tich"]), _parse_so(dien_tich)
            if None not in (d1, d2, tong) and abs(d1 + d2 - tong) > 0.05:
                canh_bao.append(f"{nhan}: diện tích loại đất 1 + loại đất 2 = {d1 + d2:g} m² khác diện tích thửa {tong:g} m² — kiểm tra lại")
        if dat1["loai_dat"] and not dat2["loai_dat"] and not dat1["dien_tich"] and dien_tich:
            dat1["dien_tich"] = dien_tich
        thua_list.append({
            "so_to_gcn": so_to_gcn, "so_thua_gcn": so_thua_gcn,
            "ma_dinh_danh": _str(t.get("ma_dinh_danh")),
            "dia_chi_thua_dat": _str(t.get("dia_chi_thua_dat")),
            "dien_tich_thua_dat": dien_tich,
            "dat1": dat1, "dat2": dat2,
        })

    if che_do == "Chưa được cấp GCN":
        # Đơn chỉ tự khai diện tích — giống tool, lấy theo số đo đạc trên
        # bản đồ khi người dùng nhập số tờ/thửa (frontend ghi đè).
        canh_bao.append("Chưa cấp GCN: diện tích thửa sẽ lấy theo bản đồ địa chính khi nhập số tờ/số thửa")

    ket_qua = {
        "che_do": che_do, "che_do_chac_chan": chac_chan,
        "can_cu": _str(ai.get("bang_chung_cap_giay")),
        "doi_tuong": doi_tuong, "loai_chu": loai_chu,
        "owners": owners, "to_chuc": to_chuc, "gcn": gcn,
        "nguoi_su_dung_hien_tai": nguoi_ht, "thua_list": thua_list,
    }
    ap_quy_tac_mac_dinh(ket_qua, canh_bao)
    return ket_qua, canh_bao


def _vuot_gioi_han(ip: str) -> bool:
    now = time.time()
    with _khoa_luot:
        q = _luot_theo_ip[ip]
        while q and now - q[0] > 3600:
            q.popleft()
        if len(q) >= GIOI_HAN_MOI_GIO:
            return True
        q.append(now)
        return False


def doc_ho_so(ma_xa: str, ten_xa: str, files: list[tuple[str, str, bytes]], ip: str):
    """files: [(loại 'chinh'|'phu'|'tbxn', mime, nội dung)] -> (data, error_response)."""
    api_key = Config.GEMINI_API_KEY.strip()
    if not api_key:
        return None, (jsonify({"error": "Máy chủ chưa cấu hình khóa AI (GEMINI_API_KEY)"}), 503)
    if not files:
        return None, (jsonify({"error": "Chưa chọn file hồ sơ quét nào"}), 400)
    tong = sum(len(d) for _, _, d in files)
    if tong > MAX_BYTES_MOI_LAN:
        return None, (jsonify({"error": f"Tổng dung lượng file {tong / 1024 / 1024:.1f}MB vượt giới hạn "
                                        f"{MAX_BYTES_MOI_LAN // (1024 * 1024)}MB mỗi lần đọc"}), 400)
    if _vuot_gioi_han(ip):
        return None, (jsonify({"error": "Đã dùng quá số lượt đọc AI trong 1 giờ — thử lại sau"}), 429)

    model = Config.GEMINI_MODEL.strip() or MODEL_MAC_DINH
    loai_files = [loai for loai, _, _ in files]
    try:
        ai = goi_gemini(api_key, model, tao_prompt(loai_files, ten_xa, ma_xa),
                        [(mime, data) for _, mime, data in files])
    except LoiAI as exc:
        return None, (jsonify({"error": str(exc)}), 502)

    ket_qua, canh_bao = ai_sang_form(loai_files, ai)
    return {"ket_qua": ket_qua, "canh_bao": canh_bao, "model": model}, None

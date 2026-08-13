import { useCallback, useEffect, useState } from "react";

import { saveUngThuaMatch } from "../services/mplisService";

const EMPTY_FORM = { to_thua_mplis: "", so_giay_chung_nhan: "", ma_don_mplis: "" };

// Form "Ứng thửa MPLIS" trong khung thông tin thửa đất — nạp lại mỗi khi
// đổi thửa đang chọn (kể cả bỏ chọn), để không lẫn dữ liệu giữa các thửa.
export function useMplisMatch(parcel) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setForm({
      to_thua_mplis: parcel?.ung_thua?.to_thua_mplis || "",
      so_giay_chung_nhan: parcel?.ung_thua?.so_giay_chung_nhan || "",
      ma_don_mplis: parcel?.ung_thua?.ma_don_mplis || "",
    });
    setError("");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chỉ nạp lại khi đổi thửa
  }, [parcel?.id]);

  const setField = useCallback((field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  }, []);

  const save = useCallback(async () => {
    if (!parcel || !form.to_thua_mplis.trim()) return null;

    setSaving(true);
    setError("");

    try {
      const body = await saveUngThuaMatch({
        ma_xa: parcel.ma_xa,
        so_to: parcel.so_to,
        so_thua: parcel.so_thua,
        to_thua_mplis: form.to_thua_mplis.trim(),
        so_giay_chung_nhan: form.so_giay_chung_nhan.trim(),
        ma_don_mplis: form.ma_don_mplis.trim(),
      });

      return {
        to_thua_mplis: body.item?.to_thua_mplis ?? form.to_thua_mplis.trim(),
        so_giay_chung_nhan:
          body.item?.so_giay_chung_nhan ?? (form.so_giay_chung_nhan.trim() || null),
        ma_don_mplis: body.item?.ma_don_mplis ?? (form.ma_don_mplis.trim() || null),
      };
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setSaving(false);
    }
  }, [parcel, form]);

  return { form, setField, saving, error, save };
}

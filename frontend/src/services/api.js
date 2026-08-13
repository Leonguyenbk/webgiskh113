import { API_URL } from "../config/env";

export { API_URL };

/**
 * Client fetch dùng chung cho mọi service — component không tự viết
 * fetch()/tự dựng URL. Giữ đúng hành vi cũ đang chạy ở từng trang: parse
 * JSON trước, chỉ ném lỗi khi response.ok === false, dùng lỗi từ
 * `body.error` (backend luôn trả {"error": "..."}) hoặc `errorFallback`
 * nếu backend không kèm error.
 */
export async function request(
  path,
  { method = "GET", params, body, token, isFormData = false, signal, errorFallback } = {},
) {
  const query = params
    ? "?" +
      new URLSearchParams(
        Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""),
      ).toString()
    : "";

  const headers = {};
  if (token) headers["X-Import-Token"] = token;
  if (!isFormData) headers["Content-Type"] = "application/json";

  const response = await fetch(`${API_URL}${path}${query}`, {
    method,
    signal,
    headers,
    body: isFormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
  });

  const responseBody = await response.json();
  if (!response.ok) {
    throw new Error(responseBody?.error || errorFallback || "Có lỗi xảy ra, vui lòng thử lại.");
  }
  return responseBody;
}

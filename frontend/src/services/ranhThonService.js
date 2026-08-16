import { request } from "./api";

export function getRanhGioiThon({ maXa } = {}, { signal } = {}) {
  return request("/api/ranh-thon", {
    params: { ma_xa: maXa },
    signal,
    errorFallback: "Không tải được ranh giới thôn",
  });
}

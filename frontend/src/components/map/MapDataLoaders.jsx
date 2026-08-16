import { useEffect } from "react";

import L from "leaflet";
import { useMap } from "react-leaflet";

import { getParcelsByBounds, getParcelsCount, searchParcels } from "../../services/parcelService";
import { boundsForRadius, featureKey } from "../../utils/geometry";
import {
  MAX_FEATURES,
  NEAR_ME_RADII_METERS,
  NEAR_ME_TARGET,
  NEAR_ME_ZOOM,
  PAGE_SIZE,
} from "../../utils/constants";

// Bắt lấy instance bản đồ Leaflet để các nút ở header (ngoài MapContainer)
// vẫn điều khiển được bản đồ.
export function MapInstanceCapture({ onReady }) {
  const map = useMap();

  useEffect(() => {
    onReady(map);
  }, [map, onReady]);

  return null;
}

export function FitBounds({ focusFeature, focusTick }) {
  const map = useMap();

  useEffect(() => {
    if (!focusFeature || focusTick === 0) return;

    map.fitBounds(L.geoJSON(focusFeature).getBounds(), {
      padding: [30, 30],
      maxZoom: 18,
    });

    // Chỉ chạy khi người dùng bấm chọn/phóng đến thửa.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusTick, map]);

  return null;
}

// =========================================================
// TRA CỨU THEO BỘ LỌC
//
// Không còn tự tải toàn tỉnh khi mở trang. Người dùng chọn mã xã
// (bắt buộc), nhóm, số tờ, số thửa rồi bấm "Tra cứu" mới gọi API.
// Component này chỉ chạy lại khi `filters` đổi tham chiếu (mỗi lần
// bấm Tra cứu tạo object filters mới, kể cả giữ nguyên giá trị).
// =========================================================

export function SearchParcelsLoader({ filters, onData, onLoading, onError, onMeta }) {
  const map = useMap();

  useEffect(() => {
    if (!filters) return;

    const controller = new AbortController();

    const run = async () => {
      onLoading(true);
      onError("");
      onData(null);

      const baseParams = { ma_xa: filters.maXa };
      if (filters.nhom?.length) baseParams.nhom = filters.nhom.join(",");
      if (filters.soTo) baseParams.so_to = filters.soTo;
      if (filters.soThua) baseParams.so_thua = filters.soThua;
      if (filters.tenThon) baseParams.ten_thon = filters.tenThon;

      const collected = [];
      const seen = new Set();

      try {
        for (
          let offset = 0;
          offset < MAX_FEATURES && !controller.signal.aborted;
          offset += PAGE_SIZE
        ) {
          const result = await searchParcels(
            { ...baseParams, limit: PAGE_SIZE, offset },
            { signal: controller.signal },
          );

          const features = result?.features || [];
          let added = 0;

          features.forEach((feature) => {
            const key = featureKey(feature);
            if (seen.has(key)) return;
            seen.add(key);
            collected.push(feature);
            added += 1;
          });

          onData({ type: "FeatureCollection", features: collected.slice() });
          onMeta({ loaded: collected.length });

          if (features.length < PAGE_SIZE) break;

          if (added === 0) {
            throw new Error(
              "Server trả về cùng một lô dữ liệu. Kiểm tra p_offset " +
                "trong hàm search_parcels.",
            );
          }

          await new Promise((resolve) => window.setTimeout(resolve, 60));
        }

        // Khớp bản đồ vào chính kết quả vừa tra cứu.
        if (collected.length > 0 && !controller.signal.aborted) {
          const bounds = L.geoJSON({
            type: "FeatureCollection",
            features: collected,
          }).getBounds();

          if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [20, 20], maxZoom: 17 });
          }
        }
      } catch (error) {
        if (error.name !== "AbortError") onError(error.message);
      } finally {
        if (!controller.signal.aborted) onLoading(false);
      }
    };

    run();

    return () => controller.abort();
  }, [filters, map, onData, onLoading, onError, onMeta]);

  return null;
}

// =========================================================
// "QUANH VỊ TRÍ CỦA TÔI"
//
// Không biết trước mã xã, nên không dùng được /api/parcels/search. Dò dần
// bán kính quanh vị trí GPS bằng /api/parcels/count (chỉ đụng index GIST,
// rất nhẹ) tới khi đủ ~NEAR_ME_TARGET thửa, rồi mới gọi /api/parcels
// (bbox) một lần để lấy hình học.
// =========================================================

export function NearMeLoader({ request, onData, onLoading, onError, onMeta }) {
  const map = useMap();

  useEffect(() => {
    if (!request) return;

    const controller = new AbortController();

    const run = async () => {
      onLoading(true);
      onError("");
      onData(null);
      onMeta({ loaded: 0 });

      const { lat, lng, nhom } = request;
      const nhomParam = nhom?.length ? nhom.join(",") : "";

      try {
        let chosenBounds = boundsForRadius(
          lat,
          lng,
          NEAR_ME_RADII_METERS[NEAR_ME_RADII_METERS.length - 1],
        );

        for (const radius of NEAR_ME_RADII_METERS) {
          if (controller.signal.aborted) return;

          const bounds = boundsForRadius(lat, lng, radius);
          chosenBounds = bounds;

          const countResult = await getParcelsCount(
            {
              west: bounds.west,
              south: bounds.south,
              east: bounds.east,
              north: bounds.north,
              center_lng: lng,
              center_lat: lat,
              nhom: nhomParam || undefined,
            },
            { signal: controller.signal, errorFallback: "Không đếm được số thửa quanh vị trí" },
          );

          if ((countResult.total || 0) >= NEAR_ME_TARGET) break;
        }

        if (controller.signal.aborted) return;

        const result = await getParcelsByBounds(
          {
            west: chosenBounds.west,
            south: chosenBounds.south,
            east: chosenBounds.east,
            north: chosenBounds.north,
            center_lng: lng,
            center_lat: lat,
            limit: NEAR_ME_TARGET,
            offset: 0,
            zoom: NEAR_ME_ZOOM,
            nhom: nhomParam || undefined,
          },
          { signal: controller.signal, errorFallback: "Không tải được thửa đất quanh vị trí" },
        );

        const features = result?.features || [];
        onData({ type: "FeatureCollection", features });
        onMeta({ loaded: features.length });

        if (features.length > 0) {
          const bounds = L.geoJSON({
            type: "FeatureCollection",
            features,
          }).getBounds();

          if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [20, 20], maxZoom: 18 });
          }
        }
      } catch (error) {
        if (error.name !== "AbortError") onError(error.message);
      } finally {
        if (!controller.signal.aborted) onLoading(false);
      }
    };

    run();

    return () => controller.abort();
  }, [request, map, onData, onLoading, onError, onMeta]);

  return null;
}

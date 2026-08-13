import L from "leaflet";

export function metersToDegrees(meters, latDeg) {
  const dLat = meters / 111320;
  const dLng = meters / (111320 * Math.max(Math.cos((latDeg * Math.PI) / 180), 0.1));
  return { dLat, dLng };
}

export function boundsForRadius(lat, lng, meters) {
  const { dLat, dLng } = metersToDegrees(meters, lat);
  return { west: lng - dLng, east: lng + dLng, south: lat - dLat, north: lat + dLat };
}

export function featureKey(feature) {
  if (feature.id !== null && feature.id !== undefined) {
    return `id:${String(feature.id)}`;
  }

  const p = feature.properties || {};
  return ["parcel", p.ma_xa, p.so_to, p.so_thua].join(":");
}

export function googleMapsDirectionsUrl(feature) {
  const center = L.geoJSON(feature).getBounds().getCenter();
  return `https://www.google.com/maps/dir/?api=1&destination=${center.lat},${center.lng}`;
}

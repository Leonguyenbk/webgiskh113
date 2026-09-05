import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import "leaflet/dist/leaflet.css";
import "./styles.css";
import App from "./App.jsx";
import ToolsPage from "./ToolsPage.jsx";
import ImportGmlPage from "./ImportGmlPage.jsx";
import ImportSyncPage from "./ImportSyncPage.jsx";
import ManageGcnLinksPage from "./ManageGcnLinksPage.jsx";
import GcnDashboardPage from "./GcnDashboardPage.jsx";
import BieuThongKePage from "./BieuThongKePage.jsx";
import ExportGcnNhom2Page from "./ExportGcnNhom2Page.jsx";
import ExportGcnNhom3Page from "./ExportGcnNhom3Page.jsx";
import MplisSyncPage from "./MplisSyncPage.jsx";
import Nhom4FormPage from "./Nhom4FormPage.jsx";
import ImportRanhThonPage from "./ImportRanhThonPage.jsx";
import ManageBanDoNenPage from "./ManageBanDoNenPage.jsx";

function Root() {
  const [path, setPath] = useState(window.location.pathname);
  const [nhom4Prefill, setNhom4Prefill] = useState(null);

  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  // iOS Safari bỏ qua user-scalable=no, vẫn cho chụm 2 ngón phóng to cả
  // trang. Chặn sự kiện "gesture*" (chỉ Safari phát) để pinch chỉ zoom bản
  // đồ Leaflet (Leaflet dùng touch event nên không bị ảnh hưởng), nhờ đó
  // các nút nổi không trôi theo khi zoom.
  useEffect(() => {
    const stop = (event) => event.preventDefault();
    document.addEventListener("gesturestart", stop);
    document.addEventListener("gesturechange", stop);
    return () => {
      document.removeEventListener("gesturestart", stop);
      document.removeEventListener("gesturechange", stop);
    };
  }, []);

  const navigate = (to) => {
    window.history.pushState({}, "", to);
    setPath(to);
  };

  const navigateToNhom4 = (parcel) => {
    setNhom4Prefill(parcel || null);
    navigate("/nhom-4");
  };

  if (path.startsWith("/tools")) {
    return (
      <ToolsPage
        onNavigateHome={() => navigate("/")}
        onNavigateImport={() => navigate("/import-gml")}
        onNavigateSync={() => navigate("/import-dong-bo")}
        onNavigateGcnLinks={() => navigate("/nguon-gcn")}
        onNavigateGcnDashboard={() => navigate("/thong-ke-gcn")}
        onNavigateBieuThongKe={() => navigate("/thong-ke-nhap-bieu")}
        onNavigateExportGcnNhom2={() => navigate("/xuat-gcn-nhom2")}
        onNavigateExportGcnNhom3={() => navigate("/xuat-gcn-nhom3")}
        onNavigateMplisSync={() => navigate("/cap-nhat-mplis")}
        onNavigateNhom4={() => navigate("/nhom-4")}
        onNavigateRanhThon={() => navigate("/import-ranh-thon")}
        onNavigateBanDoNen={() => navigate("/ban-do-nen")}
      />
    );
  }
  if (path.startsWith("/import-gml")) {
    return <ImportGmlPage onNavigateHome={() => navigate("/")} />;
  }
  if (path.startsWith("/import-dong-bo")) {
    return <ImportSyncPage onNavigateHome={() => navigate("/")} />;
  }
  if (path.startsWith("/nguon-gcn")) {
    return <ManageGcnLinksPage onNavigateHome={() => navigate("/")} />;
  }
  if (path.startsWith("/thong-ke-gcn")) {
    return <GcnDashboardPage onNavigateHome={() => navigate("/")} />;
  }
  if (path.startsWith("/thong-ke-nhap-bieu")) {
    return <BieuThongKePage onNavigateHome={() => navigate("/")} />;
  }
  if (path.startsWith("/xuat-gcn-nhom2")) {
    return <ExportGcnNhom2Page onNavigateHome={() => navigate("/")} />;
  }
  if (path.startsWith("/xuat-gcn-nhom3")) {
    return <ExportGcnNhom3Page onNavigateHome={() => navigate("/")} />;
  }
  if (path.startsWith("/cap-nhat-mplis")) {
    return <MplisSyncPage onNavigateHome={() => navigate("/")} />;
  }
  if (path.startsWith("/nhom-4")) {
    return <Nhom4FormPage onNavigateHome={() => navigate("/")} prefill={nhom4Prefill} />;
  }
  if (path.startsWith("/import-ranh-thon")) {
    return <ImportRanhThonPage onNavigateHome={() => navigate("/")} />;
  }
  if (path.startsWith("/ban-do-nen")) {
    return <ManageBanDoNenPage onNavigateHome={() => navigate("/")} />;
  }
  return <App onNavigateTools={() => navigate("/tools")} onNavigateNhom4={navigateToNhom4} />;
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);

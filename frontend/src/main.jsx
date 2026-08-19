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
import MplisSyncPage from "./MplisSyncPage.jsx";
import Nhom4FormPage from "./Nhom4FormPage.jsx";
import ImportRanhThonPage from "./ImportRanhThonPage.jsx";

function Root() {
  const [path, setPath] = useState(window.location.pathname);
  const [nhom4Prefill, setNhom4Prefill] = useState(null);

  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
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
        onNavigateMplisSync={() => navigate("/cap-nhat-mplis")}
        onNavigateNhom4={() => navigate("/nhom-4")}
        onNavigateRanhThon={() => navigate("/import-ranh-thon")}
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
  if (path.startsWith("/cap-nhat-mplis")) {
    return <MplisSyncPage onNavigateHome={() => navigate("/")} />;
  }
  if (path.startsWith("/nhom-4")) {
    return <Nhom4FormPage onNavigateHome={() => navigate("/")} prefill={nhom4Prefill} />;
  }
  if (path.startsWith("/import-ranh-thon")) {
    return <ImportRanhThonPage onNavigateHome={() => navigate("/")} />;
  }
  return <App onNavigateTools={() => navigate("/tools")} onNavigateNhom4={navigateToNhom4} />;
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);

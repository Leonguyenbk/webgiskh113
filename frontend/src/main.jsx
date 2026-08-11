import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import "leaflet/dist/leaflet.css";
import "./styles.css";
import App from "./App.jsx";
import ToolsPage from "./ToolsPage.jsx";
import ImportGmlPage from "./ImportGmlPage.jsx";
import ImportSyncPage from "./ImportSyncPage.jsx";
import ManageMbtilesPage from "./ManageMbtilesPage.jsx";
import ManageGcnLinksPage from "./ManageGcnLinksPage.jsx";
import GcnDashboardPage from "./GcnDashboardPage.jsx";
import MplisSyncPage from "./MplisSyncPage.jsx";

function Root() {
  const [path, setPath] = useState(window.location.pathname);

  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = (to) => {
    window.history.pushState({}, "", to);
    setPath(to);
  };

  if (path.startsWith("/tools")) {
    return (
      <ToolsPage
        onNavigateHome={() => navigate("/")}
        onNavigateImport={() => navigate("/import-gml")}
        onNavigateSync={() => navigate("/import-dong-bo")}
        onNavigateMbtiles={() => navigate("/mbtiles")}
        onNavigateGcnLinks={() => navigate("/nguon-gcn")}
        onNavigateGcnDashboard={() => navigate("/thong-ke-gcn")}
        onNavigateMplisSync={() => navigate("/cap-nhat-mplis")}
      />
    );
  }
  if (path.startsWith("/import-gml")) {
    return <ImportGmlPage onNavigateHome={() => navigate("/")} />;
  }
  if (path.startsWith("/import-dong-bo")) {
    return <ImportSyncPage onNavigateHome={() => navigate("/")} />;
  }
  if (path.startsWith("/mbtiles")) {
    return <ManageMbtilesPage onNavigateHome={() => navigate("/")} />;
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
  return <App onNavigateTools={() => navigate("/tools")} />;
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);

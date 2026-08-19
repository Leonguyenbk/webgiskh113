// Điền tên tool + link Google Drive thực tế vào đây.
const TOOLS = [
  {
    name: "Tool Xóa đơn",
    description: "Công cụ Tkinter hỗ trợ xử lý dữ liệu đăng ký đất đai trên MPLIS theo ba chế độ: kiểm tra, kiểm tra rồi xóa và xóa thẳng. Tool tự lấy phiên đăng nhập, đọc danh sách tờ/thửa từ Excel, tra cứu đơn, xuất kết quả định dạng màu, tự lưu sau mỗi 5 thửa, đồng thời có tiến trình, nhật ký và chức năng dừng an toàn.",
    driveUrl: "https://drive.google.com/file/d/1jUBp0VzvoxI8qbKeeTWxcPwwWfdry6qh/view?usp=sharing",
  },
  {
    name: "Tool 2",
    description: "Công cụ Tkinter hỗ trợ xử lý dữ liệu đăng ký đất đai trên MPLIS theo ba chế độ: kiểm tra, kiểm tra rồi xóa và xóa thẳng. Tool tự lấy phiên đăng nhập, đọc danh sách tờ/thửa từ Excel, tra cứu đơn, xuất kết quả định dạng màu, tự lưu sau mỗi 5 thửa, đồng thời có tiến trình, nhật ký và chức năng dừng an toàn.",
    driveUrl: "",
  },
  {
    name: "Tool 3",
    description: "Mô tả ngắn về công dụng của tool này.",
    driveUrl: "",
  },
];

export default function ToolsPage({
  onNavigateHome,
  onNavigateImport,
  onNavigateSync,
  onNavigateGcnLinks,
  onNavigateGcnDashboard,
  onNavigateMplisSync,
  onNavigateNhom4,
  onNavigateRanhThon,
}) {
  const ADMIN_TOOLS = [
    {
      name: "⇪ Nhập GML",
      description: "Nhập file GML thửa đất vào Supabase (bảng thua_dat).",
      onNavigate: onNavigateImport,
    },
    {
      name: "⇪ Nhập đồng bộ",
      description: "Nhập file CSV/Excel dữ liệu đồng bộ (bảng dong_bo_du_lieu).",
      onNavigate: onNavigateSync,
    },
    {
      name: "⇪ Nhập đường link",
      description: "Quản lý danh sách link Google Sheet cho công cụ đồng bộ GCN.",
      onNavigate: onNavigateGcnLinks,
    },
    {
      name: "📊 Thống kê thu thập",
      description: "Tỉ lệ thửa đất đã nhập biểu GCN theo từng xã/phường.",
      onNavigate: onNavigateGcnDashboard,
    },
    {
      name: "🔄 Cập nhật MPLIS",
      description: "Lấy trạng thái thửa đất từ MPLIS, cập nhật vào dong_bo_du_lieu (1 thửa hoặc cả xã).",
      onNavigate: onNavigateMplisSync,
    },
    {
      name: "📝 Nhập biểu Nhóm 4",
      description: "Nhập biểu mẫu thu thập dữ liệu thửa đất (Hộ gia đình/Tổ chức), lưu vào Supabase, hồ sơ quét lên Google Drive.",
      onNavigate: onNavigateNhom4,
    },
    {
      name: "🗺️ Nhập ranh giới thôn",
      description: "Nhập file Shapefile (.zip) ranh giới thôn vào Supabase, hiển thị dạng viền trên bản đồ.",
      onNavigate: onNavigateRanhThon,
    },
  ];

  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Công cụ</h1>
          <p>Tải công cụ ngoài và các trang nhập/quản lý dữ liệu</p>
        </div>
        <a
          className="backLink"
          href="/"
          onClick={(event) => {
            event.preventDefault();
            onNavigateHome?.();
          }}
        >
          ← Về bản đồ
        </a>
      </header>

      <section className="toolsGrid">
        {ADMIN_TOOLS.map((tool) => (
          <article className="toolCard" key={tool.name}>
            <h2>{tool.name}</h2>
            <p>{tool.description}</p>
            <a
              className="downloadButton"
              href="#"
              onClick={(event) => {
                event.preventDefault();
                tool.onNavigate?.();
              }}
            >
              Mở
            </a>
          </article>
        ))}

        {TOOLS.map((tool) => (
          <article className="toolCard" key={tool.name}>
            <h2>{tool.name}</h2>
            <p>{tool.description}</p>
            {tool.driveUrl ? (
              <a
                className="downloadButton"
                href={tool.driveUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                ⬇ Tải về (Google Drive)
              </a>
            ) : (
              <span className="downloadButton disabled">Chưa có link</span>
            )}
          </article>
        ))}
      </section>
    </main>
  );
}

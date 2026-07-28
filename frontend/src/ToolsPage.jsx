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

export default function ToolsPage({ onNavigateHome }) {
  return (
    <main className="toolsShell">
      <header className="topbar">
        <div className="brandMark">GIS</div>
        <div>
          <h1>Tải công cụ</h1>
          <p>Danh sách tools và link Google Drive</p>
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

// Hiển thị trạng thái job: queued | running | done | error. `step` là chữ backend trả về.
export default function StatusBanner({ status, step, error }) {
  if (status === "error") return <div className="banner banner-loi">Lỗi: {error}</div>;
  if (status === "done") return <div className="banner banner-xong">Hoàn tất</div>;
  const chu = status === "queued" ? "Đang chờ tới lượt..." : `Đang chạy: ${step || "..."}`;
  return <div className="banner">{chu}</div>;
}

import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import CandidateCard from "../components/CandidateCard.jsx";

export default function ResultsPage() {
  const { state } = useLocation();
  const nav = useNavigate();
  if (!state?.ket_qua) return <Navigate to="/" replace />;   // vào thẳng /results (hoặc tải lại trang) thì về trang đầu

  return (
    <div className="trang">
      <h2>Kết quả tra cứu</h2>
      {state.ket_qua.length === 0 && <p>Không tìm thấy tên công ty nào trong đoạn văn.</p>}
      {state.ket_qua.map((kq) => (
        <section key={kq.ten} className="khoi">
          <h3>"{kq.ten}"</h3>
          {kq.trang_thai === "duy_nhat" && (
            <>
              <CandidateCard ung_vien={kq.ung_vien[0]} />
              <button onClick={() => nav(`/report/${kq.ung_vien[0].ticker}`)}>Chạy screening {kq.ung_vien[0].ticker}</button>
            </>
          )}
          {kq.trang_thai === "can_xac_nhan" && (
            <>
              <p>Chưa chắc chắn, cần bạn xác nhận công ty ({kq.ung_vien.length} ứng viên).</p>
              <button onClick={() => nav("/confirm", { state: { ket_qua: kq } })}>Chọn công ty</button>
            </>
          )}
          {kq.trang_thai === "khong_co" && (
            <p>{kq.ghi_chu ? kq.ghi_chu + "." : "Không có trong danh mục (VN100)."} Không có gì để screening.</p>
          )}
        </section>
      ))}
      <Link to="/">← Tra cứu khác</Link>
    </div>
  );
}

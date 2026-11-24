import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import CandidateCard from "../components/CandidateCard.jsx";

export default function ConfirmPage() {
  const { state } = useLocation();
  const nav = useNavigate();
  const [chon, setChon] = useState(null);
  if (!state?.ket_qua) return <Navigate to="/" replace />;
  const kq = state.ket_qua;

  return (
    <div className="trang">
      <h2>Xác nhận công ty cho "{kq.ten}"</h2>
      {kq.ung_vien.map((u) => (
        <CandidateCard key={u.ticker} ung_vien={u} duoc_chon={chon === u.ticker} onChon={() => setChon(u.ticker)} />
      ))}
      <button disabled={!chon} onClick={() => nav(`/report/${chon}`)}>Xác nhận và chạy screening</button>
      <Link to="/">← Hủy</Link>
    </div>
  );
}

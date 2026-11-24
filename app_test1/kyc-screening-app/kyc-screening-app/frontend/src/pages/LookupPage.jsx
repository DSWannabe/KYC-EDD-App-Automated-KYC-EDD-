import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { lookup } from "../api/client.js";

export default function LookupPage() {
  const [doan, setDoan] = useState("");
  const [ten, setTen] = useState("");
  const [dangTim, setDangTim] = useState(false);
  const [loi, setLoi] = useState("");
  const nav = useNavigate();

  async function gui(e) {
    e.preventDefault();
    setLoi("");
    setDangTim(true);
    try {
      const ket_qua = await lookup(doan, ten.trim());
      nav("/results", { state: { ket_qua } });
    } catch (err) {
      setLoi(err.message);
    } finally {
      setDangTim(false);
    }
  }

  return (
    <form onSubmit={gui} className="trang">
      <h2>Tra cứu công ty</h2>
      <label>Đoạn văn</label>
      <textarea rows={8} value={doan} onChange={(e) => setDoan(e.target.value)} placeholder="Dán đoạn văn có nhắc tới công ty..." />
      <label>Tên công ty (bỏ trống để hệ thống tự tìm trong đoạn)</label>
      <input value={ten} onChange={(e) => setTen(e.target.value)} placeholder="Ví dụ: ACB" />
      <button disabled={dangTim || !doan.trim()}>{dangTim ? "Đang tra cứu..." : "Tra cứu"}</button>
      {loi && <div className="banner banner-loi">{loi}</div>}
    </form>
  );
}

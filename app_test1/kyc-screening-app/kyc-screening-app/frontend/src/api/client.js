// Gọi backend. Đổi địa chỉ bằng VITE_API_URL trong file .env
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function goi(duong_dan, tuy_chon) {
  const res = await fetch(BASE + duong_dan, tuy_chon);
  if (!res.ok) {
    let loi = res.statusText;
    try {
      const d = await res.json();
      loi = typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail);
    } catch {}
    throw new Error(loi);
  }
  return res.json();
}

const post = (duong_dan, body) =>
  goi(duong_dan, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

// Đoạn văn (+ tên) -> danh sách kết quả, mỗi tên một phần tử
export const lookup = (doan, ten) => post("/lookup", { doan, ten: ten || null }).then((d) => d.ket_qua);

// Bắt đầu screening cho ticker đã xác nhận -> job_id
export const batDauScreening = (ticker) => post("/screening", { ticker }).then((d) => d.job_id);

export const trangThaiJob = (job_id) => goi(`/screening/${job_id}`);

export const getReport = (run_id) => goi(`/reports/${run_id}`);

// Tên hàm confirm theo thiết kế: người dùng chọn ticker thì bắt đầu screening
export const confirm = batDauScreening;

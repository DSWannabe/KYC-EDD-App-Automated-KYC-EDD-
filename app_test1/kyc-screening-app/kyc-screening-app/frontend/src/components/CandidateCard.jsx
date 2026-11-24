import ScoreBar from "./ScoreBar.jsx";

// Một ứng viên công ty. Truyền onChon thì card bấm được.
export default function CandidateCard({ ung_vien, duoc_chon, onChon }) {
  const lop = "card" + (duoc_chon ? " card-chon" : "") + (onChon ? " card-bam" : "");
  return (
    <div className={lop} onClick={onChon}>
      <div className="card-tren">
        <strong>{ung_vien.ticker}</strong>
        <span>{ung_vien.ten_cong_ty}</span>
      </div>
      <ScoreBar diem={ung_vien.diem} />
    </div>
  );
}

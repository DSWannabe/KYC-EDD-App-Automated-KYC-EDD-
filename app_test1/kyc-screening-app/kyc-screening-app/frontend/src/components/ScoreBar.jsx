// Thanh hiển thị điểm 0-1
export default function ScoreBar({ diem }) {
  return (
    <div className="scorebar" title={`Điểm ${diem.toFixed(2)}`}>
      <div className="scorebar-fill" style={{ width: `${Math.round(diem * 100)}%` }} />
      <span>{diem.toFixed(2)}</span>
    </div>
  );
}

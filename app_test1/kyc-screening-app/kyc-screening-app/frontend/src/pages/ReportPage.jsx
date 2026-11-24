import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { batDauScreening, getReport, trangThaiJob } from "../api/client.js";
import StatusBanner from "../components/StatusBanner.jsx";

const CHU_KY_MS = 2000;

export default function ReportPage() {
  const { ticker } = useParams();
  const [job, setJob] = useState(null);       // trạng thái job mới nhất
  const [baoCao, setBaoCao] = useState(null);
  const [loi, setLoi] = useState("");
  const daChay = useRef(null);                // tránh gọi POST hai lần khi React StrictMode chạy effect đôi

  useEffect(() => {
    if (daChay.current === ticker) return;
    daChay.current = ticker;
    setJob(null); setBaoCao(null); setLoi("");

    let dung = false;
    async function chay() {
      try {
        const job_id = await batDauScreening(ticker);
        while (!dung) {
          const j = await trangThaiJob(job_id);
          setJob(j);
          if (j.status === "error") return;
          if (j.status === "done") {
            setBaoCao(await getReport(j.run_id));
            return;
          }
          await new Promise((r) => setTimeout(r, CHU_KY_MS));
        }
      } catch (err) {
        setLoi(err.message);
      }
    }
    chay();
    return () => { dung = true; };
  }, [ticker]);

  return (
    <div className="trang">
      <h2>Screening {ticker}</h2>
      {loi && <div className="banner banner-loi">{loi}</div>}
      {!loi && <StatusBanner status={job?.status || "queued"} step={job?.step} error={job?.error} />}

      {baoCao && (
        <>
          <section className="khoi"><ReactMarkdown>{baoCao.report_md}</ReactMarkdown></section>
          <h3>Top {job.top.length} bài liên quan nhất</h3>
          <table>
            <thead><tr><th>#</th><th>Tiêu đề</th><th>Ngày</th><th>Điểm</th></tr></thead>
            <tbody>
              {job.top.map((b) => (
                <tr key={b.article_id}>
                  <td>{b.rank}</td>
                  <td>{b.source_url ? <a href={b.source_url} target="_blank" rel="noreferrer">{b.title}</a> : b.title}</td>
                  <td>{b.published_at}</td>
                  <td>{b.final?.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      <Link to="/">← Tra cứu khác</Link>
    </div>
  );
}

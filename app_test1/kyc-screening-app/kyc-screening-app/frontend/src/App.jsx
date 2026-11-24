import { Route, Routes } from "react-router-dom";
import Header from "./components/Header.jsx";
import LookupPage from "./pages/LookupPage.jsx";
import ResultsPage from "./pages/ResultsPage.jsx";
import ConfirmPage from "./pages/ConfirmPage.jsx";
import ReportPage from "./pages/ReportPage.jsx";

export default function App() {
  return (
    <>
      <Header />
      <main>
        <Routes>
          <Route path="/" element={<LookupPage />} />
          <Route path="/results" element={<ResultsPage />} />
          <Route path="/confirm" element={<ConfirmPage />} />
          <Route path="/report/:ticker" element={<ReportPage />} />
        </Routes>
      </main>
    </>
  );
}

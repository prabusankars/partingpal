import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AdminLayout from "./pages/AdminLayout";
import Dashboard from "./pages/Dashboard";
import InterviewChat from "./pages/InterviewChat";
import InterviewDetail from "./pages/InterviewDetail";
import Login from "./pages/Login";

// Charts are heavy, so the reports page loads on demand.
const Reports = lazy(() => import("./pages/Reports"));

export default function App() {
  return (
    <Routes>
      <Route path="/interview/:token" element={<InterviewChat />} />
      <Route path="/login" element={<Login />} />
      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="interviews/:id" element={<InterviewDetail />} />
        <Route
          path="reports"
          element={
            <Suspense fallback={<p className="muted">Loading…</p>}>
              <Reports />
            </Suspense>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/admin" replace />} />
    </Routes>
  );
}

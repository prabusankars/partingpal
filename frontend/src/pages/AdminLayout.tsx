import { useEffect, useState } from "react";
import { Navigate, NavLink, Outlet, useNavigate } from "react-router-dom";
import { ApiError } from "../api";
import { useAuth } from "../auth";
import Brand from "../components/Brand";
import ThemeToggle from "../components/ThemeToggle";

export default function AdminLayout() {
  const { api, email, signOut } = useAuth();
  const navigate = useNavigate();
  const [verified, setVerified] = useState(false);

  // Confirm the account is on the server's allowlist before showing any HR data.
  useEffect(() => {
    if (!api) return;
    let active = true;
    api
      .me()
      .then(() => active && setVerified(true))
      .catch((err: unknown) => {
        if (!active) return;
        signOut();
        const message = err instanceof ApiError ? err.message : "Sign-in failed";
        navigate("/login", { replace: true, state: { error: message } });
      });
    return () => {
      active = false;
    };
  }, [api, navigate, signOut]);

  if (!api) return <Navigate to="/login" replace />;
  if (!verified) return <main className="center-page muted">Checking access…</main>;

  return (
    <div className="admin">
      <header className="topbar">
        <Brand />
        <nav>
          <NavLink to="/admin" end>
            Interviews
          </NavLink>
          <NavLink to="/admin/reports">Reports</NavLink>
        </nav>
        <span className="spacer" />
        <span className="muted small">{email}</span>
        <ThemeToggle />
        <button className="ghost" onClick={signOut}>
          Sign out
        </button>
      </header>
      <main className="admin-main">
        <Outlet />
      </main>
    </div>
  );
}

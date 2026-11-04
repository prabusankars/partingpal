import { useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { GoogleLogin } from "@react-oauth/google";
import { DEV_MODE, useAuth } from "../auth";
import Brand from "../components/Brand";
import ThemeToggle from "../components/ThemeToggle";

export default function Login() {
  const { token, signIn } = useAuth();
  const location = useLocation();
  const [error, setError] = useState<string | null>((location.state as { error?: string } | null)?.error ?? null);

  if (token) return <Navigate to="/admin" replace />;

  return (
    <main className="center-page">
      <div className="card login-card">
        <Brand as="h1" />
        <p className="muted">HR dashboard for exit interviews. Sign in with your work Google account.</p>
        {error && <p className="error">{error}</p>}
        {DEV_MODE ? (
          <>
            <p className="notice">No Google client id is configured. Development mode only.</p>
            <button className="primary" onClick={() => signIn("dev")}>
              Continue in development mode
            </button>
          </>
        ) : (
          <GoogleLogin
            onSuccess={(response) => (response.credential ? signIn(response.credential) : setError("Sign-in failed"))}
            onError={() => setError("Google sign-in failed. Please try again.")}
          />
        )}
        <ThemeToggle />
      </div>
    </main>
  );
}

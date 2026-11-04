import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { adminApi, ApiError, type AdminApi } from "./api";

export const GOOGLE_CLIENT_ID: string = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? "";
// Without a client id the backend must run with AUTH_DISABLED=true (local development only).
export const DEV_MODE = !GOOGLE_CLIENT_ID;

const STORAGE_KEY = "partingpal.idToken";

interface AuthContextValue {
  token: string | null;
  email: string | null;
  api: AdminApi | null;
  signIn: (token: string) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function decode(token: string): { email?: string; exp?: number } {
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(payload));
  } catch {
    return {};
  }
}

function isUsable(token: string | null): token is string {
  if (!token) return false;
  if (DEV_MODE) return true;
  const { exp } = decode(token);
  return typeof exp === "number" && exp * 1000 > Date.now() + 30_000;
}

function readStored(): string | null {
  try {
    const token = sessionStorage.getItem(STORAGE_KEY);
    return isUsable(token) ? token : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(readStored);

  const signIn = useCallback((value: string) => {
    try {
      sessionStorage.setItem(STORAGE_KEY, value);
    } catch {
      /* storage unavailable: keep the session in memory only */
    }
    setToken(value);
  }, []);

  const signOut = useCallback(() => {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
    setToken(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      email: token ? (DEV_MODE ? "dev@localhost" : decode(token).email ?? null) : null,
      api: token ? adminApi(token) : null,
      signIn,
      signOut,
    }),
    [token, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}

/** Turns an error into a message, signing out when the Google token has expired. */
export function useErrorMessage(): (err: unknown) => string {
  const { signOut } = useAuth();
  return useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.status === 401) signOut();
      return err instanceof Error ? err.message : "Something went wrong";
    },
    [signOut],
  );
}

/** Admin API for pages rendered inside AdminLayout. */
export function useAdmin(): AdminApi {
  const { api } = useAuth();
  if (!api) throw new Error("Not signed in");
  return api;
}

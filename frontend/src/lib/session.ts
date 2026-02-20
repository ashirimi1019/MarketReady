"use client";

import { useLocalStorage } from "@/lib/useLocalStorage";

export function useSession() {
  const [storedUsername, setStoredUsername] = useLocalStorage("mp_username", "");
  const [authToken, setAuthToken] = useLocalStorage("mp_auth_token", "");
  const [refreshToken, setRefreshToken] = useLocalStorage("mp_refresh_token", "");
  const fallbackUsername =
    typeof window !== "undefined"
      ? (window.localStorage.getItem("mp_username") ?? "")
      : "";
  const fallbackAuthToken =
    typeof window !== "undefined"
      ? (window.localStorage.getItem("mp_auth_token") ?? "")
      : "";

  const username = storedUsername || fallbackUsername;
  const isLoggedIn = Boolean((storedUsername || fallbackUsername) && (authToken || fallbackAuthToken));

  const login = (nextUsername: string, token: string, nextRefreshToken: string) => {
    setStoredUsername(nextUsername);
    setAuthToken(token);
    setRefreshToken(nextRefreshToken);
  };

  const logout = () => {
    setStoredUsername("");
    setAuthToken("");
    setRefreshToken("");
  };

  return { username, isLoggedIn, login, logout, authToken, refreshToken };
}

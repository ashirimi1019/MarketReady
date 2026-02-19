"use client";

import { useLocalStorage } from "@/lib/useLocalStorage";

export function useSession() {
  const [storedUsername, setStoredUsername] = useLocalStorage("mp_username", "");
  const [authToken, setAuthToken] = useLocalStorage("mp_auth_token", "");
  const [refreshToken, setRefreshToken] = useLocalStorage("mp_refresh_token", "");
  const username = storedUsername;
  const isLoggedIn = Boolean(storedUsername && authToken);

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

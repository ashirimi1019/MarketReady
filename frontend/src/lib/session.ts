"use client";

import { useEffect, useState } from "react";
import { useLocalStorage } from "@/lib/useLocalStorage";

export function useSession() {
  const [storedUsername, setStoredUsername] = useLocalStorage(
    "mp_username",
    ""
  );
  const [authToken, setAuthToken] = useLocalStorage("mp_auth_token", "");
  const [refreshToken, setRefreshToken] = useLocalStorage("mp_refresh_token", "");
  const [loggedInFlag, setLoggedInFlag] = useLocalStorage(
    "mp_logged_in",
    "false"
  );
  const [username, setUsername] = useState(storedUsername);
  const [isLoggedIn, setIsLoggedIn] = useState(Boolean(storedUsername));

  useEffect(() => {
    setUsername(storedUsername);
  }, [storedUsername]);

  useEffect(() => {
    if (storedUsername && authToken && refreshToken && loggedInFlag !== "true") {
      setLoggedInFlag("true");
    }
    if ((!storedUsername || !authToken || !refreshToken) && loggedInFlag !== "false") {
      setLoggedInFlag("false");
    }
    setIsLoggedIn(Boolean(storedUsername && authToken && refreshToken));
  }, [loggedInFlag, storedUsername, authToken, refreshToken, setLoggedInFlag]);

  const login = (nextUsername: string, token: string, nextRefreshToken: string) => {
    setStoredUsername(nextUsername);
    setAuthToken(token);
    setRefreshToken(nextRefreshToken);
    setLoggedInFlag("true");
  };

  const logout = () => {
    setStoredUsername("");
    setAuthToken("");
    setRefreshToken("");
    setLoggedInFlag("false");
  };

  return { username, isLoggedIn, login, logout, authToken, refreshToken };
}

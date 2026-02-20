"use client";

import { useEffect, useState } from "react";

export function useLocalStorage(key: string, initialValue: string) {
  const [value, setValue] = useState(() => {
    if (typeof window === "undefined") {
      return initialValue;
    }
    try {
      return window.localStorage.getItem(key) ?? initialValue;
    } catch {
      return initialValue;
    }
  });

  useEffect(() => {
    if (typeof window === "undefined") return;

    const onStorage = (event: StorageEvent) => {
      if (event.key !== key) return;
      setValue(event.newValue ?? initialValue);
    };

    const onLocalStorageSync = (event: Event) => {
      const custom = event as CustomEvent<{ key: string; value: string }>;
      if (!custom.detail || custom.detail.key !== key) return;
      setValue(custom.detail.value ?? initialValue);
    };

    window.addEventListener("storage", onStorage);
    window.addEventListener("mp-local-storage", onLocalStorageSync);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("mp-local-storage", onLocalStorageSync);
    };
  }, [key, initialValue]);

  const setStoredValue = (nextValue: string) => {
    setValue(nextValue);
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(key, nextValue);
      window.dispatchEvent(
        new CustomEvent("mp-local-storage", {
          detail: { key, value: nextValue },
        })
      );
    } catch {
      // ignore write failures
    }
  };

  return [value, setStoredValue] as const;
}

import { useEffect, useState } from "react";

const DARK_MODE_KEY = "darkMode";
const DARK_MODE_CLASS = "is-dark";

const getInitialDarkMode = (): boolean => {
  // Check localStorage first
  const stored = localStorage.getItem(DARK_MODE_KEY);
  if (stored !== null) {
    return stored === "true";
  }

  // Fall back to user's system preference
  return (
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
};

const useDarkMode = (): [boolean, () => void] => {
  const [isDarkMode, setIsDarkMode] = useState<boolean>(getInitialDarkMode());

  useEffect(() => {
    // Apply or remove the dark mode class on the body
    if (isDarkMode) {
      document.body.classList.add(DARK_MODE_CLASS);
    } else {
      document.body.classList.remove(DARK_MODE_CLASS);
    }

    // Persist to localStorage
    localStorage.setItem(DARK_MODE_KEY, String(isDarkMode));
  }, [isDarkMode]);

  const toggleDarkMode = () => {
    setIsDarkMode((prev) => !prev);
  };

  return [isDarkMode, toggleDarkMode];
};

export default useDarkMode;

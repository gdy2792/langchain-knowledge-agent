import { useState } from "react";
import { Chat } from "./Chat";
import { Login } from "./Login";
import "./App.css";

const TOKEN_STORAGE_KEY = "access_token";

function App() {
  const [accessToken, setAccessToken] = useState<string | null>(
    localStorage.getItem(TOKEN_STORAGE_KEY),
  );
  // Shown on the login screen after an automatic logout, e.g. an expired token.
  const [notice, setNotice] = useState<string | null>(null);

  function handleLogin(token: string) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
    setAccessToken(token);
    setNotice(null);
  }

  function handleLogout(message?: string) {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setAccessToken(null);
    setNotice(message ?? null);
  }

  return accessToken ? (
    <Chat accessToken={accessToken} onLogout={handleLogout} />
  ) : (
    <Login onLogin={handleLogin} notice={notice} />
  );
}

export default App;

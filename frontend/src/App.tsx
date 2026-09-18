import { useState } from "react";
import { Chat } from "./Chat";
import { Login } from "./Login";
import "./App.css";

const TOKEN_STORAGE_KEY = "access_token";

function App() {
  const [accessToken, setAccessToken] = useState<string | null>(
    localStorage.getItem(TOKEN_STORAGE_KEY),
  );

  function handleLogin(token: string) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
    setAccessToken(token);
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setAccessToken(null);
  }

  return accessToken ? (
    <Chat accessToken={accessToken} onLogout={handleLogout} />
  ) : (
    <Login onLogin={handleLogin} />
  );
}

export default App;

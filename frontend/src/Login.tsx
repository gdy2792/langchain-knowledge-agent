import { useState } from "react";
import { login } from "./api";
import { Brand } from "./Brand";

export function Login({
  onLogin,
  notice,
}: {
  onLogin: (token: string) => void;
  notice: string | null;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const token = await login(email, password);
      onLogin(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-backdrop">
      <form className="login-form" onSubmit={handleSubmit}>
        <Brand className="login-mascot" />
        <h1>Welcome to FSSA Agents</h1>
        {notice && <p className="notice">{notice}</p>}
        <label>
          <span>Email</span>
          <input
            type="email"
            placeholder="Enter email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label>
          <span>Password</span>
          <input
            type="password"
            placeholder="Enter password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="primary-btn" disabled={busy} type="submit">
          {busy ? "Logging in…" : "Log in"}
        </button>
      </form>
    </div>
  );
}

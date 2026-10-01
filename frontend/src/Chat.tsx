import { useEffect, useRef, useState } from "react";
import { Brand } from "./Brand";
import { SessionExpiredError, streamChat, type ChatEvent } from "./api";

type LogItem =
  | { kind: "user"; text: string }
  | { kind: "answer"; text: string }
  | { kind: "event"; event: ChatEvent };

// The backend has no "list my conversations" endpoint, so the sidebar only
// knows about chats started in this browser tab — a refresh clears it.
type ChatSession = { id: string; title: string; log: LogItem[] };

// Each one exercises a different tool, so new users see what the agent
// can do: finance news (twice), the internal knowledge base, chat history.
const QUICK_ACTIONS = [
  "Latest news on Elevance Health (ELV)",
  "Summarize this week's health insurance industry news",
  "What's in our internal project notes?",
  "What did I ask about last time?",
];

function newSession(): ChatSession {
  return { id: crypto.randomUUID(), title: "New chat", log: [] };
}

// The access token is a JWT whose middle section is base64 JSON holding the
// user's email — enough to show initials, no request needed.
function emailFromToken(token: string): string {
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return (JSON.parse(atob(payload)).email as string) ?? "";
  } catch {
    return "";
  }
}

export function Chat({
  accessToken,
  onLogout,
}: {
  accessToken: string;
  onLogout: (notice?: string) => void;
}) {
  const [sessions, setSessions] = useState<ChatSession[]>(() => [newSession()]);
  const [activeId, setActiveId] = useState(() => sessions[0].id);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const mainRef = useRef<HTMLElement>(null);

  const active = sessions.find((s) => s.id === activeId) ?? sessions[0];
  const email = emailFromToken(accessToken);
  const initials = email ? email.slice(0, 2).toUpperCase() : "--";
  const started = active.log.length > 0;

  useEffect(() => {
    const main = mainRef.current;
    if (main) main.scrollTop = main.scrollHeight;
  }, [active.log.length, sending]);

  // Each chat's id doubles as its backend thread_id, so the agent keeps
  // separate memory per chat.
  function appendTo(id: string, item: LogItem) {
    setSessions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, log: [...s.log, item] } : s)),
    );
  }

  function newChat() {
    if (!started) return;
    const s = newSession();
    setSessions((prev) => [s, ...prev]);
    setActiveId(s.id);
    setInput("");
  }

  async function send(text?: string) {
    const message = (text ?? input).trim();
    if (!message || sending) return;
    const threadId = active.id;
    setInput("");
    setSending(true);
    setSessions((prev) =>
      prev.map((s) =>
        s.id === threadId
          ? {
              ...s,
              title: s.log.length === 0 ? message : s.title,
              log: [...s.log, { kind: "user", text: message }],
            }
          : s,
      ),
    );

    // Tracks whether the stream produced anything worth showing — if the
    // backend's connection drops mid-reply, the loop below just ends
    // quietly, and without this the user would see nothing at all.
    let gotAnswerOrWarning = false;
    try {
      for await (const event of streamChat(accessToken, message, threadId)) {
        if (event.type === "final_answer" || event.type === "warning") {
          gotAnswerOrWarning = true;
        }
        if (event.type === "final_answer") {
          appendTo(threadId, { kind: "answer", text: event.text });
        } else {
          appendTo(threadId, { kind: "event", event });
        }
      }
      if (!gotAnswerOrWarning) {
        appendTo(threadId, {
          kind: "event",
          event: {
            type: "warning",
            message:
              "The server ended its reply without an answer. Check the backend logs for the error.",
          },
        });
      }
    } catch (err) {
      if (err instanceof SessionExpiredError) {
        onLogout("Your session expired — please log in again.");
        return;
      }
      appendTo(threadId, {
        kind: "event",
        event: { type: "warning", message: String(err) },
      });
    } finally {
      setSending(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="layout">
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        {sidebarOpen ? (
          <button
            className="icon-btn close-chevron"
            onClick={() => setSidebarOpen(false)}
            title="Close menu"
            aria-label="Close menu"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="m18.75 4.5-7.5 7.5 7.5 7.5m-6-15L5.25 12l7.5 7.5" />
            </svg>
          </button>
        ) : (
          <button
            className="icon-btn toggle-btn"
            onClick={() => setSidebarOpen(true)}
            title="Open menu"
            aria-label="Open menu"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 16L12 6L20 16" />
            </svg>
          </button>
        )}
        <button
          className="icon-btn pencil-btn"
          onClick={newChat}
          disabled={sending}
          title="New chat"
          aria-label="New chat"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" />
          </svg>
        </button>

        {sidebarOpen && (
          <div className="chat-list-wrap">
            <span className="chat-list-heading">chats</span>
            <div className="chat-list">
              {sessions.map((s) => (
                <button
                  key={s.id}
                  className={`chat-item ${s.id === activeId ? "active" : ""}`}
                  onClick={() => setActiveId(s.id)}
                  title={s.title}
                >
                  {s.title}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="user-section">
          <button
            className="avatar"
            onClick={() => {
              if (window.confirm("Log out?")) onLogout();
            }}
            title={`Logged in as ${email} – click to log out`}
          >
            {initials}
          </button>
          {sidebarOpen && <span className="user-name">{email}</span>}
        </div>
      </aside>

      <div className="pane">
        <main className="main" ref={mainRef}>
          <div className="main-inner">
            <section className="stream">
              {active.log.map((item, i) => (
                <LogLine key={i} item={item} />
              ))}
              {sending && (
                <div className="bubble-row start">
                  <div className="bubble answer pending">thinking…</div>
                </div>
              )}
            </section>

            {!started && (
              <>
                <Brand className="mascot" />
                <div className="init-card">
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={onKeyDown}
                    placeholder="Ask FSSA Agents"
                    disabled={sending}
                    autoFocus
                  />
                  <div className="init-actions">
                    <div className="quick-actions">
                      {QUICK_ACTIONS.map((q) => (
                        <button
                          key={q}
                          className="pill"
                          onClick={() => send(q)}
                          disabled={sending}
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                    <SendButton onClick={() => send()} disabled={sending} />
                  </div>
                </div>
              </>
            )}
          </div>
        </main>

        {started && (
          <footer className="footer">
            <div className="footer-card">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Ask FSSA Agents"
                disabled={sending}
                autoFocus
              />
              <SendButton onClick={() => send()} disabled={sending} />
            </div>
          </footer>
        )}
      </div>
    </div>
  );
}

function SendButton({
  onClick,
  disabled,
}: {
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <button className="send-btn" onClick={onClick} disabled={disabled} aria-label="Send">
      {disabled ? (
        <span className="spinner" />
      ) : (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 19.5V4.5m0 0l-6 6m6-6l6 6" />
        </svg>
      )}
    </button>
  );
}

function LogLine({ item }: { item: LogItem }) {
  if (item.kind === "user") {
    return (
      <div className="bubble-row end">
        <div className="bubble user">{item.text}</div>
      </div>
    );
  }
  if (item.kind === "answer") {
    return (
      <div className="bubble-row start">
        <div className="bubble answer">{item.text}</div>
      </div>
    );
  }

  const { event } = item;
  switch (event.type) {
    case "memory_recalled":
      return <p className="trace">🧠 recalled: {event.context}</p>;
    case "tool_call":
      return (
        <p className="trace">
          🔧 calling {event.name}({JSON.stringify(event.args)})
        </p>
      );
    case "tool_result":
      return (
        <p className="trace">
          ✅ {event.name} → {event.content}
        </p>
      );
    case "warning":
      return <p className="trace warning">⚠️ {event.message}</p>;
  }
}

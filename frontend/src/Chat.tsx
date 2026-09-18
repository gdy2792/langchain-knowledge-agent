import { useState } from "react";
import { streamChat, type ChatEvent } from "./api";

type LogItem =
  | { kind: "user"; text: string }
  | { kind: "answer"; text: string }
  | { kind: "event"; event: ChatEvent };

export function Chat({
  accessToken,
  onLogout,
}: {
  accessToken: string;
  onLogout: () => void;
}) {
  const [log, setLog] = useState<LogItem[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  async function send() {
    const message = input.trim();
    if (!message || sending) return;
    setInput("");
    setSending(true);
    setLog((prev) => [...prev, { kind: "user", text: message }]);

    try {
      for await (const event of streamChat(accessToken, message)) {
        if (event.type === "final_answer") {
          setLog((prev) => [...prev, { kind: "answer", text: event.text }]);
        } else {
          setLog((prev) => [...prev, { kind: "event", event }]);
        }
      }
    } catch (err) {
      setLog((prev) => [
        ...prev,
        { kind: "event", event: { type: "warning", message: String(err) } },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="chat">
      <div className="chat-header">
        <span>Knowledge Agent</span>
        <button className="logout" onClick={onLogout}>
          Log out
        </button>
      </div>
      <div className="log">
        {log.map((item, i) => (
          <LogLine key={i} item={item} />
        ))}
        {sending && <p className="pending">thinking…</p>}
      </div>
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask something…"
          disabled={sending}
        />
        <button type="submit" disabled={sending}>
          Send
        </button>
      </form>
    </div>
  );
}

function LogLine({ item }: { item: LogItem }) {
  if (item.kind === "user") {
    return <p className="line user">{item.text}</p>;
  }
  if (item.kind === "answer") {
    return <p className="line answer">{item.text}</p>;
  }

  const { event } = item;
  switch (event.type) {
    case "memory_recalled":
      return <p className="line trace memory">🧠 recalled: {event.context}</p>;
    case "tool_call":
      return (
        <p className="line trace tool">
          🔧 calling {event.name}({JSON.stringify(event.args)})
        </p>
      );
    case "tool_result":
      return (
        <p className="line trace tool">
          ✅ {event.name} → {event.content}
        </p>
      );
    case "warning":
      return <p className="line trace warning">⚠️ {event.message}</p>;
  }
}

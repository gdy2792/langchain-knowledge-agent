// Talks to the Phase 5/6 FastAPI backend. Login is a plain JSON request —
// there is no signup endpoint at all (single-user app; accounts are created
// directly in the Supabase dashboard). Chat is different because the
// backend streams its answer as Server-Sent Events instead of one
// response — `fetch` doesn't parse SSE for us the way the browser's
// built-in `EventSource` does, but `EventSource` can't send the
// Authorization header or a POST body, so we read the raw response stream
// ourselves and split it on SSE's blank-line event separator.

const API_URL = import.meta.env.VITE_API_URL as string;

export type ChatEvent =
  | { type: "memory_recalled"; context: string }
  | { type: "tool_call"; name: string; args: Record<string, unknown> }
  | { type: "tool_result"; name: string; content: string }
  | { type: "final_answer"; text: string }
  | { type: "warning"; message: string };

export async function login(email: string, password: string): Promise<string> {
  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    throw new Error(`Login failed: ${await response.text()}`);
  }
  const data = await response.json();
  return data.access_token as string;
}

export async function* streamChat(
  accessToken: string,
  message: string,
): AsyncGenerator<ChatEvent> {
  const response = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({ message }),
  });
  if (!response.ok || !response.body) {
    throw new Error(`Chat request failed: ${await response.text()}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by a blank line ("\n\n"); each event's
    // payload is on a line starting with "data: ".
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const rawEvent of events) {
      const line = rawEvent.trim();
      if (line.startsWith("data: ")) {
        yield JSON.parse(line.slice("data: ".length)) as ChatEvent;
      }
    }
  }
}

import { Component, type ReactNode } from "react";

// Without this, any render-time exception (like the "Objects are not valid
// as a React child" bug from a malformed tool result) silently unmounts the
// whole app to a blank page with no visible clue why. This shows the error
// instead — React only supports catching render errors via a class
// component's lifecycle methods, there's no hook equivalent.
export class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: "2rem", fontFamily: "monospace" }}>
          <h2>Something crashed</h2>
          <pre style={{ whiteSpace: "pre-wrap" }}>{this.state.error.message}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

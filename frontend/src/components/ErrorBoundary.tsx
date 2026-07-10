import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("REMY UI crashed:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-full items-center justify-center bg-surface-0 p-6 text-center">
          <div className="max-w-sm">
            <h2 className="mb-2 text-lg font-semibold text-ink">
              Something went wrong
            </h2>
            <p className="mb-4 text-sm text-ink-muted">
              The interface hit an unexpected error. Your REMY backend is
              unaffected.
            </p>
            <button
              onClick={() => location.reload()}
              className="rounded-lg bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover"
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

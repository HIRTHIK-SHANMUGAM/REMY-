import { Chat } from "./components/Chat";
import { ErrorBoundary } from "./components/ErrorBoundary";

export default function App() {
  return (
    <ErrorBoundary>
      <Chat />
    </ErrorBoundary>
  );
}

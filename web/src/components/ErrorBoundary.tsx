import { Component, type ReactNode } from "react";
import styles from "./ErrorBoundary.module.css";

type ErrorBoundaryProps = { name: string; children: ReactNode };
type ErrorBoundaryState = { error: Error | null };

export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error(`${this.props.name}: greška`, error);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className={styles.error} role="alert">
        {this.props.name}: greška ({this.state.error.message}){" "}
        <button
          className={styles.retry}
          onClick={() => this.setState({ error: null })}
        >
          Pokušaj ponovo
        </button>
      </div>
    );
  }
}

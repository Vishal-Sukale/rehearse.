import { Component } from "react";

// Shows a friendly screen instead of a blank page if something unexpected breaks.
export default class ErrorBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error) {
    console.error(error);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="boot crash">
        <div>
          <h1>Something went wrong</h1>
          <p>The app hit an unexpected problem. Your saved interviews are safe.</p>
          <button className="primary" onClick={() => window.location.reload()}>Reload</button>
        </div>
      </div>
    );
  }
}
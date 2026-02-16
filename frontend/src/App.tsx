import { useEffect, useState } from "react";

type HealthResponse = {
  status: string;
};

const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function App() {
  const [health, setHealth] = useState<string>("loading");

  useEffect(() => {
    fetch(`${apiBase}/health`)
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = (await res.json()) as HealthResponse;
        setHealth(data.status);
      })
      .catch((error: unknown) => {
        const message = error instanceof Error ? error.message : "unknown error";
        setHealth(`error: ${message}`);
      });
  }, []);

  return (
    <main style={{ fontFamily: "sans-serif", margin: "2rem" }}>
      <h1>Finance Dashboard Frontend Ready</h1>
      <p>API health: {health}</p>
      <p>API base URL: {apiBase}</p>
    </main>
  );
}

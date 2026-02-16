import { FormEvent, useEffect, useState } from "react";

type HealthResponse = {
  status: string;
};

type UploadResponse = {
  upload_id: number;
  filename: string;
  status: string;
  rows_total: number;
  rows_skipped_non_transaction: number;
  rows_invalid: number;
  rows_duplicate: number;
  rows_inserted: number;
};

const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function App() {
  const [health, setHealth] = useState<string>("loading");
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string>("");
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);

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

  const onUpload = async (event: FormEvent) => {
    event.preventDefault();

    if (!file) {
      setUploadError("Please select an .xlsx file first.");
      return;
    }

    setIsUploading(true);
    setUploadError("");
    setUploadResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${apiBase}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorBody = (await response.json()) as { detail?: string };
        throw new Error(errorBody.detail ?? `Upload failed (HTTP ${response.status})`);
      }

      const data = (await response.json()) as UploadResponse;
      setUploadResult(data);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "unknown error";
      setUploadError(message);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <main style={{ fontFamily: "sans-serif", margin: "2rem", maxWidth: "760px" }}>
      <h1>Finance Dashboard Frontend Ready</h1>
      <p>API health: {health}</p>
      <p>API base URL: {apiBase}</p>

      <hr style={{ margin: "1.5rem 0" }} />

      <section>
        <h2>Upload Statement</h2>
        <form onSubmit={onUpload}>
          <input
            type="file"
            accept=".xlsx"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setUploadError("");
              setUploadResult(null);
            }}
          />
          <button
            type="submit"
            disabled={!file || isUploading}
            style={{ marginLeft: "0.75rem" }}
          >
            {isUploading ? "Uploading..." : "Upload"}
          </button>
        </form>
        <p style={{ marginTop: "0.5rem", color: "#555" }}>
          Only .xlsx files are supported.
        </p>

        {uploadError && (
          <p style={{ color: "crimson", marginTop: "1rem" }}>
            Upload error: {uploadError}
          </p>
        )}

        {uploadResult && (
          <div style={{ marginTop: "1rem" }}>
            <h3>Upload Result</h3>
            <ul>
              <li>upload_id: {uploadResult.upload_id}</li>
              <li>filename: {uploadResult.filename}</li>
              <li>status: {uploadResult.status}</li>
              <li>rows_total: {uploadResult.rows_total}</li>
              <li>
                rows_skipped_non_transaction:{" "}
                {uploadResult.rows_skipped_non_transaction}
              </li>
              <li>rows_invalid: {uploadResult.rows_invalid}</li>
              <li>rows_duplicate: {uploadResult.rows_duplicate}</li>
              <li>rows_inserted: {uploadResult.rows_inserted}</li>
            </ul>
          </div>
        )}
      </section>
    </main>
  );
}

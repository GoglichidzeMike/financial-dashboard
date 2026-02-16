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
  llm_used_count: number;
  fallback_used_count: number;
};

type Merchant = {
  id: number;
  raw_name: string;
  normalized_name: string;
  category: string;
  category_source: string;
  mcc_code: string | null;
  transaction_count: number;
  total_spent: string;
};

type MerchantsResponse = {
  items: Merchant[];
};

type CategoriesResponse = {
  items: string[];
};

type LlmCheckResponse = {
  configured: boolean;
  ok: boolean;
  model: string;
  response?: string;
  error?: string | null;
};

const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function App() {
  const [health, setHealth] = useState<string>("loading");
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string>("");
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [merchantsError, setMerchantsError] = useState<string>("");
  const [isLoadingMerchants, setIsLoadingMerchants] = useState(false);
  const [savingMerchantId, setSavingMerchantId] = useState<number | null>(null);
  const [llmCheck, setLlmCheck] = useState<LlmCheckResponse | null>(null);
  const [isCheckingLlm, setIsCheckingLlm] = useState(false);

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

  useEffect(() => {
    fetch(`${apiBase}/categories`)
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = (await res.json()) as CategoriesResponse;
        setCategories(data.items);
      })
      .catch(() => {
        setCategories([]);
      });
  }, []);

  const loadMerchants = async () => {
    setIsLoadingMerchants(true);
    setMerchantsError("");
    try {
      const response = await fetch(`${apiBase}/merchants?limit=200&offset=0`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = (await response.json()) as MerchantsResponse;
      setMerchants(data.items);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "unknown error";
      setMerchantsError(message);
    } finally {
      setIsLoadingMerchants(false);
    }
  };

  const onCategoryChange = async (merchantId: number, category: string) => {
    setSavingMerchantId(merchantId);
    setMerchantsError("");

    try {
      const response = await fetch(`${apiBase}/merchants/${merchantId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ category }),
      });

      if (!response.ok) {
        const errorBody = (await response.json()) as { detail?: string };
        throw new Error(errorBody.detail ?? `HTTP ${response.status}`);
      }

      setMerchants((prev) =>
        prev.map((m) =>
          m.id === merchantId
            ? { ...m, category, category_source: "user" }
            : m
        )
      );
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "unknown error";
      setMerchantsError(message);
    } finally {
      setSavingMerchantId(null);
    }
  };

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

  const onCheckLlm = async () => {
    setIsCheckingLlm(true);
    setLlmCheck(null);
    try {
      const response = await fetch(`${apiBase}/llm/check`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = (await response.json()) as LlmCheckResponse;
      setLlmCheck(data);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "unknown error";
      setLlmCheck({
        configured: false,
        ok: false,
        model: "gpt-4o-mini",
        error: message,
      });
    } finally {
      setIsCheckingLlm(false);
    }
  };

  return (
    <main style={{ fontFamily: "sans-serif", margin: "2rem", maxWidth: "760px" }}>
      <h1>Finance Dashboard Frontend Ready</h1>
      <p>API health: {health}</p>
      <p>API base URL: {apiBase}</p>
      <button type="button" onClick={onCheckLlm} disabled={isCheckingLlm}>
        {isCheckingLlm ? "Checking LLM..." : "Check LLM"}
      </button>
      {llmCheck && (
        <p style={{ marginTop: "0.5rem" }}>
          LLM check: {llmCheck.ok ? "OK" : "FAILED"} | configured:{" "}
          {String(llmCheck.configured)} | model: {llmCheck.model}
          {llmCheck.error ? ` | error: ${llmCheck.error}` : ""}
          {llmCheck.response ? ` | response: ${llmCheck.response}` : ""}
        </p>
      )}

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
              <li>llm_used_count: {uploadResult.llm_used_count}</li>
              <li>fallback_used_count: {uploadResult.fallback_used_count}</li>
            </ul>
          </div>
        )}
      </section>

      <hr style={{ margin: "1.5rem 0" }} />

      <section>
        <h2>Merchants</h2>
        <button type="button" onClick={loadMerchants} disabled={isLoadingMerchants}>
          {isLoadingMerchants ? "Loading..." : "Load Merchants"}
        </button>

        {merchantsError && (
          <p style={{ color: "crimson", marginTop: "1rem" }}>
            Merchants error: {merchantsError}
          </p>
        )}

        {merchants.length > 0 && (
          <div style={{ marginTop: "1rem", overflowX: "auto" }}>
            <table style={{ borderCollapse: "collapse", minWidth: "700px" }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", padding: "0.4rem" }}>Merchant</th>
                  <th style={{ textAlign: "left", padding: "0.4rem" }}>Category</th>
                  <th style={{ textAlign: "right", padding: "0.4rem" }}>Tx Count</th>
                  <th style={{ textAlign: "right", padding: "0.4rem" }}>
                    Total Spent (GEL)
                  </th>
                </tr>
              </thead>
              <tbody>
                {merchants.map((merchant) => (
                  <tr key={merchant.id}>
                    <td style={{ padding: "0.4rem", borderTop: "1px solid #ddd" }}>
                      {merchant.raw_name}
                    </td>
                    <td style={{ padding: "0.4rem", borderTop: "1px solid #ddd" }}>
                      <select
                        value={merchant.category}
                        disabled={savingMerchantId === merchant.id || categories.length === 0}
                        onChange={(e) =>
                          onCategoryChange(merchant.id, e.target.value)
                        }
                      >
                        {categories.map((category) => (
                          <option key={category} value={category}>
                            {category}
                          </option>
                        ))}
                      </select>
                      <span style={{ marginLeft: "0.5rem", color: "#666" }}>
                        ({merchant.category_source})
                      </span>
                    </td>
                    <td
                      style={{
                        padding: "0.4rem",
                        borderTop: "1px solid #ddd",
                        textAlign: "right",
                      }}
                    >
                      {merchant.transaction_count}
                    </td>
                    <td
                      style={{
                        padding: "0.4rem",
                        borderTop: "1px solid #ddd",
                        textAlign: "right",
                      }}
                    >
                      {merchant.total_spent}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}

import { useEffect, useState } from "react";

// Plain on purpose: the brief says a plain working table is the right answer.
const cell = { border: "1px solid #ccc", padding: "4px 8px", textAlign: "left", verticalAlign: "top" };

async function getJson(url) {
  const res = await fetch(url);
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
  return body;
}

export default function App() {
  const [orgs, setOrgs] = useState([]);
  const [org, setOrg] = useState("");
  const [reason, setReason] = useState("");
  const [ordering, setOrdering] = useState(""); // "", "value", "-value"
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getJson("/api/orgs")
      .then((b) => { setOrgs(b.orgs); setOrg(b.orgs[0] || ""); })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!org) return;
    const q = new URLSearchParams({ org, reason, ordering });
    setError("");
    getJson(`/api/disagreements?${q}`).then(setData).catch((e) => setError(e.message));
  }, [org, reason, ordering]);

  const cycleSort = () => setOrdering(ordering === "" ? "value" : ordering === "value" ? "-value" : "");
  const arrow = ordering === "value" ? " ▲" : ordering === "-value" ? " ▼" : "";
  const total = data ? data.reasons.reduce((n, r) => n + r.count, 0) : 0;

  return (
    <div style={{ fontFamily: "sans-serif", padding: 16 }}>
      <h1>System A vs System B: disagreements</h1>

      <p>
        <label>Org:{" "}
          <select value={org} onChange={(e) => { setOrg(e.target.value); setReason(""); }}>
            {orgs.map((o) => <option key={o} value={o}>{o}</option>)}
          </select>
        </label>{" "}
        <label>Reason:{" "}
          <select value={reason} onChange={(e) => setReason(e.target.value)}>
            <option value="">All ({total})</option>
            {data && data.reasons.filter((r) => r.count > 0).map((r) => (
              <option key={r.key} value={r.key}>{r.label} ({r.count})</option>
            ))}
          </select>
        </label>
      </p>

      {error && <p style={{ color: "crimson" }}>Error: {error}</p>}
      {data && data.results.length === 0 && <p>No disagreements.</p>}

      {data && data.results.length > 0 && (
        <table style={{ borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["Reason", "Record", "B entry", "A value", "B value", "A location", "B location", "Detail"].map((h) => (
                <th key={h} style={cell}>
                  {h === "A value" ? (
                    <button onClick={cycleSort} title="Sort by value">{h}{arrow}</button>
                  ) : h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.results.map((r) => (
              <tr key={r.id} style={r.redacted ? { background: "#fff6e0" } : undefined}>
                <td style={cell}>{data.reasons.find((x) => x.key === r.reason)?.label ?? r.reason}</td>
                <td style={cell}>{r.record_id}</td>
                <td style={cell}>{r.entry_ids.join(", ")}</td>
                <td style={{ ...cell, textAlign: "right" }}>{r.a_value}</td>
                <td style={{ ...cell, textAlign: "right" }}>{r.b_value}</td>
                <td style={cell}>{r.a_location}</td>
                <td style={cell}>{r.b_location}</td>
                <td style={cell}>{r.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

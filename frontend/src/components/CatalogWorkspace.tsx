import { useEffect, useMemo, useState } from "react";
import L from "leaflet";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";
import { ApiError, api } from "../api/client";
import { LABEL_COLOR, formatMoney } from "../lib/format";
import { cityCenter, mapCities } from "../lib/cities";
import type { CatalogCommitment, CatalogMatch, CatalogProject, CatalogRecommendation, CatalogSummary } from "../types/catalog";

const examples = [
  {
    country: "Pakistan",
    city: "Karachi",
    title: "Karachi water and sewerage services",
    description: "Expand water supply and sewerage services for households in Karachi.",
    sector: "Water",
    amount: "40000000",
  },
  {
    country: "Bangladesh",
    city: "Dhaka",
    title: "Dhaka public transport improvement",
    description: "Public transport improvement for commuters in Dhaka.",
    sector: "Transport",
    amount: "50000000",
  },
  {
    country: "Pakistan",
    city: "Lahore",
    title: "Lahore urban transport",
    description: "Urban transport services for Lahore.",
    sector: "Transport",
    amount: "25000000",
  },
] as const;

function text(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "The World Bank catalog could not be loaded.";
}

function FitCities({ points }: { points: [number, number][] }) {
  const map = useMap();
  const signature = points.map((point) => point.join(",")).join("|");
  useEffect(() => {
    if (!points.length) return;
    const fit = () => {
      map.invalidateSize();
      map.fitBounds(L.latLngBounds(points), { padding: [48, 48] });
    };
    fit();
    const timer = window.setTimeout(fit, 200);
    return () => window.clearTimeout(timer);
  }, [map, signature]);
  return null;
}

function FocusCity({ city }: { city: string }) {
  const map = useMap();
  useEffect(() => {
    const center = cityCenter(city);
    if (!center) return;
    map.flyTo(center, 6, { duration: 0.6 });
  }, [city, map]);
  return null;
}

export function CatalogWorkspace() {
  const [summary, setSummary] = useState<CatalogSummary | null>(null);
  const [projects, setProjects] = useState<CatalogProject[]>([]);
  const [matches, setMatches] = useState<CatalogMatch[]>([]);
  const [note, setNote] = useState("");
  const [commitment, setCommitment] = useState<CatalogCommitment | null>(null);
  const [advice, setAdvice] = useState<CatalogRecommendation | null>(null);
  const [decisionNote, setDecisionNote] = useState("");
  const [country, setCountry] = useState<string>(examples[0].country);
  const [city, setCity] = useState<string>(examples[0].city);
  const [title, setTitle] = useState<string>(examples[0].title);
  const [description, setDescription] = useState<string>(examples[0].description);
  const [sector, setSector] = useState<string>(examples[0].sector);
  const [amount, setAmount] = useState<string>(examples[0].amount);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"compare" | "recommend" | "direct" | "">("");
  const [focused, setFocused] = useState(false);

  const cities = useMemo(() => mapCities(summary?.cities ?? []), [summary]);
  const countryCities = (summary?.cities ?? []).filter((item) => item.country === country);
  const step = commitment?.city === city && commitment.title === title ? 3 : advice ? 2 : 1;
  const overriding = Boolean(advice && city !== advice.recommended_city);

  useEffect(() => {
    const controller = new AbortController();
    api.getCatalog()
      .then((next) => {
        if (!controller.signal.aborted) setSummary(next);
      })
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) setError(text(reason));
      });
    api.getCatalogCommitment()
      .then((next) => {
        if (!controller.signal.aborted) setCommitment(next);
      })
      .catch((reason: unknown) => {
        if (reason instanceof ApiError && reason.status === 404) return;
        if (!controller.signal.aborted) setError(text(reason));
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!country || !city) return;
    let cancelled = false;
    api.getCatalogProjects(country, city)
      .then((rows) => {
        if (!cancelled) setProjects(rows);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setError(text(reason));
      });
    return () => {
      cancelled = true;
    };
  }, [country, city]);

  function applyExample(index: number) {
    const example = examples[index];
    setCountry(example.country);
    setCity(example.city);
    setTitle(example.title);
    setDescription(example.description);
    setSector(example.sector);
    setAmount(example.amount);
    setMatches([]);
    setNote("");
    setAdvice(null);
    setDecisionNote("");
    setFocused(true);
  }

  function chooseCity(nextCountry: string, nextCity: string) {
    setCountry(nextCountry);
    setCity(nextCity);
    setMatches([]);
    setNote("");
    setFocused(true);
    if (advice && nextCountry !== advice.country) {
      setAdvice(null);
      setDecisionNote("");
      return;
    }
    if (advice) void compareFor(nextCity);
  }

  function editProposal(update: () => void) {
    update();
    setAdvice(null);
    setDecisionNote("");
    setMatches([]);
    setNote("");
  }

  async function compareFor(nextCity: string) {
    setBusy("compare");
    setError("");
    setNote("");
    try {
      const result = await api.compareCatalog({ title, description, country, city: nextCity, sector });
      setMatches(result.matches);
      setNote(result.matches.length ? result.note : "No World Bank project shared enough of this wording. Try one of the city examples.");
      setFocused(true);
    } catch (reason: unknown) {
      setError(text(reason));
    } finally {
      setBusy("");
    }
  }

  async function recommend() {
    setBusy("recommend");
    setError("");
    setAdvice(null);
    setDecisionNote("");
    try {
      const result = await api.recommendCatalog({ title, description, country, city, sector });
      setAdvice(result);
      setCity(result.recommended_city);
      setFocused(true);
      setBusy("");
      await compareFor(result.recommended_city);
    } catch (reason: unknown) {
      setError(text(reason));
      setBusy("");
    }
  }

  async function direct() {
    if (!advice) return;
    if (overriding && decisionNote.trim().length < 8) {
      setError("Add a short reason for choosing a different city.");
      return;
    }
    setBusy("direct");
    setError("");
    try {
      const recorded = await api.commitCatalog({
        country,
        city,
        title,
        amount_usd: amount || "0",
        project_ids: matches.map((match) => match.project.project_id),
        recommended_city: advice.recommended_city,
        human_choice: overriding ? "override" : "accepted",
        decision_note: overriding ? decisionNote.trim() : "",
      });
      setCommitment(recorded);
      setFocused(true);
    } catch (reason: unknown) {
      setError(text(reason));
    } finally {
      setBusy("");
    }
  }

  const pendingChoice = advice ? (overriding ? "override" : "accepted") : commitment?.human_choice;
  const directedHere = Boolean(
    commitment &&
    commitment.city === city &&
    commitment.title === title &&
    (commitment.human_choice ?? "unreviewed") === pendingChoice &&
    (!overriding || (commitment.decision_note ?? "") === decisionNote.trim())
  );
  const shownMatches = matches.length ? matches.map((match) => match.project) : projects;

  return (
    <>
      <ol className="progress steps-3">
        {["Describe the proposal", "Review the area", "Direct the budget"].map((label, index) => (
          <li key={label} className={index + 1 < step ? "done" : index + 1 === step ? "current" : ""}>
            <span>{index + 1}</span>
            {label}
          </li>
        ))}
      </ol>
      {error && <p className="banner" role="alert">{error}</p>}
      <div className="workspace">
        <aside className="intake">
          <section className="guide">
            <p className="eyebrow">World Bank Projects API · Pakistan and Bangladesh</p>
            <h2>
              {summary
                ? `${summary.project_count} urban projects from the World Bank.`
                : "Loading the World Bank project snapshot."}
            </h2>
            <p>
              {summary
                ? `${summary.projects_without_city} records name a country but no city, so only named cities are on the map. A recommendation ranks those cities from the proposal and the money already on record. You choose the city before anything is directed.`
                : "The map uses the local snapshot fetched from search.worldbank.org."}
            </p>
            <div className="city-picks">
              {examples.map((example, index) => (
                <button key={example.city + example.title} type="button" className="chip" onClick={() => applyExample(index)}>
                  {example.city}
                </button>
              ))}
            </div>
          </section>
          <form
            className="proposal"
            onSubmit={(event) => {
              event.preventDefault();
              void recommend();
            }}
          >
            <div className="split">
              <label>
                Country
                <select
                  value={country}
                  onChange={(event) => {
                    const next = event.target.value;
                    const first = summary?.cities.find((item) => item.country === next);
                    editProposal(() => {
                      setCountry(next);
                      setCity(first?.city ?? "");
                      setFocused(true);
                    });
                  }}
                >
                  {(summary?.countries ?? [{ country, project_count: 0 }]).map((item) => (
                    <option key={item.country} value={item.country}>{item.country} · {item.project_count}</option>
                  ))}
                </select>
              </label>
              <label>
                City named in the records
                <select value={city} onChange={(event) => chooseCity(country, event.target.value)}>
                  {countryCities.map((item) => (
                    <option key={item.city} value={item.city}>{item.city} · {item.project_count}</option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              Proposal title
              <input value={title} onChange={(event) => editProposal(() => setTitle(event.target.value))} />
            </label>
            <label>
              What it would fund
              <textarea value={description} onChange={(event) => editProposal(() => setDescription(event.target.value))} />
            </label>
            <div className="split">
              <label>
                Sector
                <input value={sector} onChange={(event) => editProposal(() => setSector(event.target.value))} />
              </label>
              <label>
                Budget to direct (USD)
                <input value={amount} inputMode="decimal" onChange={(event) => setAmount(event.target.value)} />
              </label>
            </div>
            <button type="submit" className="primary" disabled={busy !== "" || title.trim().length < 3}>
              {busy === "recommend" || busy === "compare" ? "Reading the project index…" : "Recommend an area"}
            </button>
          </form>
          {advice && (
            <section className="advice" aria-label="Area recommendation">
              <h2>{advice.summary}</h2>
              {advice.model_id && <p className="meta-line">Chat model {advice.model_id} · local · no charge</p>}
              <p className="hint">{advice.note}</p>
              {advice.areas.map((area) => (
                <article key={area.city} className="verdict" style={{ borderLeftColor: area.recommended ? "#1c6b74" : "#8d6840" }}>
                  <strong>{area.recommended ? "Recommended" : "Alternative"}</strong>
                  <h3>{area.city}</h3>
                  <p className="meta-line">
                    World Bank on record {formatMoney(area.worldbank_usd)} · {area.project_count} projects
                    {area.relevance > 0 ? ` · similarity ${(area.relevance * 100).toFixed(0)}%` : ""}
                  </p>
                  <p className="why">{area.reason}</p>
                  {area.city !== city && (
                    <button type="button" className="secondary" disabled={busy !== ""} onClick={() => chooseCity(area.country, area.city)}>
                      Choose {area.city} instead
                    </button>
                  )}
                </article>
              ))}
              {overriding && (
                <label>
                  Why this city instead of {advice.recommended_city}
                  <textarea
                    value={decisionNote}
                    onChange={(event) => setDecisionNote(event.target.value)}
                    placeholder="A short reason is saved with the decision."
                  />
                </label>
              )}
              {!overriding && <p className="hint">This uses {advice.recommended_city}. Pick another city above if you want a different call.</p>}
            </section>
          )}
          <div className="verdicts">
            <div className="section-head">
              <h2>{matches.length ? "World Bank matches" : `Projects that name ${city}`}</h2>
              <span>{shownMatches.length}</span>
            </div>
            {note && <p className="hint">{note}</p>}
            {shownMatches.map((project) => {
              const match = matches.find((item) => item.project.project_id === project.project_id);
              return (
                <article key={project.project_id} className="verdict" style={{ borderLeftColor: match ? LABEL_COLOR[match.label as keyof typeof LABEL_COLOR] ?? "#1c6b74" : "#1c6b74" }}>
                  {match && <strong style={{ color: LABEL_COLOR[match.label as keyof typeof LABEL_COLOR] }}>{match.label}</strong>}
                  <h3>{project.name}</h3>
                  <p className="meta-line">
                    {project.project_id} · {project.city ?? "No city named"} · {formatMoney(project.amount_usd)} · {project.source}
                  </p>
                  {match && <p className="why">{match.explanation}</p>}
                  {project.source_url && (
                    <a href={project.source_url} target="_blank" rel="noreferrer">Open the World Bank record</a>
                  )}
                </article>
              );
            })}
            <button type="button" className="primary" disabled={busy !== "" || !advice || !matches.length || !city || (overriding && decisionNote.trim().length < 8)} onClick={() => void direct()}>
              {busy === "direct"
                ? "Directing…"
                : directedHere
                  ? `${formatMoney(commitment?.amount_usd ?? amount)} is directed to ${city}`
                  : overriding
                    ? `Direct ${formatMoney(amount || 0)} to ${city} instead`
                    : `Direct ${formatMoney(amount || 0)} to ${city}`}
            </button>
            {!advice && <p className="hint">Recommend an area first. You can accept that city or choose another, and the budget is recorded only when you direct it.</p>}
            {advice && !matches.length && <p className="hint">Waiting for the project match in {city}.</p>}
            {directedHere && commitment && (
              <section className="impact">
                <h2>What {formatMoney(commitment.impact.added_usd)} does in {commitment.city}</h2>
                {commitment.human_choice === "override" && (
                  <p className="why">You chose {commitment.city} instead of {commitment.recommended_city}. {commitment.decision_note}</p>
                )}
                {commitment.human_choice === "accepted" && (
                  <p className="why">You accepted the recommendation for {commitment.city}.</p>
                )}
                <p className="meta-line">
                  World Bank already on record {formatMoney(commitment.impact.worldbank_in_city_usd)}
                  {" + "}your budget {formatMoney(commitment.impact.added_usd)}
                  {" = "}{formatMoney(commitment.impact.after_usd)} visible in this city.
                </p>
                {commitment.impact.lines.map((line) => (
                  <article key={line.project_id} className="verdict" style={{ borderLeftColor: LABEL_COLOR[line.label as keyof typeof LABEL_COLOR] ?? "#1c6b74" }}>
                    <strong style={{ color: LABEL_COLOR[line.label as keyof typeof LABEL_COLOR] }}>{line.label === "OVERLAPPING" ? "Co-finance" : "Complement"}</strong>
                    <h3>{line.name}</h3>
                    <p className="meta-line">
                      World Bank {formatMoney(line.worldbank_amount_usd)} + your share {formatMoney(line.added_usd)} = {formatMoney(line.combined_usd)}
                    </p>
                    <p className="why">{line.connection}</p>
                  </article>
                ))}
              </section>
            )}
          </div>
        </aside>
        <section className="map-stage geo" aria-label="World Bank project map">
          <MapContainer center={[26.2, 78]} zoom={5} style={{ height: "100%", width: "100%" }}>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {focused ? <FocusCity city={city} /> : <FitCities points={cities.map((item) => item.center)} />}
            {cities.map((item) => {
              const selected = item.names.includes(city) || item.key === city;
              const directed = commitment ? item.names.includes(commitment.city) || item.key === commitment.city : false;
              const recommended = advice ? item.names.includes(advice.recommended_city) || item.key === advice.recommended_city : false;
              return (
                <CircleMarker
                  key={`${item.country}-${item.key}`}
                  center={item.center}
                  radius={selected ? 16 : 8 + Math.sqrt(item.count) * 2}
                  pathOptions={{
                    color: recommended ? "#1c6b74" : directed ? "#8d6840" : "#102433",
                    weight: selected ? 3 : 1.5,
                    fillColor: recommended ? "#2f8f86" : directed ? "#c4a574" : "#16485a",
                    fillOpacity: 0.85,
                  }}
                  eventHandlers={{ click: () => chooseCity(item.country, item.names[0]) }}
                >
                  <Tooltip direction="top">
                    {item.label}, {item.country}: {item.count} World Bank projects. City center, not a project site.
                    {recommended ? " Recommended from the proposal and existing coverage." : ""}
                    {directed && commitment ? ` ${formatMoney(commitment.amount_usd)} directed here.` : ""}
                  </Tooltip>
                </CircleMarker>
              );
            })}
          </MapContainer>
          <aside className="map-legend">
            <b>World Bank</b>
            <p>
              Each circle is a city named in the project records. Teal is the recommended city. {summary ? `${summary.projects_without_city} projects have no city and stay off the map.` : ""}
              {commitment ? ` ${commitment.city}: ${formatMoney(commitment.impact.worldbank_in_city_usd)} on record, ${formatMoney(commitment.impact.after_usd)} after this budget.` : ""}
            </p>
          </aside>
          {commitment && (
            <div className="district-strip">
              <div className="district-card">
                <span>
                  <strong>{formatMoney(commitment.impact.worldbank_in_city_usd)} → {formatMoney(commitment.impact.after_usd)}</strong>
                  <small>World Bank on record in {commitment.city}, then after your {formatMoney(commitment.impact.added_usd)}</small>
                </span>
              </div>
              <div className="district-card">
                <span>
                  <strong>{commitment.title}</strong>
                  <small>{commitment.country} · saved {commitment.commitment_id}</small>
                </span>
              </div>
            </div>
          )}
        </section>
      </div>
    </>
  );
}

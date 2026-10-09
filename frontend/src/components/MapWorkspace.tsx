import { useEffect } from "react";
import L from "leaflet";
import { GeoJSON, MapContainer, useMap } from "react-leaflet";
import { districtFromAttributes, districts, type DistrictProperties } from "../lib/geo";
import { LABEL_COLOR, formatMoney, needColor } from "../lib/format";
import type { Assignment, DistrictNeedRecord, Proposal, Role, Verdict } from "../types/api";

interface MapWorkspaceProps {
  gaps: DistrictNeedRecord[];
  gapsError: string;
  proposal: Proposal | null;
  role: Role;
  assignment: Assignment | null;
  deciding: boolean;
  verdicts: Verdict[];
  selectedProjectId: string | null;
  focusedDistrictId: string | null;
  onFocus: (districtId: string) => void;
  onCommit: (districtId: string) => void;
}

function FitMap({ focus }: { focus: string | null }) {
  const map = useMap();
  useEffect(() => {
    const layer = L.geoJSON(districts);
    const fit = () => {
      map.invalidateSize();
      map.fitBounds(layer.getBounds(), { padding: [36, 48], animate: false });
    };
    fit();
    const timer = window.setTimeout(fit, 180);
    window.addEventListener("resize", fit);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("resize", fit);
    };
  }, [map]);
  useEffect(() => {
    if (!focus) return;
    const feature = districts.features.find((item) => item.properties.district_id === focus);
    if (!feature) return;
    const bounds = L.geoJSON(feature).getBounds();
    map.fitBounds(bounds, { padding: [80, 80], maxZoom: 1, animate: true });
  }, [focus, map]);
  return null;
}

export function MapWorkspace({
  gaps,
  gapsError,
  proposal,
  role,
  assignment,
  deciding,
  verdicts,
  selectedProjectId,
  focusedDistrictId,
  onFocus,
  onCommit,
}: MapWorkspaceProps) {
  const snapshot = gaps[0]?.snapshot_date ?? "TBD: needs source";
  const quality = gaps[0]?.indicator_quality;
  const canCommit = role === "approver" && (proposal?.status === "REVIEWED" || proposal?.status === "APPROVED");
  const budget = proposal ? formatMoney(proposal.budget_usd) : "";

  return (
    <section className="map-stage" aria-label="District need map">
      <MapContainer
        crs={L.CRS.Simple}
        bounds={[[0, 0], [1, 2]]}
        minZoom={-2}
        maxZoom={3}
        zoomSnap={0.1}
        attributionControl={false}
        zoomControl={false}
        style={{ height: "100%", width: "100%", background: "transparent" }}
      >
        <FitMap focus={focusedDistrictId} />
        <GeoJSON
          key={`${focusedDistrictId ?? ""}-${selectedProjectId ?? ""}-${gaps.length}`}
          data={districts}
          style={(feature) => {
            const id = String(feature?.properties?.district_id ?? "");
            const record = gaps.find((item) => item.district_id === id);
            const selected = verdicts.find((verdict) => verdict.project_id === selectedProjectId);
            const linked = selected ? districtFromAttributes(selected.matching_attributes) === id : false;
            return {
              color: linked ? LABEL_COLOR[selected!.label] : focusedDistrictId === id ? "#8d6840" : "#102433",
              weight: focusedDistrictId === id || linked ? 3.5 : 1.5,
              fillColor: record ? needColor(record.need_score) : "#d9e2e4",
              fillOpacity: record && record.need_score > 0.55 ? 0.72 : 0.42,
            };
          }}
          onEachFeature={(feature, layer) => {
            const id = String((feature.properties as DistrictProperties | null)?.district_id ?? "");
            const record = gaps.find((item) => item.district_id === id);
            layer.on("click", () => onFocus(id));
          }}
        />
      </MapContainer>
      <aside className="map-legend">
        <b>Need</b>
        <div>
          <div className="scale" aria-hidden="true"><i /><i /><i /><i /><i /></div>
          <div className="scale-labels"><span>0 low</span><span>1 high</span></div>
        </div>
        <p>Darker fill means higher need. Names and the commit buttons are on the cards below, not drawn on the shapes. {quality ?? "Illustrative"} indicators. Data snapshot: {snapshot}.</p>
        {gapsError && <p className="error">{gapsError}</p>}
      </aside>
      <div className="district-strip">
        {gaps.map((record) => {
          const committedHere = assignment?.district_id === record.district_id;
          const shown = committedHere ? Number(assignment?.amount_usd ?? 0) : 0;
          return (
            <div key={record.district_id} className={focusedDistrictId === record.district_id ? "district-slot on" : "district-slot"}>
              <button
                type="button"
                className="district-card"
                onClick={() => onFocus(record.district_id)}
              >
                <span className="swatch" style={{ background: needColor(record.need_score) }} />
                <span>
                  <strong>{record.district_name}</strong>
                  <small>Need {record.need_score.toFixed(2)}</small>
                </span>
                <span className="nums">
                  <b>{formatMoney(shown)}</b>
                  <small>{committedHere ? "Committed here" : "Nothing committed"}</small>
                </span>
              </button>
              {proposal && (proposal.status === "REVIEWED" || proposal.status === "APPROVED") && (
                <button
                  type="button"
                  className="primary"
                  disabled={!canCommit || deciding || committedHere}
                  onClick={() => onCommit(record.district_id)}
                >
                  {committedHere ? `Committed ${budget}` : assignment ? `Move ${budget} here` : `Commit ${budget} here`}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

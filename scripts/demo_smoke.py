"""Exercise the deterministic cached Atlas11 API path without AWS or retrieval."""

import os
import sys
import tempfile
from pathlib import Path

os.environ["DEMO_MODE"] = "cached"
_smoke_db = tempfile.NamedTemporaryFile(
    prefix="atlas11-demo-", suffix=".db", delete=False
)
_smoke_db.close()
os.environ["ATLAS11_DB_PATH"] = _smoke_db.name
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from agent.app import app  # noqa: E402


def main() -> None:
    """Run canonical intake, SSE, report, approval, audit, and read-only gaps checks."""
    client = TestClient(app)
    import json
    from pathlib import Path

    cached = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data/demo_cache/demo-city-transit-01.json"
        ).read_text()
    )
    proposal = client.post("/proposals", json=cached["proposal"])
    assert proposal.status_code == 201, proposal.text
    proposal_id = proposal.json()["proposal_id"]
    review = client.post(f"/proposals/{proposal_id}/review")
    assert review.status_code == 202, review.text
    review_id = review.json()["review_id"]
    stream = client.get(f"/reviews/{review_id}/events")
    assert stream.status_code == 200, stream.text
    event_types = [
        json.loads(line[6:])["type"]
        for line in stream.text.splitlines()
        if line.startswith("data: ")
    ]
    assert event_types == ["status", "tool_call", "verdict", "verdict", "done"], (
        event_types
    )
    report = client.get(f"/reviews/{review_id}").json()["report"]
    assert [v["label"] for v in report["candidates"]] == [
        "OVERLAPPING",
        "COMPLEMENTARY",
    ]
    assert report["memo"]["recommendation"] == "CO_FINANCE"
    decision = client.post(
        "/approvals",
        json={
            "review_id": review_id,
            "decision": "APPROVED",
            "actor": "demo-approver",
            "role": "approver",
        },
    )
    assert decision.status_code == 201, decision.text
    assert (
        client.get(
            "/gaps", params={"district_id": report["memo"]["redirect_district_id"]}
        ).status_code
        == 200
    )
    assert client.get("/audit", params={"review_id": review_id}).status_code == 200
    print(
        "Cached demo smoke passed: seeded review, coordination approval, and read-only gap focus."
    )


if __name__ == "__main__":
    main()

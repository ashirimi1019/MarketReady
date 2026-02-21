"""
Backend tests for 6 hackathon features:
1. GitHub Signal Auditor
2. MRI Algorithm
3. Sentinel Market Guard
4. Interactive 90-Day Pivot Kanban (CRUD + generate)
5. 2027 Future-Shock Simulator
6. Recruiter Truth-Link (public profile share)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback to external URL for this test session
    BASE_URL = "https://market-sentinel-54.preview.emergentagent.com/api"

AUTH_HEADERS_STORE = {}


# ---------------------------------------------------------------------------
# Helper / Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def auth_token():
    """Register + login test user, return auth token."""
    session = requests.Session()
    # Try to register (may already exist)
    reg_resp = session.post(
        f"{BASE_URL}/auth/register",
        json={"username": "testuser", "password": "TestPass123!", "email": "test@example.com"},
        timeout=15,
    )
    # 200/201 = created; 400/409 = already exists – both ok
    assert reg_resp.status_code in (200, 201, 400, 409), (
        f"Unexpected register status {reg_resp.status_code}: {reg_resp.text}"
    )

    # Login
    login_resp = session.post(
        f"{BASE_URL}/auth/login",
        json={"username": "testuser", "password": "TestPass123!"},
        timeout=15,
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    data = login_resp.json()
    # Backend returns 'auth_token' key
    token = data.get("auth_token") or data.get("token") or data.get("access_token")
    assert token, f"No token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def authed(auth_token):
    """Requests session with X-Auth-Token header."""
    s = requests.Session()
    s.headers.update({"X-Auth-Token": auth_token, "Content-Type": "application/json"})
    return s


# ===========================================================================
# 1. GitHub Signal Auditor
# ===========================================================================

class TestGitHubAudit:
    """GET /github/audit/:username"""

    def test_audit_valid_user_octocat(self):
        """Test GitHub audit with 'octocat' – public well-known user."""
        resp = requests.get(f"{BASE_URL}/github/audit/octocat", timeout=20)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        # Required fields
        assert "verified_skills" in data, "Missing verified_skills"
        assert "velocity" in data, "Missing velocity"
        assert "warnings" in data, "Missing warnings"
        assert isinstance(data["verified_skills"], list)
        assert isinstance(data["velocity"], dict)
        # Velocity sub-keys
        vel = data["velocity"]
        assert "velocity_score" in vel
        assert "recent_repos" in vel
        assert "total_repos" in vel
        assert "languages" in vel
        assert "stars" in vel
        print(f"PASS: octocat audit – {len(data['verified_skills'])} skills, velocity={vel['velocity_score']}")

    def test_audit_username_field_returned(self):
        """Returned JSON must include the username."""
        resp = requests.get(f"{BASE_URL}/github/audit/octocat", timeout=20)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("username") == "octocat"
        print("PASS: username field matches")

    def test_audit_invalid_user_404(self):
        """Non-existent GitHub user should return 404."""
        resp = requests.get(
            f"{BASE_URL}/github/audit/this-user-definitely-does-not-exist-xyz-12345abc",
            timeout=20,
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("PASS: 404 for non-existent user")

    def test_audit_no_auth_required(self):
        """GitHub audit endpoint should work without auth."""
        resp = requests.get(f"{BASE_URL}/github/audit/octocat", timeout=20)
        assert resp.status_code == 200
        print("PASS: No auth required for GitHub audit")


# ===========================================================================
# 2. MRI Algorithm
# ===========================================================================

class TestMRIScore:
    """GET /score/mri – requires auth"""

    def test_mri_returns_200(self, authed):
        resp = authed.get(f"{BASE_URL}/score/mri", timeout=15)
        assert resp.status_code == 200, f"MRI failed: {resp.status_code} {resp.text}"
        print(f"PASS: MRI returned 200")

    def test_mri_has_required_fields(self, authed):
        resp = authed.get(f"{BASE_URL}/score/mri", timeout=15)
        assert resp.status_code == 200
        data = resp.json()
        assert "score" in data
        assert "components" in data
        assert "band" in data
        comps = data["components"]
        assert "federal_standards" in comps
        assert "market_demand" in comps
        assert "evidence_density" in comps
        print(f"PASS: MRI fields present – score={data['score']}, band={data['band']}")

    def test_mri_score_is_numeric(self, authed):
        resp = authed.get(f"{BASE_URL}/score/mri", timeout=15)
        data = resp.json()
        assert isinstance(data["score"], (int, float))
        assert 0.0 <= data["score"] <= 100.0
        print(f"PASS: MRI score is valid numeric: {data['score']}")

    def test_mri_band_is_valid_string(self, authed):
        resp = authed.get(f"{BASE_URL}/score/mri", timeout=15)
        data = resp.json()
        valid_bands = {"Market Ready", "Competitive", "Developing", "Focus Gaps", "Not Started"}
        assert data["band"] in valid_bands, f"Unknown band: {data['band']}"
        print(f"PASS: MRI band is valid: {data['band']}")

    def test_mri_without_auth_returns_401(self):
        resp = requests.get(f"{BASE_URL}/score/mri", timeout=15)
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: 401 without auth token")


# ===========================================================================
# 3. Sentinel Market Guard
# ===========================================================================

class TestSentinel:
    """POST /sentinel/run – requires auth"""

    def test_sentinel_run_returns_200(self, authed):
        resp = authed.post(f"{BASE_URL}/sentinel/run", timeout=20)
        assert resp.status_code == 200, f"Sentinel failed: {resp.status_code} {resp.text}"
        print("PASS: Sentinel run returned 200")

    def test_sentinel_returns_alerts(self, authed):
        resp = authed.post(f"{BASE_URL}/sentinel/run", timeout=20)
        assert resp.status_code == 200
        data = resp.json()
        assert "alerts" in data, "Missing 'alerts' key"
        assert "alerts_created" in data, "Missing 'alerts_created' key"
        assert isinstance(data["alerts"], list)
        assert isinstance(data["alerts_created"], int)
        print(f"PASS: Sentinel alerts_created={data['alerts_created']}, count={len(data['alerts'])}")

    def test_sentinel_creates_notifications(self, authed):
        """After running sentinel, notifications list should not be empty."""
        authed.post(f"{BASE_URL}/sentinel/run", timeout=20)
        notif_resp = authed.get(f"{BASE_URL}/user/notifications", timeout=15)
        assert notif_resp.status_code == 200
        notes = notif_resp.json()
        assert len(notes) >= 1, "No notifications after sentinel run"
        print(f"PASS: {len(notes)} notifications after sentinel run")

    def test_sentinel_without_auth_returns_401(self):
        resp = requests.post(f"{BASE_URL}/sentinel/run", timeout=15)
        assert resp.status_code == 401
        print("PASS: Sentinel 401 without auth")


# ===========================================================================
# 4. Kanban Board – CRUD + Generate
# ===========================================================================

class TestKanban:
    """Full Kanban CRUD flow"""

    created_task_id = None

    def test_get_board_returns_200(self, authed):
        resp = authed.get(f"{BASE_URL}/kanban/board", timeout=15)
        assert resp.status_code == 200, f"Get board failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "board" in data
        board = data["board"]
        assert "todo" in board
        assert "in_progress" in board
        assert "done" in board
        print(f"PASS: Board returned – total={data['total']}")

    def test_create_task(self, authed):
        resp = authed.post(
            f"{BASE_URL}/kanban/tasks",
            json={"title": "TEST_Hackathon Task", "status": "todo", "priority": "high"},
            timeout=15,
        )
        assert resp.status_code == 200, f"Create task failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "id" in data
        assert data["title"] == "TEST_Hackathon Task"
        assert data["status"] == "todo"
        TestKanban.created_task_id = data["id"]
        print(f"PASS: Task created id={data['id']}")

    def test_update_task_status(self, authed):
        assert TestKanban.created_task_id, "No task ID from create"
        task_id = TestKanban.created_task_id
        resp = authed.put(
            f"{BASE_URL}/kanban/tasks/{task_id}",
            json={"status": "in_progress"},
            timeout=15,
        )
        assert resp.status_code == 200, f"Update task failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data["status"] == "in_progress"
        print(f"PASS: Task status updated to in_progress")

    def test_update_nonexistent_task_404(self, authed):
        resp = authed.put(
            f"{BASE_URL}/kanban/tasks/00000000-0000-0000-0000-000000000000",
            json={"status": "done"},
            timeout=15,
        )
        assert resp.status_code == 404
        print("PASS: 404 for non-existent task update")

    def test_delete_task(self, authed):
        assert TestKanban.created_task_id, "No task ID"
        task_id = TestKanban.created_task_id
        resp = authed.delete(f"{BASE_URL}/kanban/tasks/{task_id}", timeout=15)
        assert resp.status_code in (200, 204), f"Delete failed: {resp.status_code} {resp.text}"
        print(f"PASS: Task deleted")

    def test_delete_verifies_removal(self, authed):
        """Board should not contain deleted task."""
        board_resp = authed.get(f"{BASE_URL}/kanban/board", timeout=15)
        assert board_resp.status_code == 200
        data = board_resp.json()
        all_ids = (
            [t["id"] for t in data["board"]["todo"]] +
            [t["id"] for t in data["board"]["in_progress"]] +
            [t["id"] for t in data["board"]["done"]]
        )
        if TestKanban.created_task_id:
            assert TestKanban.created_task_id not in all_ids, "Deleted task still in board"
        print("PASS: Deleted task not found in board")

    def test_generate_ai_plan(self, authed):
        resp = authed.post(f"{BASE_URL}/kanban/generate", timeout=30)
        assert resp.status_code == 200, f"Generate failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "tasks_created" in data
        assert "tasks" in data
        assert isinstance(data["tasks"], list)
        # Should create 12 tasks
        assert data["tasks_created"] == 12, f"Expected 12 tasks, got {data['tasks_created']}"
        print(f"PASS: Generated {data['tasks_created']} tasks, ai_powered={data.get('ai_powered')}")

    def test_generate_populates_board(self, authed):
        """After generate, board should have tasks."""
        board_resp = authed.get(f"{BASE_URL}/kanban/board", timeout=15)
        data = board_resp.json()
        total = data["total"]
        assert total >= 12, f"Board should have ≥12 tasks after generate, got {total}"
        print(f"PASS: Board has {total} tasks after generate")


# ===========================================================================
# 5. 2027 Future-Shock Simulator
# ===========================================================================

class TestFutureShock:
    """POST /simulator/future-shock – requires auth"""

    def test_future_shock_default_acceleration(self, authed):
        resp = authed.post(
            f"{BASE_URL}/simulator/future-shock",
            json={"acceleration": 50.0},
            timeout=15,
        )
        assert resp.status_code == 200, f"Future shock failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "adjusted_score" in data
        assert "skill_profiles" in data
        assert "risk_level" in data
        print(f"PASS: Future-shock – adjusted_score={data['adjusted_score']}, risk={data['risk_level']}")

    def test_future_shock_returns_delta(self, authed):
        resp = authed.post(
            f"{BASE_URL}/simulator/future-shock",
            json={"acceleration": 75.0},
            timeout=15,
        )
        data = resp.json()
        assert "delta" in data
        assert "original_score" in data
        assert isinstance(data["delta"], (int, float))
        print(f"PASS: Delta={data['delta']}")

    def test_future_shock_zero_acceleration(self, authed):
        resp = authed.post(
            f"{BASE_URL}/simulator/future-shock",
            json={"acceleration": 0.0},
            timeout=15,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["adjusted_score"] >= 0
        print(f"PASS: Zero acceleration score={data['adjusted_score']}")

    def test_future_shock_full_acceleration(self, authed):
        resp = authed.post(
            f"{BASE_URL}/simulator/future-shock",
            json={"acceleration": 100.0},
            timeout=15,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["adjusted_score"] >= 0
        assert data["risk_level"] in ("low", "medium", "high", "unknown")
        print(f"PASS: Full acceleration score={data['adjusted_score']}, risk={data['risk_level']}")

    def test_future_shock_invalid_acceleration(self, authed):
        resp = authed.post(
            f"{BASE_URL}/simulator/future-shock",
            json={"acceleration": 150.0},  # Out of range 0-100
            timeout=15,
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"
        print("PASS: 422 for out-of-range acceleration")

    def test_future_shock_without_auth(self):
        resp = requests.post(
            f"{BASE_URL}/simulator/future-shock",
            json={"acceleration": 50.0},
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        assert resp.status_code == 401
        print("PASS: 401 without auth")


# ===========================================================================
# 6. Recruiter Truth-Link (Public Profile Share)
# ===========================================================================

class TestPublicProfile:
    """POST /profile/generate-share-link + GET /public/:slug"""

    share_slug = None

    def test_generate_share_link_returns_200(self, authed):
        resp = authed.post(f"{BASE_URL}/profile/generate-share-link", timeout=15)
        assert resp.status_code == 200, f"Generate share link failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "share_slug" in data, "Missing share_slug"
        assert "share_url" in data, "Missing share_url"
        assert data["share_slug"], "share_slug is empty"
        assert data["share_url"], "share_url is empty"
        TestPublicProfile.share_slug = data["share_slug"]
        print(f"PASS: Share link generated – slug={data['share_slug']}, url={data['share_url']}")

    def test_share_link_is_permanent(self, authed):
        """Calling again should return the SAME slug (not regenerated)."""
        resp1 = authed.post(f"{BASE_URL}/profile/generate-share-link", timeout=15)
        slug1 = resp1.json().get("share_slug")
        resp2 = authed.post(f"{BASE_URL}/profile/generate-share-link", timeout=15)
        slug2 = resp2.json().get("share_slug")
        assert slug1 == slug2, f"Slug changed between calls: {slug1} != {slug2}"
        print(f"PASS: Share slug is permanent: {slug1}")

    def test_get_public_profile_by_slug(self):
        """GET /public/:slug should return public profile data."""
        assert TestPublicProfile.share_slug, "No slug from generate step"
        slug = TestPublicProfile.share_slug
        resp = requests.get(f"{BASE_URL}/public/{slug}", timeout=15)
        assert resp.status_code == 200, f"Public profile failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "username" in data
        assert "mri_score" in data
        assert "mri_band" in data
        assert "mri_components" in data
        comps = data["mri_components"]
        assert "federal_standards" in comps
        assert "market_demand" in comps
        assert "evidence_density" in comps
        print(f"PASS: Public profile – user={data['username']}, mri={data['mri_score']}, band={data['mri_band']}")

    def test_public_profile_no_auth_required(self):
        """Public profile endpoint should work without auth."""
        assert TestPublicProfile.share_slug, "No slug"
        slug = TestPublicProfile.share_slug
        resp = requests.get(f"{BASE_URL}/public/{slug}", timeout=15)
        assert resp.status_code == 200
        print("PASS: No auth required for public profile")

    def test_public_profile_not_found_404(self):
        resp = requests.get(f"{BASE_URL}/public/nonexistent-slug-xyz123abc", timeout=15)
        assert resp.status_code == 404
        print("PASS: 404 for non-existent slug")

    def test_generate_share_link_without_auth(self):
        resp = requests.post(
            f"{BASE_URL}/profile/generate-share-link",
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        assert resp.status_code == 401
        print("PASS: 401 without auth for generate-share-link")

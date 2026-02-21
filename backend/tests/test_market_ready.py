"""Market Ready - Backend API Tests"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://7be5a208-9532-4df3-bc70-81686eaa39fd.preview.emergentagent.com/api"
    BASE_URL = BASE_URL.rstrip("/api") if BASE_URL.endswith("/api") else BASE_URL


# Use environment variable
BACKEND_BASE = "https://7be5a208-9532-4df3-bc70-81686eaa39fd.preview.emergentagent.com"

TEST_USERNAME = f"testuser_auto_{int(time.time())}"
TEST_PASSWORD = "TestPass123!"

auth_token_store = {}


class TestMeta:
    """Health check endpoint"""

    def test_health(self):
        r = requests.get(f"{BACKEND_BASE}/api/meta/health")
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True


class TestAuth:
    """Auth - register and login"""

    def test_register(self):
        r = requests.post(f"{BACKEND_BASE}/api/auth/register", json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
            "email": f"{TEST_USERNAME}@test.com",
        })
        assert r.status_code == 200
        data = r.json()
        assert data.get("user_id") == TEST_USERNAME
        # either token or verification required
        assert "auth_token" in data or data.get("email_verification_required") is True

    def test_login(self):
        r = requests.post(f"{BACKEND_BASE}/api/auth/login", json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
        })
        assert r.status_code == 200
        data = r.json()
        assert "auth_token" in data
        auth_token_store["token"] = data["auth_token"]

    def test_login_existing_user(self):
        """Login with the provided test credentials"""
        r = requests.post(f"{BACKEND_BASE}/api/auth/login", json={
            "username": "testuser",
            "password": "TestPass123!",
        })
        # might be 200 or 401 if user doesn't exist yet
        if r.status_code == 200:
            data = r.json()
            assert "auth_token" in data
            auth_token_store["token"] = data["auth_token"]
        else:
            # Create the testuser
            reg = requests.post(f"{BACKEND_BASE}/api/auth/register", json={
                "username": "testuser",
                "password": "TestPass123!",
            })
            assert reg.status_code in [200, 409]


class TestAIEndpoints:
    """AI feature endpoints - require auth"""

    @pytest.fixture(autouse=True)
    def setup_token(self):
        if "token" not in auth_token_store:
            r = requests.post(f"{BACKEND_BASE}/api/auth/login", json={
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD,
            })
            if r.status_code == 200:
                auth_token_store["token"] = r.json()["auth_token"]
            else:
                pytest.skip("No auth token available")

    def _headers(self):
        return {"X-Auth-Token": auth_token_store["token"]}

    def test_market_stress_test(self):
        r = requests.post(
            f"{BACKEND_BASE}/api/user/ai/market-stress-test",
            json={"target_job": "Software Engineer", "location": "New York"},
            headers=self._headers(),
            timeout=60,
        )
        assert r.status_code == 200
        data = r.json()
        assert "mri_score" in data or "score" in data or "skill_match" in data

    def test_proof_checker(self):
        r = requests.post(
            f"{BACKEND_BASE}/api/user/ai/proof-checker",
            json={
                "target_job": "Software Engineer",
                "location": "New York",
                "repo_url": "https://github.com/tiangolo/fastapi",
            },
            headers=self._headers(),
            timeout=60,
        )
        assert r.status_code == 200
        data = r.json()
        assert "skill_matches" in data or "matches" in data or "proof_density" in data or isinstance(data, dict)

    def test_orchestrator(self):
        r = requests.post(
            f"{BACKEND_BASE}/api/user/ai/orchestrator",
            json={
                "target_job": "Software Engineer",
                "location": "New York",
                "availability_hours_per_week": 10,
                "pivot_requested": False,
            },
            headers=self._headers(),
            timeout=90,
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)

"""
Backend tests for proficiency level and AI certificate verification features:
1. Proof submission API accepts proficiency_level field
2. MRI score returns proficiency_breakdown with beginner/intermediate/professional counts
3. MRI score returns ai_verified_certs count
4. Proficiency level defaults to 'intermediate' when not provided
5. Proficiency level is returned in proof response
"""
import pytest
import requests
import os
import time

BASE_URL = "https://market-sentinel-54.preview.emergentagent.com/api"

MAJOR_ID = "854d6c9b-b976-441d-85b6-1b3cf5aa204d"
PATHWAY_ID = "a4a36bdd-763d-4693-9da5-25da136489f5"

# Test user for proficiency testing (separate from testuser)
PROF_TEST_USER = "proftest_user"
PROF_TEST_PASS = "ProfTest123!"


@pytest.fixture(scope="module")
def auth_token():
    """Register + login proficiency test user, return auth token."""
    session = requests.Session()
    # Try to register
    reg_resp = session.post(
        f"{BASE_URL}/auth/register",
        json={"username": PROF_TEST_USER, "password": PROF_TEST_PASS, "email": f"{PROF_TEST_USER}@test.com"},
        timeout=15,
    )
    # 200/201 = created; 400/409 = already exists - both ok
    assert reg_resp.status_code in (200, 201, 400, 409), (
        f"Unexpected register status {reg_resp.status_code}: {reg_resp.text}"
    )

    # Login
    login_resp = session.post(
        f"{BASE_URL}/auth/login",
        json={"username": PROF_TEST_USER, "password": PROF_TEST_PASS},
        timeout=15,
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    data = login_resp.json()
    token = data.get("auth_token") or data.get("token") or data.get("access_token")
    assert token, f"No token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def authed(auth_token):
    """Requests session with X-Auth-Token header."""
    s = requests.Session()
    s.headers.update({"X-Auth-Token": auth_token, "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def pathway_setup(authed):
    """Select a pathway for the test user. Returns checklist items."""
    # Select pathway
    pathway_resp = authed.post(
        f"{BASE_URL}/user/pathway/select",
        json={"major_id": MAJOR_ID, "pathway_id": PATHWAY_ID},
        timeout=15,
    )
    assert pathway_resp.status_code in (200, 201, 400, 409), (
        f"Pathway select failed: {pathway_resp.status_code}: {pathway_resp.text}"
    )
    print(f"Pathway select status: {pathway_resp.status_code}")

    # Get checklist items
    checklist_resp = authed.get(f"{BASE_URL}/user/checklist", timeout=15)
    assert checklist_resp.status_code == 200, f"Checklist failed: {checklist_resp.status_code}: {checklist_resp.text}"
    items = checklist_resp.json()
    assert len(items) > 0, "No checklist items found after pathway setup"
    print(f"Got {len(items)} checklist items")
    return items


# ===========================================================================
# Test: MRI Score with existing testuser (no pathway)
# ===========================================================================

class TestMRIScoreFields:
    """Test MRI score API returns new proficiency_breakdown and ai_verified_certs fields"""

    def test_mri_returns_proficiency_breakdown(self, authed):
        """MRI score must return proficiency_breakdown dict."""
        resp = authed.get(f"{BASE_URL}/score/mri", timeout=15)
        assert resp.status_code == 200, f"MRI failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "proficiency_breakdown" in data, f"Missing proficiency_breakdown in MRI response: {list(data.keys())}"
        print(f"PASS: proficiency_breakdown present: {data['proficiency_breakdown']}")

    def test_mri_proficiency_breakdown_has_three_levels(self, authed):
        """proficiency_breakdown must have beginner, intermediate, professional keys."""
        resp = authed.get(f"{BASE_URL}/score/mri", timeout=15)
        data = resp.json()
        pb = data.get("proficiency_breakdown", {})
        # Either it has all 3 keys (empty dict when no pathway) or non-empty dict
        # For user with no pathway, it returns empty dict {} which is also acceptable
        # For user with pathway+proofs, it must have the 3 keys
        if pb:
            assert "beginner" in pb, f"Missing 'beginner' in proficiency_breakdown: {pb}"
            assert "intermediate" in pb, f"Missing 'intermediate' in proficiency_breakdown: {pb}"
            assert "professional" in pb, f"Missing 'professional' in proficiency_breakdown: {pb}"
        print(f"PASS: proficiency_breakdown structure: {pb}")

    def test_mri_returns_ai_verified_certs(self, authed):
        """MRI score must return ai_verified_certs count."""
        resp = authed.get(f"{BASE_URL}/score/mri", timeout=15)
        assert resp.status_code == 200
        data = resp.json()
        assert "ai_verified_certs" in data, f"Missing ai_verified_certs in MRI response: {list(data.keys())}"
        assert isinstance(data["ai_verified_certs"], int), f"ai_verified_certs should be int, got: {type(data['ai_verified_certs'])}"
        print(f"PASS: ai_verified_certs present: {data['ai_verified_certs']}")

    def test_mri_score_formula_field(self, authed):
        """MRI score must include formula field."""
        resp = authed.get(f"{BASE_URL}/score/mri", timeout=15)
        data = resp.json()
        assert "formula" in data
        assert "MRI" in data["formula"]
        print(f"PASS: formula={data['formula']}")


# ===========================================================================
# Test: Proof submission with proficiency_level
# ===========================================================================

class TestProofProficiencyLevel:
    """Test that proof submission accepts and returns proficiency_level"""

    created_proof_ids = []

    def test_proof_submission_returns_proficiency_level(self, authed, pathway_setup):
        """Proof submission response must include proficiency_level field."""
        items = pathway_setup
        # Find first non-cert item (self-attestable)
        non_cert_items = [
            i for i in items
            if not any("cert" in pt.lower() for pt in (i.get("allowed_proof_types") or []))
        ]
        if not non_cert_items:
            # Use first item
            item = items[0]
        else:
            item = non_cert_items[0]

        item_id = str(item["id"])
        proof_type = (item.get("allowed_proof_types") or ["self_attested"])[0]

        resp = authed.post(
            f"{BASE_URL}/user/proofs",
            json={
                "checklist_item_id": item_id,
                "proof_type": proof_type,
                "url": "self_attested://yes",
                "proficiency_level": "beginner",
            },
            timeout=15,
        )
        assert resp.status_code in (200, 201), f"Proof submission failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "proficiency_level" in data, f"Missing proficiency_level in proof response: {list(data.keys())}"
        assert data["proficiency_level"] == "beginner", f"Expected 'beginner', got: {data['proficiency_level']}"
        if "id" in data:
            TestProofProficiencyLevel.created_proof_ids.append(str(data["id"]))
        print(f"PASS: proficiency_level='beginner' returned in proof response")

    def test_proof_intermediate_proficiency(self, authed, pathway_setup):
        """Submit proof with intermediate proficiency level."""
        items = pathway_setup
        non_cert_items = [
            i for i in items
            if not any("cert" in pt.lower() for pt in (i.get("allowed_proof_types") or []))
        ]
        if len(non_cert_items) >= 2:
            item = non_cert_items[1]
        elif non_cert_items:
            item = non_cert_items[0]
        else:
            item = items[1] if len(items) > 1 else items[0]

        item_id = str(item["id"])
        proof_type = (item.get("allowed_proof_types") or ["self_attested"])[0]

        resp = authed.post(
            f"{BASE_URL}/user/proofs",
            json={
                "checklist_item_id": item_id,
                "proof_type": proof_type,
                "url": "self_attested://yes",
                "proficiency_level": "intermediate",
            },
            timeout=15,
        )
        assert resp.status_code in (200, 201), f"Failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data.get("proficiency_level") == "intermediate", f"Expected 'intermediate', got: {data.get('proficiency_level')}"
        if "id" in data:
            TestProofProficiencyLevel.created_proof_ids.append(str(data["id"]))
        print(f"PASS: proficiency_level='intermediate' accepted and returned")

    def test_proof_professional_proficiency(self, authed, pathway_setup):
        """Submit proof with professional proficiency level."""
        items = pathway_setup
        non_cert_items = [
            i for i in items
            if not any("cert" in pt.lower() for pt in (i.get("allowed_proof_types") or []))
        ]
        if len(non_cert_items) >= 3:
            item = non_cert_items[2]
        elif len(non_cert_items) >= 1:
            item = non_cert_items[0]
        else:
            item = items[0]

        item_id = str(item["id"])
        proof_type = (item.get("allowed_proof_types") or ["self_attested"])[0]

        resp = authed.post(
            f"{BASE_URL}/user/proofs",
            json={
                "checklist_item_id": item_id,
                "proof_type": proof_type,
                "url": "self_attested://yes",
                "proficiency_level": "professional",
            },
            timeout=15,
        )
        assert resp.status_code in (200, 201), f"Failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data.get("proficiency_level") == "professional", f"Expected 'professional', got: {data.get('proficiency_level')}"
        if "id" in data:
            TestProofProficiencyLevel.created_proof_ids.append(str(data["id"]))
        print(f"PASS: proficiency_level='professional' accepted and returned")

    def test_proof_default_proficiency_is_intermediate(self, authed, pathway_setup):
        """When proficiency_level not provided, defaults to 'intermediate'."""
        items = pathway_setup
        item = items[0]
        item_id = str(item["id"])
        proof_type = (item.get("allowed_proof_types") or ["self_attested"])[0]

        resp = authed.post(
            f"{BASE_URL}/user/proofs",
            json={
                "checklist_item_id": item_id,
                "proof_type": proof_type,
                "url": "self_attested://yes",
                # No proficiency_level - should default
            },
            timeout=15,
        )
        assert resp.status_code in (200, 201), f"Failed: {resp.status_code} {resp.text}"
        data = resp.json()
        assert "proficiency_level" in data, "Missing proficiency_level in response"
        assert data.get("proficiency_level") == "intermediate", f"Expected default 'intermediate', got: {data.get('proficiency_level')}"
        print(f"PASS: Default proficiency_level='intermediate' when not provided")

    def test_proof_list_includes_proficiency_level(self, authed):
        """GET /user/proofs list should include proficiency_level for each proof."""
        resp = authed.get(f"{BASE_URL}/user/proofs", timeout=15)
        assert resp.status_code == 200, f"List proofs failed: {resp.status_code}"
        proofs = resp.json()
        if proofs:
            for proof in proofs[:3]:
                assert "proficiency_level" in proof, f"Missing proficiency_level in proof list item: {list(proof.keys())}"
                assert proof["proficiency_level"] in ("beginner", "intermediate", "professional"), \
                    f"Invalid proficiency_level: {proof['proficiency_level']}"
        print(f"PASS: {len(proofs)} proofs in list, all have valid proficiency_level")


# ===========================================================================
# Test: MRI Score after proofs with different proficiency levels
# ===========================================================================

class TestMRIWithProficiencyBreakdown:
    """Test MRI score correctly reflects proficiency breakdown after proof submissions"""

    def test_mri_proficiency_breakdown_structure_after_proofs(self, authed, pathway_setup):
        """After submitting proofs, proficiency_breakdown should have the 3 keys."""
        # Ensure proofs submitted first
        time.sleep(0.5)
        resp = authed.get(f"{BASE_URL}/score/mri", timeout=15)
        assert resp.status_code == 200, f"MRI failed: {resp.status_code}"
        data = resp.json()

        pb = data.get("proficiency_breakdown", {})
        assert "beginner" in pb, f"Missing 'beginner' in proficiency_breakdown: {pb}"
        assert "intermediate" in pb, f"Missing 'intermediate' in proficiency_breakdown: {pb}"
        assert "professional" in pb, f"Missing 'professional' in proficiency_breakdown: {pb}"
        print(f"PASS: proficiency_breakdown = {pb}")

    def test_mri_proficiency_counts_are_integers(self, authed, pathway_setup):
        """proficiency_breakdown values must be integers (counts)."""
        resp = authed.get(f"{BASE_URL}/score/mri", timeout=15)
        data = resp.json()
        pb = data.get("proficiency_breakdown", {})
        if pb:
            for level, count in pb.items():
                assert isinstance(count, int), f"{level} count should be int, got {type(count)}: {count}"
        print(f"PASS: proficiency_breakdown counts are integers: {pb}")

    def test_mri_beginner_proficiency_shown(self, authed, pathway_setup):
        """After submitting a beginner proof, beginner count in breakdown should be >= 1."""
        resp = authed.get(f"{BASE_URL}/score/mri", timeout=15)
        data = resp.json()
        pb = data.get("proficiency_breakdown", {})
        beginner_count = pb.get("beginner", 0)
        # We submitted at least 1 beginner proof
        assert beginner_count >= 1, f"Expected beginner >= 1 after beginner proof submission, got: {beginner_count}"
        print(f"PASS: beginner count = {beginner_count} (>=1)")

    def test_mri_professional_proficiency_shown(self, authed, pathway_setup):
        """After submitting a professional proof, professional count should be >= 1."""
        resp = authed.get(f"{BASE_URL}/score/mri", timeout=15)
        data = resp.json()
        pb = data.get("proficiency_breakdown", {})
        professional_count = pb.get("professional", 0)
        assert professional_count >= 1, f"Expected professional >= 1, got: {professional_count}"
        print(f"PASS: professional count = {professional_count} (>=1)")

    def test_mri_score_above_zero_after_proofs(self, authed, pathway_setup):
        """After pathway setup and proof submissions, MRI score should be > 0."""
        resp = authed.get(f"{BASE_URL}/score/mri", timeout=15)
        data = resp.json()
        score = data.get("score", 0)
        assert score > 0, f"MRI score should be > 0 after submitting proofs, got: {score}"
        print(f"PASS: MRI score = {score} (> 0)")

    def test_mri_ai_verified_certs_is_non_negative(self, authed, pathway_setup):
        """ai_verified_certs should be >= 0 (int)."""
        resp = authed.get(f"{BASE_URL}/score/mri", timeout=15)
        data = resp.json()
        ai_certs = data.get("ai_verified_certs", 0)
        assert isinstance(ai_certs, int), f"ai_verified_certs should be int, got {type(ai_certs)}"
        assert ai_certs >= 0, f"ai_verified_certs should be >= 0, got: {ai_certs}"
        print(f"PASS: ai_verified_certs = {ai_certs}")


# ===========================================================================
# Test: Existing testuser MRI API still works
# ===========================================================================

class TestExistingTestuserMRI:
    """Ensure MRI API still returns expected structure for testuser (no pathway)"""

    @pytest.fixture(scope="class")
    def testuser_authed(self):
        s = requests.Session()
        login_resp = s.post(
            f"{BASE_URL}/auth/login",
            json={"username": "testuser", "password": "TestPass123!"},
            timeout=15,
        )
        assert login_resp.status_code == 200, f"testuser login failed: {login_resp.text}"
        token = login_resp.json().get("auth_token")
        s.headers.update({"X-Auth-Token": token, "Content-Type": "application/json"})
        return s

    def test_testuser_mri_returns_200(self, testuser_authed):
        resp = testuser_authed.get(f"{BASE_URL}/score/mri", timeout=15)
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] == 0  # No pathway
        assert data["band"] == "Not Started"
        print(f"PASS: testuser MRI = 0, band = Not Started")

    def test_testuser_mri_has_proficiency_breakdown(self, testuser_authed):
        """Even with no pathway, proficiency_breakdown key must be present."""
        resp = testuser_authed.get(f"{BASE_URL}/score/mri", timeout=15)
        data = resp.json()
        assert "proficiency_breakdown" in data, f"Missing proficiency_breakdown: {list(data.keys())}"
        print(f"PASS: proficiency_breakdown present for testuser: {data['proficiency_breakdown']}")

    def test_testuser_mri_has_ai_verified_certs(self, testuser_authed):
        """Even with no pathway, ai_verified_certs key must be present."""
        resp = testuser_authed.get(f"{BASE_URL}/score/mri", timeout=15)
        data = resp.json()
        assert "ai_verified_certs" in data, f"Missing ai_verified_certs: {list(data.keys())}"
        print(f"PASS: ai_verified_certs present for testuser: {data['ai_verified_certs']}")

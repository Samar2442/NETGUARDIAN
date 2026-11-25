from unittest.mock import MagicMock, patch
import pytest
from app.models import CredentialVault, DeviceConnectionProfile
from app.services.network_connector import resolve_allowlisted_command
from app.services.ssh_connector import HostKeyMismatchError, SSHConnector, _StrictFingerprintPolicy


def _login(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_credential_vault_rbac_encryption_and_redaction(client, db):
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")
    eng_tok = _login(client, "neteng", "CiscoEngineer2026!")
    admin_tok = _login(client, "admin", "NetGuardianAdmin2026!")

    v_h = {"Authorization": f"Bearer {viewer_tok}"}
    e_h = {"Authorization": f"Bearer {eng_tok}"}
    a_h = {"Authorization": f"Bearer {admin_tok}"}

    # Only admin can create or list credentials
    assert client.post(
        "/api/v1/integrations/credentials",
        json={"name": "lab-ssh", "username": "cisco", "password": "LabSecretPassword99!"},
        headers=e_h,
    ).status_code == 403
    assert client.get("/api/v1/integrations/credentials", headers=v_h).status_code == 403

    cred_res = client.post(
        "/api/v1/integrations/credentials",
        json={"name": "lab-ssh", "username": "cisco", "password": "LabSecretPassword99!"},
        headers=a_h,
    )
    assert cred_res.status_code == 201
    cred_body = cred_res.json()
    assert "LabSecretPassword99!" not in str(cred_body)
    cred_ref = cred_body["credential_ref"]

    # Stored encrypted in DB (not plaintext)
    row = db.query(CredentialVault).filter(CredentialVault.credential_ref == cred_ref).first()
    assert row.encrypted_password != "LabSecretPassword99!"

    # Approved destination enforcement & PRODUCTION gate disabled by default
    assert client.post(
        "/api/v1/integrations/profiles",
        json={
            "device_name": "UNAPPROVED-EXT",
            "management_ip": "8.8.8.8",
            "credential_ref": cred_ref,
            "environment": "LAB",
        },
        headers=a_h,
    ).status_code == 403

    assert client.post(
        "/api/v1/integrations/profiles",
        json={
            "device_name": "PROD-RTR-01",
            "management_ip": "10.10.10.1",
            "credential_ref": cred_ref,
            "environment": "PRODUCTION",
        },
        headers=a_h,
    ).status_code == 403

    prof_res = client.post(
        "/api/v1/integrations/profiles",
        json={
            "device_name": "LAB-IOS-SW-01",
            "management_ip": "10.200.1.10",
            "device_platform": "cisco_ios",
            "protocol": "SSH",
            "port": 22,
            "credential_ref": cred_ref,
            "environment": "LAB",
            "timeout_seconds": 5,
            "max_retries": 2,
            "ssh_host_key_fingerprint": "SHA256:MockExpectedFingerprint",
        },
        headers=a_h,
    )
    assert prof_res.status_code == 201
    prof_id = prof_res.json()["id"]
    assert "LabSecretPassword99!" not in str(prof_res.json())

    # Command allowlist rejects arbitrary CLI
    with pytest.raises(ValueError):
        resolve_allowlisted_command("conf t; reload")
    assert client.get(
        f"/api/v1/integrations/profiles/{prof_id}/device-info?operation=reload",
        headers=v_h,
    ).status_code == 400

    # Capabilities report NETCONF/RESTCONF unsupported on cisco_ios
    caps = client.post(f"/api/v1/integrations/profiles/{prof_id}/capabilities", headers=e_h)
    assert caps.status_code == 200
    assert caps.json()["capabilities"]["NETCONF"]["status"] == "UNSUPPORTED"
    assert caps.json()["capabilities"]["RESTCONF"]["status"] == "UNSUPPORTED"

    # Mocked SSH test_connection & read-only interface_status
    with patch.object(SSHConnector, "test_connection", return_value={"connected": True, "host_key_verified": True}), \
         patch.object(SSHConnector, "run_read_only_operation", return_value={
             "operation": "interface_status",
             "command": "show ip interface brief",
             "structured_data": [{"interface": "GigabitEthernet0/1", "ip_address": "10.200.1.10", "admin_status": "up", "oper_status": "up"}],
             "stderr": "",
         }):
        t_res = client.post(f"/api/v1/integrations/profiles/{prof_id}/test", headers=e_h)
        assert t_res.status_code == 200
        assert t_res.json()["connected"] is True

        if_res = client.get(f"/api/v1/integrations/profiles/{prof_id}/interfaces", headers=v_h)
        assert if_res.status_code == 200
        assert if_res.json()["structured_data"][0]["interface"] == "GigabitEthernet0/1"


def test_ssh_host_key_mismatch_and_timeout_retry():
    policy = _StrictFingerprintPolicy("SHA256:ExpectedKey123")
    fake_key = MagicMock()
    fake_key.asbytes.return_value = b"different-host-key-bytes"
    with pytest.raises(HostKeyMismatchError):
        policy.missing_host_key(MagicMock(), "10.200.1.10", fake_key)

    # Timeout & retry limit enforcement
    conn = SSHConnector("10.200.1.10", 22, "cisco", "pass", "SHA256:ExpectedKey123", timeout_seconds=2, max_retries=2)
    with patch("paramiko.SSHClient.connect", side_effect=TimeoutError("timed out")) as mock_conn:
        with pytest.raises(TimeoutError):
            conn.test_connection()
        assert mock_conn.call_count == 2

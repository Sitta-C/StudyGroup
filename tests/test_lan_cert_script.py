"""LAN certificate issuance uses a temporary CA and never replaces keys."""

from pathlib import Path
import shutil
import subprocess

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "generate-lan-cert.sh"


@pytest.fixture
def issuer(tmp_path, certificates):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    script = scripts / SOURCE.name
    shutil.copyfile(SOURCE, script)
    certs = tmp_path / "certs"
    certs.mkdir()
    for name in ("ca.key", "ca.crt"):
        shutil.copyfile(certificates / name, certs / name)
    return script, certs


def test_lan_cert_has_requested_sans_and_refuses_overwrite(issuer):
    script, certs = issuer
    subprocess.run(["bash", script, "IP:192.168.1.20", "DNS:studygroup.local"], check=True, capture_output=True)
    for flag, name in (("-verify_ip", "192.168.1.20"), ("-verify_hostname", "studygroup.local")):
        subprocess.run(["openssl", "verify", "-CAfile", certs / "ca.crt", flag, name, certs / "lan/server.crt"], check=True, capture_output=True)
    original = (certs / "lan/server.key").read_bytes()
    repeated = subprocess.run(["bash", script, "IP:192.168.1.21"], capture_output=True)
    assert repeated.returncode != 0
    assert (certs / "lan/server.key").read_bytes() == original
    wrong = subprocess.run(["openssl", "verify", "-CAfile", certs / "ca.crt", "-verify_ip", "192.168.1.21", certs / "lan/server.crt"], capture_output=True)
    assert wrong.returncode != 0


@pytest.mark.parametrize("name", ["IP:192.168.1.20\nDNS:evil", "DNS:test,IP:1.2.3.4", "invalid", "IP:999.999.1.1"])
def test_invalid_san_does_not_publish_certificate(issuer, name):
    script, certs = issuer
    result = subprocess.run(["bash", script, name], capture_output=True)
    assert result.returncode != 0
    assert not (certs / "lan/server.crt").exists()
    assert not (certs / "lan/server.key").exists()

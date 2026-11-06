"""Shared temporary SQLite and real TLS fixtures; never use data/ or .env."""

import subprocess

import pytest

from server.config import ServerConfig
from server.database import Database, create_user
from server.main import TLSServer


@pytest.fixture
def database(tmp_path):
    db = Database(tmp_path / "ข้อมูล" / "studygroup.db")
    db.initialize()
    return db


@pytest.fixture
def conn(database):
    with database.connect() as connection:
        yield connection


@pytest.fixture
def users(conn):
    # Opaque storage fixtures, not plaintext passwords or CP04 auth evidence.
    return [create_user(conn, name, "test-hash")["id"] for name in ("Alice", "Bob", "Carol")]


@pytest.fixture(scope="session")
def certificates(tmp_path_factory):
    root = tmp_path_factory.mktemp("tls-certificates")

    def openssl(*args):
        subprocess.run(["openssl", *map(str, args)], cwd=root, check=True, capture_output=True)

    extensions = root / "extensions.cnf"
    extensions.write_text(
        "[ca]\nbasicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\n"
        "subjectKeyIdentifier=hash\n"
        "[server]\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n"
        "extendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost,IP:127.0.0.1\n"
        "authorityKeyIdentifier=keyid,issuer\nsubjectKeyIdentifier=hash\n"
    )
    openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
            "-subj", "/CN=StudyGroup Test CA", "-keyout", "ca.key", "-out", "ca.crt",
            "-config", extensions, "-extensions", "ca")
    openssl("req", "-new", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=localhost",
            "-keyout", "server.key", "-out", "server.csr")
    openssl("x509", "-req", "-in", "server.csr", "-CA", "ca.crt", "-CAkey", "ca.key",
            "-set_serial", "1", "-days", "2", "-extfile", extensions,
            "-extensions", "server", "-out", "server.crt")
    (root / "index").write_text("")
    (root / "serial").write_text("10\n")
    ca_config = root / "ca.cnf"
    ca_config.write_text(
        "[ca]\ndefault_ca=test\n[test]\ndatabase=index\nserial=serial\nnew_certs_dir=.\n"
        "certificate=ca.crt\nprivate_key=ca.key\ndefault_md=sha256\npolicy=policy\n"
        "[policy]\ncommonName=supplied\n"
    )
    openssl("ca", "-batch", "-notext", "-config", ca_config,
            "-startdate", "20000101000000Z", "-enddate", "20010101000000Z",
            "-extfile", extensions, "-extensions", "server", "-in", "server.csr", "-out", "expired.crt")
    wrong_names = root / "wrong-names.cnf"
    wrong_names.write_text(extensions.read_text().replace("DNS:localhost,IP:127.0.0.1", "DNS:wrong.invalid"))
    openssl("x509", "-req", "-in", "server.csr", "-CA", "ca.crt", "-CAkey", "ca.key",
            "-set_serial", "3", "-days", "2", "-extfile", wrong_names,
            "-extensions", "server", "-out", "hostname.crt")
    openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2",
            "-subj", "/CN=Unrelated CA", "-keyout", "other.key", "-out", "other.crt",
            "-config", extensions, "-extensions", "ca")
    return root


@pytest.fixture
def server_factory(tmp_path, certificates):
    servers = []

    def start(*, limits=None, limiter=None, certificate="server.crt"):
        config = ServerConfig(
            host="127.0.0.1", port=0, data_dir=tmp_path / str(len(servers)),
            tls_cert=certificates / certificate, tls_key=certificates / "server.key",
        )
        server = TLSServer(config, limits=limits, limiter=limiter).start()
        servers.append(server)
        return server

    yield start
    for server in reversed(servers):
        server.stop()
        assert server.registry.users() == []
        assert not server._connections
        assert not server._accept_thread.is_alive()


@pytest.fixture
def server(server_factory):
    return server_factory()

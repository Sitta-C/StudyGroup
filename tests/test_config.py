"""Config acceptance tests use temporary paths, never the developer's secrets."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from server.config import ServerConfig
from shared.config import PROJECT_ROOT, ConfigError, read_path


@pytest.fixture
def config_root(tmp_path):
    certs = tmp_path / "certs"
    certs.mkdir()
    # CP01 checks paths and readability, not certificate contents/handshakes.
    for name in ("server.crt", "server.key"):
        (certs / name).write_text("test placeholder", encoding="utf-8")
    return tmp_path


def test_defaults_without_environment_variables(config_root):
    server = ServerConfig.from_env({}, base_dir=config_root)

    assert (server.host, server.port) == ("127.0.0.1", 5000)
    assert server.tls_cert == config_root / "certs/server.crt"
    assert server.tls_key == config_root / "certs/server.key"
    assert server.data_dir == config_root / "data"
    assert server.database_path == config_root / "data/studygroup.db"
    assert server.uploads_dir == config_root / "data/uploads"
    assert (server.ai_provider, server.ai_model, server.ai_api_key) == (None, None, None)
    assert not server.data_dir.exists()


def test_environment_overrides(config_root):
    env = {
        "STUDYGROUP_HOST": "chat.example.com",
        "STUDYGROUP_PORT": "65432",
        "STUDYGROUP_TLS_CERT": "certs/../certs/server.crt",
        "STUDYGROUP_TLS_KEY": str(config_root / "certs/server.key"),
        "STUDYGROUP_DATA_DIR": "ข้อมูล/แชต",
        "STUDYGROUP_AI_PROVIDER": "example-provider",
        "STUDYGROUP_AI_MODEL": "example-model",
        "STUDYGROUP_AI_API_KEY": "test-secret-do-not-log",
    }
    original = env.copy()
    server = ServerConfig.from_env(env, base_dir=config_root)

    assert (server.host, server.port) == ("chat.example.com", 65432)
    assert server.tls_cert == config_root / "certs/server.crt"
    assert server.tls_key == config_root / "certs/server.key"
    assert server.data_dir == config_root / "ข้อมูล/แชต"
    assert server.ai_provider == "example-provider"
    assert server.ai_model == "example-model"
    assert server.ai_api_key == env["STUDYGROUP_AI_API_KEY"]
    assert env["STUDYGROUP_AI_API_KEY"] not in repr(server)
    assert env == original
    assert not server.data_dir.exists()


def test_reads_environment_at_call_time_and_honors_empty_mapping(config_root, monkeypatch):
    monkeypatch.setenv("STUDYGROUP_PORT", "6010")
    assert ServerConfig.from_env(base_dir=config_root).port == 6010
    monkeypatch.setenv("STUDYGROUP_PORT", "6020")
    assert ServerConfig.from_env(base_dir=config_root).port == 6020
    assert ServerConfig.from_env({}, base_dir=config_root).port == 5000


@pytest.mark.parametrize("port", ["", " ", "0", "-1", "65536", "5000.0", "abc", "5_000", "５０００"])
def test_invalid_ports(port, config_root):
    with pytest.raises(ConfigError, match="STUDYGROUP_PORT.*1 and 65535"):
        ServerConfig.from_env({"STUDYGROUP_PORT": port}, base_dir=config_root)


@pytest.mark.parametrize("port", ["1", "65535", " 5001 "])
def test_valid_port_boundaries(port, config_root):
    assert ServerConfig.from_env({"STUDYGROUP_PORT": port}, base_dir=config_root).port == int(port)


@pytest.mark.parametrize("host", ["localhost", "chat.example.com", "127.0.0.1", "::1", "0.0.0.0", "::"])
def test_valid_hosts(host, config_root):
    assert ServerConfig.from_env({"STUDYGROUP_HOST": host}, base_dir=config_root).host == host


@pytest.mark.parametrize("host", ["", " ", "https://localhost", "localhost:5000", "bad host", "bad\x00host"])
def test_invalid_hosts(host, config_root):
    with pytest.raises(ConfigError, match="STUDYGROUP_HOST"):
        ServerConfig.from_env({"STUDYGROUP_HOST": host}, base_dir=config_root)


@pytest.mark.parametrize("name", ["STUDYGROUP_TLS_CERT", "STUDYGROUP_TLS_KEY"])
@pytest.mark.parametrize("path", ["missing.pem", "certs", "bad\x00path"])
def test_invalid_tls_paths(name, path, config_root):
    with pytest.raises(ConfigError, match=name):
        ServerConfig.from_env({name: path}, base_dir=config_root)


@pytest.mark.parametrize("name", ["STUDYGROUP_TLS_CERT", "STUDYGROUP_TLS_KEY", "STUDYGROUP_DATA_DIR"])
@pytest.mark.parametrize("path", ["", " "])
def test_required_paths_cannot_be_empty(name, path, config_root):
    with pytest.raises(ConfigError, match=name):
        ServerConfig.from_env({name: path}, base_dir=config_root)


@pytest.mark.parametrize("path", ["certs/server.crt", "certs/server.crt/child", "bad\x00dir"])
def test_invalid_data_directory(path, config_root):
    with pytest.raises(ConfigError, match="STUDYGROUP_DATA_DIR"):
        ServerConfig.from_env({"STUDYGROUP_DATA_DIR": path}, base_dir=config_root)


def test_existing_data_directory_and_absolute_override(config_root, tmp_path):
    data = tmp_path / "existing-data"
    data.mkdir()
    marker = data / "keep.txt"
    marker.write_text("existing data", encoding="utf-8")
    config = ServerConfig.from_env({"STUDYGROUP_DATA_DIR": str(data)}, base_dir=config_root)
    assert config.data_dir == data
    assert marker.read_text(encoding="utf-8") == "existing data"
    assert list(data.iterdir()) == [marker]


def test_unreadable_tls_file_is_config_error(config_root, monkeypatch):
    def denied_open(*args, **kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "open", denied_open)
    with pytest.raises(ConfigError, match="STUDYGROUP_TLS_CERT.*permissions"):
        ServerConfig.from_env({}, base_dir=config_root)


def test_unwritable_data_directory_is_config_error(config_root, monkeypatch):
    monkeypatch.setattr(os, "access", lambda *args: False)
    with pytest.raises(ConfigError, match="STUDYGROUP_DATA_DIR.*writable"):
        ServerConfig.from_env({}, base_dir=config_root)
    assert not (config_root / "data").exists()


def test_relative_paths_do_not_depend_on_working_directory(config_root, tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    server = ServerConfig.from_env({}, base_dir=config_root)
    assert server.tls_cert == config_root / "certs/server.crt"
    assert server.tls_key == config_root / "certs/server.key"
    assert server.data_dir == config_root / "data"


def test_home_paths_are_expanded():
    path = read_path("~/studygroup-config-test", "STUDYGROUP_DATA_DIR", PROJECT_ROOT)
    assert path == (Path.home() / "studygroup-config-test").resolve()


def test_missing_default_tls_files_fail_clearly(tmp_path):
    with pytest.raises(ConfigError, match="STUDYGROUP_TLS_CERT"):
        ServerConfig.from_env({}, base_dir=tmp_path)


def test_blank_ai_settings_do_not_block_server(config_root):
    config = ServerConfig.from_env(
        {name: " " for name in ("STUDYGROUP_AI_PROVIDER", "STUDYGROUP_AI_MODEL", "STUDYGROUP_AI_API_KEY")},
        base_dir=config_root,
    )
    assert (config.ai_provider, config.ai_model, config.ai_api_key) == (None, None, None)


def test_imports_do_not_read_config_or_create_runtime_files(tmp_path):
    code = (
        "import server, shared; "
        "from server.config import ServerConfig; print('Imports OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": str(PROJECT_ROOT),
            "PYTHONDONTWRITEBYTECODE": "1",
            "STUDYGROUP_PORT": "invalid",
            "STUDYGROUP_DATA_DIR": str(tmp_path / "must-not-create"),
            "STUDYGROUP_TLS_CERT": "missing-cert",
        },
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "Imports OK"
    assert list(tmp_path.iterdir()) == []

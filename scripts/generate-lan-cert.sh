#!/usr/bin/env bash
# Issue an additional LAN certificate using the existing private development CA.
# Example: bash scripts/generate-lan-cert.sh IP:192.168.1.20 DNS:studygroup.local
set -euo pipefail
umask 077
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
if [[ $# -eq 0 ]]; then
    echo 'Usage: generate-lan-cert.sh IP:192.168.1.20 [DNS:studygroup.local ...]' >&2
    exit 1
fi
for name in "$@"; do
    case "$name" in
        IP:*) [[ "${name#IP:}" =~ ^[0-9A-Fa-f:.]+$ ]] || { echo 'Invalid IP SAN' >&2; exit 1; } ;;
        DNS:*) [[ "${name#DNS:}" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*$ ]] || { echo 'Invalid DNS SAN' >&2; exit 1; } ;;
        *) echo 'Each name must start with IP: or DNS:' >&2; exit 1 ;;
    esac
done
[[ -r certs/ca.crt && -r certs/ca.key ]] || { echo 'Create the local CA first with generate-dev-certs.sh' >&2; exit 1; }
# mkdir is the no-overwrite guard: never replace an existing LAN trust setup.
mkdir certs/lan || { echo 'certs/lan already exists; no files were replaced.' >&2; exit 1; }
scratch_dir="$(mktemp -d "$project_dir/certs/.lan.XXXXXX")"
cleanup() { rm -rf -- "$scratch_dir"; rmdir certs/lan 2>/dev/null || true; }
trap cleanup EXIT
names="$(IFS=,; echo "$*")"
cat > "$scratch_dir/extensions.cnf" <<CONFIG
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=$names
CONFIG
openssl req -new -newkey rsa:3072 -nodes -sha256 -subj /CN=StudyGroup-LAN \
    -keyout "$scratch_dir/server.key" -out "$scratch_dir/server.csr"
openssl x509 -req -sha256 -days 365 -in "$scratch_dir/server.csr" \
    -CA certs/ca.crt -CAkey certs/ca.key -set_serial "0x$(openssl rand -hex 16)" \
    -extfile "$scratch_dir/extensions.cnf" -out "$scratch_dir/server.crt"
openssl verify -CAfile certs/ca.crt "$scratch_dir/server.crt"
for name in server.key server.crt; do
    mv -- "$scratch_dir/$name" "certs/lan/$name"
done
echo 'Created certs/lan/server.crt and server.key. Share only certs/ca.crt with clients.'

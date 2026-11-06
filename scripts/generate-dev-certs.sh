#!/usr/bin/env bash
# Generate a private development CA and a localhost server certificate.
set -euo pipefail
umask 077

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
command -v openssl >/dev/null
mkdir -p certs

for name in ca.key ca.crt server.key server.crt; do
    if [[ -e "certs/$name" ]]; then
        echo "Existing certs/$name found; no certificates were replaced." >&2
        echo "Use the existing certificates or move them aside before regenerating." >&2
        exit 1
    fi
done

scratch_dir="$(mktemp -d "$project_dir/certs/.generate.XXXXXX")"
trap 'rm -rf -- "$scratch_dir"' EXIT

cat > "$scratch_dir/openssl.cnf" <<'CONFIG'
[req]
distinguished_name = dn
prompt = no

[dn]
CN = StudyGroup Local Development CA

[ca]
basicConstraints = critical,CA:TRUE,pathlen:0
keyUsage = critical,keyCertSign,cRLSign
subjectKeyIdentifier = hash

[server]
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer
subjectAltName = @names

[names]
DNS.1 = localhost
IP.1 = 127.0.0.1
IP.2 = ::1
CONFIG

openssl req -x509 -newkey rsa:3072 -nodes -sha256 -days 3650 \
    -config "$scratch_dir/openssl.cnf" -extensions ca \
    -keyout "$scratch_dir/ca.key" -out "$scratch_dir/ca.crt"
openssl req -new -newkey rsa:3072 -nodes -sha256 \
    -config "$scratch_dir/openssl.cnf" -subj /CN=localhost \
    -keyout "$scratch_dir/server.key" -out "$scratch_dir/server.csr"
openssl x509 -req -sha256 -days 365 \
    -in "$scratch_dir/server.csr" \
    -CA "$scratch_dir/ca.crt" -CAkey "$scratch_dir/ca.key" \
    -set_serial "0x$(openssl rand -hex 16)" \
    -extfile "$scratch_dir/openssl.cnf" -extensions server \
    -out "$scratch_dir/server.crt"
openssl verify -CAfile "$scratch_dir/ca.crt" \
    -verify_hostname localhost "$scratch_dir/server.crt"

for name in ca.key ca.crt server.key server.crt; do
    mv -- "$scratch_dir/$name" "certs/$name"
done
echo "Created local development certificates in certs/."
echo "Trust certs/ca.crt explicitly in the client; keep both private keys secret."

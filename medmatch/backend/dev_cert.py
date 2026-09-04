"""Generate a self-signed TLS cert with the machine's LAN IP as SAN.

Needed because phone browsers only expose the camera (barcode/OCR scanning)
inside a secure context: https://. Run once per network, then start the server
with --ssl-certfile/--ssl-keyfile (see start_https.bat).

Usage:
    python backend/dev_cert.py            # writes backend/data/dev_cert.pem + dev_key.pem
"""
from __future__ import annotations

import datetime
import ipaddress
import socket
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "MedMatch Dev")])
    now = datetime.datetime.now(datetime.timezone.utc)
    san = x509.SubjectAlternativeName(
        [
            x509.DNSName("localhost"),
            x509.IPAddress(ipaddress.ip_address(lan_ip())),
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(san, critical=False)
        .sign(key, hashes.SHA256())
    )

    out = Path(__file__).parent / "data"
    out.mkdir(exist_ok=True)
    (out / "dev_key.pem").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    (out / "dev_cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"cert for localhost + {lan_ip()} -> {out}")


if __name__ == "__main__":
    main()

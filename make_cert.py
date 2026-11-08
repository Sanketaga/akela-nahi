"""Create a self-signed HTTPS certificate so a phone on the same Wi-Fi can use the microphone.

Phones only allow the microphone on https pages (or on localhost). Run once:
    .venv\\Scripts\\python make_cert.py
Then start the server with start_https.bat and open the address it prints on the parent's phone.
The phone will warn that the certificate is not trusted: tap "Advanced" -> "Proceed". That is
expected for a self-made certificate on your own network."""
import datetime
import ipaddress
import socket
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

OUT = Path(__file__).resolve().parent / "data"


def local_ips() -> list[str]:
    ips = {"127.0.0.1"}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # no packet is sent; this just picks the Wi-Fi address
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(ips)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ips = local_ips()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Akela Nahi (local)")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=90))
        .add_extension(x509.SubjectAlternativeName(
            [x509.DNSName("localhost")] + [x509.IPAddress(ipaddress.ip_address(i)) for i in ips]), critical=False)
        .sign(key, hashes.SHA256())
    )
    (OUT / "key.pem").write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
    (OUT / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print("Certificate created in", OUT)
    for ip in ips:
        if ip != "127.0.0.1":
            print(f"On the parent's phone (same Wi-Fi) open:  https://{ip}:8443/elder")
            print(f"On your phone/laptop open:                https://{ip}:8443/family")


if __name__ == "__main__":
    main()

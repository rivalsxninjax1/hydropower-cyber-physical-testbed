"""
Step 1 of the manual attack workflow: network reconnaissance.

Run manually from inside the attacker container:
    docker compose exec attacker python3 tools/network_scan.py

This does NOT know in advance that a PLC exists at any particular
address — it discovers the local subnet from its own network
interface, then scans it with nmap for open ports. This mirrors a
real attacker's actual starting position: on a network, but with no
prior knowledge of what's on it.
"""

import socket
import subprocess
import sys


def get_own_ip() -> str:
    # A quick trick that needs no external connectivity: opening a UDP
    # "connection" doesn't actually send packets, it just makes the OS
    # pick a local address for that route, which we then read back.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def derive_subnet_cidr(ip: str) -> str:
    octets = ip.split(".")
    return f"{octets[0]}.{octets[1]}.{octets[2]}.0/24"


def main() -> None:
    own_ip = get_own_ip()
    cidr = derive_subnet_cidr(own_ip)
    print(f"[recon] This container's IP: {own_ip}")
    print(f"[recon] Scanning subnet: {cidr}")
    print("[recon] (In a real engagement this subnet would have to be")
    print("[recon]  discovered too — here it's derived from our own")
    print("[recon]  interface for simplicity, since Docker assigns it.)\n")

    # Common ICS/IT ports worth checking, plus this project's actual ports.
    ports = "22,80,443,502,5020,8000,8080,102,20000"

    result = subprocess.run(
        ["nmap", "-Pn", "-p", ports, cidr],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)


if __name__ == "__main__":
    main()
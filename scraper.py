#!/usr/bin/env python3
"""
Automated Free Proxy Scraper & Verifier
Author: SoraDev-ID
Description: Mengambil daftar proxy publik (HTTP, SOCKS4, SOCKS5) dari berbagai sumber terpercaya,
             membersihkan duplikat, memvalidasi format IP:PORT, dan melakukan verifikasi cepat.
"""

import os
import re
import sys
import time
import socket
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Set, Tuple

# Reconfigure stdout untuk Windows terminal UTF-8 safety
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("[!] Modul 'requests' belum terpasang. Jalankan: pip install -r requirements.txt")
    sys.exit(1)

# Direktori proyek
BASE_DIR = Path(__file__).resolve().parent

# Daftar Sumber Proxy Publik Gratis & Aktif
PROXY_SOURCES: Dict[str, List[str]] = {
    "http": [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
    ],
    "socks4": [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=10000&country=all",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4_RAW.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks4/data.txt",
    ],
    "socks5": [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=10000&country=all",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
    ],
}

# Regex untuk pencocokan awal format IPv4:PORT
PROXY_REGEX = re.compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}:[0-9]{1,5}$")


def create_session() -> requests.Session:
    """Membuat HTTP session dengan retry dan timeout yang terkelola."""
    session = requests.Session()
    retries = Retry(
        total=2,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "*/*",
    })
    return session


def is_valid_proxy(proxy_str: str) -> bool:
    """
    Validasi ketat format IPv4:PORT.
    - Format 4 oktet IP 0-255 (tanpa leading zeros aneh, oktet pertama bukan 0 atau 127)
    - Port antara 1 sampai 65535
    """
    if not proxy_str or ":" not in proxy_str:
        return False

    if not PROXY_REGEX.match(proxy_str):
        return False

    try:
        ip, port_str = proxy_str.split(":", 1)
        port = int(port_str)
        if not (1 <= port <= 65535):
            return False

        octets = ip.split(".")
        if len(octets) != 4:
            return False

        first_octet = int(octets[0])
        # Filter IP loopback/reserved/nol
        if first_octet == 0 or first_octet == 127:
            return False

        for octet in octets:
            val = int(octet)
            if not (0 <= val <= 255):
                return False
            # Hindari leading zero (misal "01.2.3.4")
            if len(octet) > 1 and octet.startswith("0"):
                return False

        return True
    except (ValueError, TypeError):
        return False


def fetch_source_proxies(session: requests.Session, url: str) -> Set[str]:
    """Mengambil dan memfilter proxy dari satu URL sumber."""
    proxies = set()
    try:
        resp = session.get(url, timeout=10)
        if resp.status_code == 200:
            lines = resp.text.splitlines()
            for line in lines:
                candidate = line.strip()
                # Ekstrak substring jika baris memuat teks lain
                if "://" in candidate:
                    candidate = candidate.split("://")[-1]
                if "/" in candidate:
                    candidate = candidate.split("/")[0]

                if is_valid_proxy(candidate):
                    proxies.add(candidate)
    except Exception:
        pass
    return proxies


def scrape_protocol(session: requests.Session, protocol: str) -> Set[str]:
    """Mengambil seluruh proxy untuk satu protokol dari seluruh URL sumber."""
    urls = PROXY_SOURCES.get(protocol, [])
    all_proxies = set()
    print(f"[*] Mengambil proxy {protocol.upper()} dari {len(urls)} sumber...", end=" ", flush=True)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_source_proxies, session, url): url for url in urls}
        for future in as_completed(futures):
            try:
                res = future.result()
                all_proxies.update(res)
            except Exception:
                pass

    print(f"[✓ OK] Ditemukan {len(all_proxies)} unik.")
    return all_proxies


def check_single_proxy(proxy_str: str, timeout: float) -> Tuple[str, bool]:
    """
    Melakukan pemeriksaan konektivitas TCP cepat ke IP:PORT proxy.
    Mengembalikan tuple (proxy_str, is_alive).
    """
    try:
        ip, port_str = proxy_str.split(":", 1)
        port = int(port_str)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return proxy_str, (result == 0)
    except Exception:
        return proxy_str, False


def filter_alive_proxies(proxies: Set[str], timeout: float = 1.5, max_workers: int = 150) -> Set[str]:
    """
    Memeriksa status aktif proxy secara paralel berkecepatan tinggi.
    """
    alive = set()
    total = len(proxies)
    if total == 0:
        return alive

    print(f"[*] Melakukan verifikasi cepat {total} proxy (timeout={timeout}s, threads={max_workers})...", end=" ", flush=True)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_single_proxy, p, timeout): p for p in proxies}
        for future in as_completed(futures):
            try:
                proxy_str, is_alive = future.result()
                if is_alive:
                    alive.add(proxy_str)
            except Exception:
                pass

    print(f"[✓ OK] {len(alive)} aktif.")
    return alive


def save_proxy_file(file_path: Path, proxies: Set[str]) -> int:
    """Menyimpan daftar proxy ke file dengan format satu per baris."""
    sorted_proxies = sorted(list(proxies))
    with open(file_path, "w", encoding="utf-8") as f:
        for p in sorted_proxies:
            f.write(p + "\n")
    return len(sorted_proxies)


def update_timestamp_file(counts: Dict[str, int], duration: float):
    """Memperbarui file last_updated.txt dengan timestamp UTC dan WIB."""
    now_utc = datetime.now(timezone.utc)
    wib_tz = timezone(timedelta(hours=7))
    now_wib = now_utc.astimezone(wib_tz)

    str_utc = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    str_wib = now_wib.strftime("%Y-%m-%d %H:%M:%S WIB")

    total_proxies = sum(counts.values())

    content = f"""# Proxy Scraper - Status Pembaruan Terakhir
==================================================
Waktu Update (UTC) : {str_utc}
Waktu Update (WIB) : {str_wib}
Durasi Scrape      : {duration:.2f} detik
==================================================
Statistik Proxy:
- HTTP / HTTPS     : {counts.get('http', 0):>6} proxy
- SOCKS4           : {counts.get('socks4', 0):>6} proxy
- SOCKS5           : {counts.get('socks5', 0):>6} proxy
--------------------------------------------------
Total Keseluruhan  : {total_proxies:>6} proxy
Status Otomasi     : Berhasil Diperbarui
==================================================
"""
    with open(BASE_DIR / "last_updated.txt", "w", encoding="utf-8") as f:
        f.write(content)


def main():
    parser = argparse.ArgumentParser(description="Automated Proxy Scraper & Verifier")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Lakukan verifikasi konektivitas TCP cepat pada proxy sebelum disimpan"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=1.5,
        help="Timeout verifikasi koneksi dalam detik (default: 1.5)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=120,
        help="Jumlah thread paralel untuk verifikasi (default: 120)"
    )
    args = parser.parse_args()

    start_time = time.time()
    print("══════════════════════════════════════════════════════════════")
    print("          AUTOMATED PROXY SCRAPER & VERIFIER")
    print("                  Author: SoraDev-ID")
    print("══════════════════════════════════════════════════════════════\n")

    session = create_session()
    results: Dict[str, Set[str]] = {}

    # 1. Scrape setiap protokol
    for proto in ["http", "socks4", "socks5"]:
        scraped = scrape_protocol(session, proto)
        if args.check and scraped:
            scraped = filter_alive_proxies(scraped, timeout=args.timeout, max_workers=args.workers)
        results[proto] = scraped

    # 2. Simpan ke file masing-masing
    counts = {}
    print("\n[*] Menyimpan hasil ke file output...")
    counts["http"] = save_proxy_file(BASE_DIR / "http.txt", results["http"])
    counts["socks4"] = save_proxy_file(BASE_DIR / "socks4.txt", results["socks4"])
    counts["socks5"] = save_proxy_file(BASE_DIR / "socks5.txt", results["socks5"])

    # 3. Update last_updated.txt
    duration = time.time() - start_time
    update_timestamp_file(counts, duration)

    # 4. Ringkasan
    print("\n══════════════════════════════════════════════════════════════")
    print("                  RINGKASAN PROXY SCRAPED")
    print("══════════════════════════════════════════════════════════════")
    print(f"  • http.txt   : {counts['http']:>6} proxies")
    print(f"  • socks4.txt : {counts['socks4']:>6} proxies")
    print(f"  • socks5.txt : {counts['socks5']:>6} proxies")
    print(f"  • Total      : {sum(counts.values()):>6} proxies")
    print("══════════════════════════════════════════════════════════════")
    print(f"[✓] Berhasil diperbarui dalam {duration:.2f} detik!\n")


if __name__ == "__main__":
    main()

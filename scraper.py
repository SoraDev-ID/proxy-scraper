#!/usr/bin/env python3
"""
Automated Free Proxy Scraper & Verifier
Author: SoraDev-ID
Description: Mengambil daftar proxy publik (HTTP, SOCKS4, SOCKS5) dari berbagai sumber terpercaya,
             membersihkan duplikat, memvalidasi format IP:PORT publik, dan melakukan verifikasi fungsional HTTP GET.
"""

import os
import re
import sys
import time
import json
import socket
import ipaddress
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

# Target endpoint ringan untuk validasi fungsional proxy
CHECK_TARGET_URL = "http://httpbin.org/ip"

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
    - Format IPv4 publik valid (menolak private, reserved, multicast, link-local, loopback, unspecified).
    - Port antara 1 sampai 65535.
    - Menolak leading zero pada oktet IP (misal 01.2.3.4).
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

        # Hindari leading zero pada setiap oktet (misal "01.2.3.4")
        for octet in octets:
            if len(octet) > 1 and octet.startswith("0"):
                return False

        # Validasi ketat range menggunakan modul ipaddress
        ip_obj = ipaddress.ip_address(ip)
        if (
            ip_obj.version != 4
            or ip_obj.is_private
            or ip_obj.is_reserved
            or ip_obj.is_multicast
            or ip_obj.is_link_local
            or ip_obj.is_loopback
            or ip_obj.is_unspecified
        ):
            return False

        return True
    except (ValueError, TypeError):
        return False


def fetch_source_proxies(session: requests.Session, url: str) -> Set[str]:
    """Mengambil dan memfilter proxy dari satu URL sumber dengan penanganan error dan logging."""
    proxies = set()
    try:
        resp = session.get(url, timeout=10)
        if resp.status_code == 200:
            lines = resp.text.splitlines()
            for line in lines:
                candidate = line.strip()
                if "://" in candidate:
                    candidate = candidate.split("://")[-1]
                if "/" in candidate:
                    candidate = candidate.split("/")[0]

                if is_valid_proxy(candidate):
                    proxies.add(candidate)
        else:
            print(f"  [!] HTTP {resp.status_code} saat mengakses sumber: {url}")
    except requests.exceptions.RequestException as e:
        print(f"  [!] Gagal request sumber {url}: {type(e).__name__} ({e})")
    except Exception as e:
        print(f"  [!] Kesalahan memproses sumber {url}: {type(e).__name__} ({e})")
    return proxies


def scrape_protocol(session: requests.Session, protocol: str) -> Set[str]:
    """Mengambil seluruh proxy untuk satu protokol dari seluruh URL sumber."""
    urls = PROXY_SOURCES.get(protocol, [])
    all_proxies = set()
    print(f"[*] Mengambil proxy {protocol.upper()} dari {len(urls)} sumber...", flush=True)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_source_proxies, session, url): url for url in urls}
        for future in as_completed(futures):
            try:
                res = future.result()
                all_proxies.update(res)
            except Exception as e:
                print(f"  [!] Worker exception: {e}")

    print(f"[✓ OK] Ditemukan {len(all_proxies)} proxy {protocol.upper()} unik.")
    return all_proxies


def check_single_proxy(proxy_str: str, protocol_or_timeout: object = "http", timeout: float = 2.0) -> Tuple[str, bool, str]:
    """
    Melakukan verifikasi fungsional HTTP GET melalui proxy ke target URL.
    Mengembalikan tuple (proxy_str, is_alive, anonymity_level).
    - Mendukung protokol 'http', 'socks4', dan 'socks5'.
    - Anonymity: 'transparent', 'anonymous', atau 'elite'.
    """
    if isinstance(protocol_or_timeout, (int, float)):
        timeout = float(protocol_or_timeout)
        protocol = "http"
    else:
        protocol = str(protocol_or_timeout).lower()

    proxy_url = f"{protocol}://{proxy_str}"
    proxies = {
        "http": proxy_url,
        "https": proxy_url,
    }

    try:
        resp = requests.get(
            CHECK_TARGET_URL,
            proxies=proxies,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        if resp.status_code == 200:
            anonymity = "anonymous"
            if protocol == "http":
                try:
                    data = resp.json()
                    origin = str(data.get("origin", ""))
                    # Jika origin mengandung koma, client IP bocor -> transparent
                    if "," in origin:
                        anonymity = "transparent"
                    else:
                        anonymity = "elite"
                except Exception:
                    anonymity = "anonymous"
            return proxy_str, True, anonymity
    except Exception:
        pass
    return proxy_str, False, ""


def filter_alive_proxies(
    proxies: Set[str],
    protocol: str = "http",
    timeout: float = 2.0,
    max_workers: int = 150
) -> Tuple[Set[str], Dict[str, str]]:
    """
    Memeriksa status aktif fungsional proxy secara paralel berkecepatan tinggi.
    Mengembalikan (alive_set, anonymity_dict).
    """
    alive = set()
    anonymity_map = {}
    total = len(proxies)
    if total == 0:
        return alive, anonymity_map

    print(f"[*] Melakukan verifikasi fungsional {total} proxy {protocol.upper()} (timeout={timeout}s, threads={max_workers})...", flush=True)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_single_proxy, p, protocol, timeout): p for p in proxies}
        for future in as_completed(futures):
            try:
                proxy_str, is_alive, anon = future.result()
                if is_alive:
                    alive.add(proxy_str)
                    if anon:
                        anonymity_map[proxy_str] = anon
            except Exception:
                pass

    print(f"[✓ OK] {len(alive)} proxy {protocol.upper()} aktif terverifikasi.")
    return alive, anonymity_map


def save_proxy_file(file_path: Path, proxies: Set[str]) -> int:
    """Menyimpan daftar proxy ke file dengan format satu per baris."""
    sorted_proxies = sorted(list(proxies))
    with open(file_path, "w", encoding="utf-8") as f:
        for p in sorted_proxies:
            f.write(p + "\n")
    return len(sorted_proxies)


def save_anonymity_file(file_path: Path, anonymity_data: Dict[str, Dict[str, str]]):
    """Menyimpan pemetaan tingkat anonimitas proxy ke file JSON terpisah."""
    now_utc = datetime.now(timezone.utc)
    summary_by_level: Dict[str, int] = {}
    for proto_map in anonymity_data.values():
        for level in proto_map.values():
            summary_by_level[level] = summary_by_level.get(level, 0) + 1

    payload = {
        "updated_at_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_classified": sum(len(v) for v in anonymity_data.values()),
        "summary": summary_by_level,
        "anonymity": anonymity_data
    }
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def update_timestamp_file(counts: Dict[str, int], duration: float, anonymity_summary: Dict[str, int] = None):
    """
    Memperbarui file last_updated.txt dengan format JSON machine-parseable
    diikuti human-readable summary (UTC + WIB).
    """
    now_utc = datetime.now(timezone.utc)
    wib_tz = timezone(timedelta(hours=7))
    now_wib = now_utc.astimezone(wib_tz)

    total_proxies = sum(counts.values())

    json_data = {
        "updated_at_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated_at_wib": now_wib.strftime("%Y-%m-%dT%H:%M:%S+07:00"),
        "duration_seconds": round(duration, 2),
        "proxy_counts": {
            "http": counts.get("http", 0),
            "socks4": counts.get("socks4", 0),
            "socks5": counts.get("socks5", 0),
        },
        "total": total_proxies,
        "status": "success",
    }
    if anonymity_summary:
        json_data["anonymity_summary"] = anonymity_summary

    str_utc = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    str_wib = now_wib.strftime("%Y-%m-%d %H:%M:%S WIB")

    anon_text = ""
    if anonymity_summary:
        anon_text = (
            "Klasifikasi Anonimitas:\n"
            + "\n".join(f"- {k.capitalize():<16}: {v:>6} proxy" for k, v in sorted(anonymity_summary.items()))
            + "\n--------------------------------------------------\n"
        )

    content = (
        "### MACHINE-PARSEABLE JSON (parseable by scripts) ###\n"
        + json.dumps(json_data, indent=2)
        + "\n\n"
        "### HUMAN-READABLE SUMMARY ###\n"
        "══════════════════════════════════════════════════════════════\n"
        "          Proxy Scraper - Status Pembaruan Terakhir\n"
        "══════════════════════════════════════════════════════════════\n"
        f"Waktu Update (UTC) : {str_utc}\n"
        f"Waktu Update (WIB) : {str_wib}\n"
        f"Durasi Scrape      : {duration:.2f} detik\n"
        "══════════════════════════════════════════════════════════════\n"
        "Statistik Proxy:\n"
        f"- HTTP / HTTPS     : {counts.get('http', 0):>6} proxy\n"
        f"- SOCKS4           : {counts.get('socks4', 0):>6} proxy\n"
        f"- SOCKS5           : {counts.get('socks5', 0):>6} proxy\n"
        "--------------------------------------------------\n"
        + anon_text
        + f"Total Keseluruhan  : {total_proxies:>6} proxy\n"
        "Status Otomasi     : Berhasil Diperbarui\n"
        "══════════════════════════════════════════════════════════════\n"
    )

    with open(BASE_DIR / "last_updated.txt", "w", encoding="utf-8") as f:
        f.write(content)


def main():
    parser = argparse.ArgumentParser(description="Automated Proxy Scraper & Verifier")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Lakukan verifikasi fungsional HTTP GET pada proxy sebelum disimpan"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Timeout verifikasi fungsional dalam detik (default: 2.0)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=120,
        help="Jumlah thread paralel untuk verifikasi (default: 120)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Batasi jumlah proxy per protokol untuk pengujian cepat"
    )
    args = parser.parse_args()

    start_time = time.time()
    print("══════════════════════════════════════════════════════════════")
    print("          AUTOMATED PROXY SCRAPER & VERIFIER")
    print("                  Author: SoraDev-ID")
    print("══════════════════════════════════════════════════════════════\n")

    session = create_session()
    results: Dict[str, Set[str]] = {}
    all_anonymity: Dict[str, Dict[str, str]] = {}

    # 1. Scrape setiap protokol
    for proto in ["http", "socks4", "socks5"]:
        scraped = scrape_protocol(session, proto)
        if args.limit and len(scraped) > args.limit:
            scraped = set(list(scraped)[:args.limit])
        if args.check and scraped:
            scraped, anon_map = filter_alive_proxies(
                scraped,
                protocol=proto,
                timeout=args.timeout,
                max_workers=args.workers
            )
            if anon_map:
                all_anonymity[proto] = anon_map
        results[proto] = scraped

    # 2. Simpan ke file masing-masing
    counts = {}
    print("\n[*] Menyimpan hasil ke file output...")
    counts["http"] = save_proxy_file(BASE_DIR / "http.txt", results["http"])
    counts["socks4"] = save_proxy_file(BASE_DIR / "socks4.txt", results["socks4"])
    counts["socks5"] = save_proxy_file(BASE_DIR / "socks5.txt", results["socks5"])

    anonymity_summary = {}
    if all_anonymity:
        save_anonymity_file(BASE_DIR / "anonymity.json", all_anonymity)
        for proto_map in all_anonymity.values():
            for level in proto_map.values():
                anonymity_summary[level] = anonymity_summary.get(level, 0) + 1

    # 3. Update last_updated.txt
    duration = time.time() - start_time
    update_timestamp_file(counts, duration, anonymity_summary if anonymity_summary else None)

    # 4. Ringkasan
    print("\n══════════════════════════════════════════════════════════════")
    print("                  RINGKASAN PROXY SCRAPED")
    print("══════════════════════════════════════════════════════════════")
    print(f"  • http.txt   : {counts['http']:>6} proxies")
    print(f"  • socks4.txt : {counts['socks4']:>6} proxies")
    print(f"  • socks5.txt : {counts['socks5']:>6} proxies")
    print(f"  • Total      : {sum(counts.values()):>6} proxies")
    if anonymity_summary:
        print("  • Anonimitas : " + ", ".join(f"{k}: {v}" for k, v in sorted(anonymity_summary.items())))
    print("══════════════════════════════════════════════════════════════")
    print(f"[✓] Berhasil diperbarui dalam {duration:.2f} detik!\n")


if __name__ == "__main__":
    main()

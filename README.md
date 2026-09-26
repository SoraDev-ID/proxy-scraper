# ⚡ Automated Fast Proxy Scraper

[![Proxy Update Workflow](https://github.com/SoraDev-ID/proxy-scraper/actions/workflows/update-proxy.yml/badge.svg)](https://github.com/SoraDev-ID/proxy-scraper/actions/workflows/update-proxy.yml)
[![Protocols](https://img.shields.io/badge/Protocols-HTTP%20%7C%20SOCKS4%20%7C%20SOCKS5-3D5AFE?style=flat-square)](#)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-10B981?style=flat-square)](LICENSE)

Alat otomatisasi pengambil (*scraper*) dan pemverifikasi proxy publik gratis dari berbagai sumber terpercaya di internet. Daftar proxy diperbarui secara berkala dan otomatis via **GitHub Actions** dan dipisahkan berdasarkan protokol (**HTTP/HTTPS**, **SOCKS4**, dan **SOCKS5**).

---

## 🔗 Tautan Langsung Raw Proxy (Siap Pakai)

Gunakan tautan `raw.githubusercontent.com` di bawah ini untuk mengunduh atau mengintegrasikan daftar proxy langsung ke dalam bot, scraper, atau aplikasi Anda:

| Protokol | Tautan Raw GitHub | Format |
| :--- | :--- | :---: |
| **HTTP / HTTPS** | [`https://raw.githubusercontent.com/SoraDev-ID/proxy-scraper/main/http.txt`](https://raw.githubusercontent.com/SoraDev-ID/proxy-scraper/main/http.txt) | `IP:PORT` |
| **SOCKS4** | [`https://raw.githubusercontent.com/SoraDev-ID/proxy-scraper/main/socks4.txt`](https://raw.githubusercontent.com/SoraDev-ID/proxy-scraper/main/socks4.txt) | `IP:PORT` |
| **SOCKS5** | [`https://raw.githubusercontent.com/SoraDev-ID/proxy-scraper/main/socks5.txt`](https://raw.githubusercontent.com/SoraDev-ID/proxy-scraper/main/socks5.txt) | `IP:PORT` |
| **Status Update** | [`https://raw.githubusercontent.com/SoraDev-ID/proxy-scraper/main/last_updated.txt`](https://raw.githubusercontent.com/SoraDev-ID/proxy-scraper/main/last_updated.txt) | Metadata & Count |

---

## ✨ Fitur Unggulan

- 🚀 **Cepat & Ringan**: Mengambil puluhan ribu proxy unik dalam hitungan detik.
- 🧹 **Deduplikasi & Validasi Ketat**: Memastikan hanya string dengan format IPv4 valid (`0-255` per oktet tanpa reserved/loopback) dan port valid (`1-65535`).
- 📡 **Multi-Protokol**: Mendukung pemisahan bersih untuk HTTP/HTTPS, SOCKS4, dan SOCKS5.
- ⚡ **Opsi Health-Check Asinkron**: Dilengkapi opsi `--check` untuk pengujian konektivitas TCP berkecepatan tinggi dengan ratusan thread paralel.
- 🤖 **Auto-Commit Cerdas**: GitHub Actions hanya membuat commit jika ada perubahan data baru untuk mencegah commit kosong (*no spam commits*).

---

## 📁 Struktur Direktori

```text
proxy-scraper/
├── .github/
│   └── workflows/
│       └── update-proxy.yml # GitHub Actions auto-updater
├── scraper.py               # Script utama pengambil & pemverifikasi proxy
├── http.txt                 # Daftar proxy HTTP/HTTPS
├── socks4.txt               # Daftar proxy SOCKS4
├── socks5.txt               # Daftar proxy SOCKS5
├── last_updated.txt         # Timestamp dan rekap jumlah proxy
├── requirements.txt         # Dependensi Python (requests, urllib3)
├── .gitignore               # Standard ignore
└── README.md                # Dokumentasi & panduan
```

---

## 💻 Contoh Penggunaan di Python

### 1. HTTP/HTTPS Proxy (Rotasi Acak dengan `requests`)

```python
import random
import requests

# 1. Ambil daftar proxy dari file lokal atau URL raw
with open("http.txt", "r") as f:
    proxies = [line.strip() for line in f if line.strip()]

# 2. Pilih proxy secara acak
random_proxy = random.choice(proxies)
proxy_dict = {
    "http": f"http://{random_proxy}",
    "https": f"http://{random_proxy}"
}

print(f"[*] Mencoba request melalui proxy: {random_proxy}")
try:
    response = requests.get(
        "https://httpbin.org/ip",
        proxies=proxy_dict,
        timeout=5
    )
    print("[✓] IP Asli Berhasil Disamarkan:", response.json())
except requests.exceptions.RequestException as e:
    print("[✗] Proxy timeout / gagal:", e)
```

### 2. SOCKS4 / SOCKS5 Proxy
Untuk menggunakan SOCKS proxy dengan `requests`, pasang dependensi `PySocks`:
```bash
pip install "requests[socks]"
```

```python
import random
import requests

with open("socks5.txt", "r") as f:
    socks5_proxies = [line.strip() for line in f if line.strip()]

proxy = random.choice(socks5_proxies)
proxies = {
    "http": f"socks5://{proxy}",
    "https": f"socks5://{proxy}"
}

response = requests.get("https://httpbin.org/ip", proxies=proxies, timeout=5)
print(response.json())
```

---

## ⚙️ Cara Menjalankan Scraper Sendiri

### 1. Kloning Repository
```bash
git clone https://github.com/SoraDev-ID/proxy-scraper.git
cd proxy-scraper
```

### 2. Pasang Dependensi
```bash
pip install -r requirements.txt
```

### 3. Eksekusi Script
```bash
# Mode cepat (scrape & validasi format IP:Port)
python scraper.py

# Mode dengan verifikasi TCP aktif (opsional)
python scraper.py --check --timeout 1.5 --workers 150
```

---

## ℹ️ Catatan Mengenai Interval 1 Menit di GitHub Actions

Workflow ini dikonfigurasikan dengan sintaks cron `* * * * *` (setiap 1 menit). Namun, penting untuk dipahami:

> ⚠️ **Limitasi Resmi GitHub Actions:**  
> GitHub membatasi interval minimum cron terjadwal gratis rata-rata **sekali per 5 menit** *(dan dapat terjadi antrian tambahan beberapa menit pada jam sibuk server GitHub)*. Sintaks `* * * * *` akan dijalankan oleh GitHub setiap ~5 menit.

### 💡 Alternatif jika Anda BENAR-BENAR membutuhkan update per 1 menit:
1. **Cron di VPS / Server Kecil Pribadi (Paling Direkomendasikan)**:
   Gunakan VPS Linux murah (DigitalOcean, Contabo, AWS Lightsail) dan pasang cron job:
   ```cron
   * * * * * cd /home/user/proxy-scraper && python scraper.py && git add . && git commit -m "auto-update" && git push origin main
   ```
2. **Self-Hosted GitHub Runner**:
   Pasang GitHub Runner di server/PC lokal Anda sendiri sehingga eksekusi tidak bergantung pada antrian publik GitHub.
3. **Eksternal Webhook / Cron Service**:
   Gunakan layanan gratis seperti *cron-job.org* atau *EasyCron* yang menembak API GitHub `repository_dispatch` setiap 1 menit.

---

## ⚖️ Disclaimer (Penyangkalan)

Semua proxy di dalam repository ini dikumpulkan secara publik dari berbagai agregator dan database open-source di internet. 
- Penulis (**SoraDev-ID**) **tidak mengoperasikan, mengontrol, atau menjamin keandalan/keamanan** dari server proxy yang terdaftar.
- **Dilarang keras** menggunakan proxy ini untuk aktivitas ilegal, penipuan, peretasan, atau tindakan merugikan lainnya.
- Gunakan secara bijak dan bertanggung jawab, terutama untuk kebutuhan riset, pengujian kompabilitas jaringan, dan pengikisan data publik (*ethical web scraping*).

---

## 📄 Lisensi

Proyek ini dirilis di bawah lisensi resmi **[MIT License](LICENSE)**.

<p align="center">
  Dikelola dengan ⚡ oleh <b><a href="https://github.com/SoraDev-ID">SoraDev-ID</a></b>
</p>

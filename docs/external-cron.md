# Setup External Scheduler untuk GitHub Actions (1 Menit Interval)

Panduan ini menjelaskan cara memicu workflow GitHub Actions pada repositori `SoraDev-ID/proxy-scraper` setiap 1 menit menggunakan webhook `repository_dispatch` melalui layanan gratis cron-job.org untuk melewati batasan cron bawaan GitHub Actions (yang memiliki limit minimum interval 5 menit).

---

## 1. Membuat Personal Access Token (PAT) di GitHub

1. Buka akun GitHub, klik profil di pojok kanan atas lalu pilih **Settings**.
2. Gulir ke bawah di panel kiri dan pilih **Developer settings** -> **Personal access tokens** -> **Tokens (classic)** (atau [klik link langsung ini](https://github.com/settings/tokens)).
3. Klik tombol **Generate new token** -> **Generate new token (classic)**.
4. Masukkan nama/Note, misalnya: `proxy-scraper-cron`.
5. Tentukan masa berlaku token (**Expiration**), misalnya *90 days* atau *No expiration* sesuai preferensi.
6. Pada bagian **Select scopes**, centang:
   - `public_repo` (jika repositori ini bersifat publik).
   - *Catatan:* Jika repositori diubah menjadi private, centang seluruh scope `repo`.
7. Klik **Generate token** di bagian bawah halaman.
8. Salin token tersebut (berawalan `ghp_...`) dan simpan di tempat aman. Token tidak akan bisa dilihat lagi setelah halaman ditutup.

---

## 2. Mendaftar di cron-job.org

1. Buka situs [cron-job.org](https://cron-job.org/).
2. Daftar akun baru secara gratis (**Sign Up**) atau masuk (**Log In**) jika sudah memiliki akun.
3. Konfirmasi alamat email akun jika diminta.

---

## 3. Membuat Cronjob Baru

1. Masuk ke halaman **Cronjobs** di dashboard cron-job.org, lalu klik tombol **Create cronjob**.
2. Isi formulir konfigurasi berikut:
   - **Title**: `Proxy Scraper Trigger`
   - **URL**:
     ```text
     https://api.github.com/repos/SoraDev-ID/proxy-scraper/dispatches
     ```
   - **Request Method**: Ubah menjadi `POST`.
3. Buka tab atau bagian **Headers**, lalu tambahkan 3 header berikut:
   - Header 1:
     - Key: `Authorization`
     - Value: `Bearer <PAT_ANDA>` *(Ganti `<PAT_ANDA>` dengan token yang disalin di langkah 1, contoh: `Bearer ghp_xxx`)*
   - Header 2:
     - Key: `Accept`
     - Value: `application/vnd.github+json`
   - Header 3:
     - Key: `Content-Type`
     - Value: `application/json`
4. Buka tab atau bagian **Request Body**, lalu masukkan JSON berikut:
   ```json
   {"event_type": "update-proxy"}
   ```

---

## 4. Mengatur Jadwal Interval

1. Pada bagian **Schedule**, pilih **User-defined**.
2. Atur interval eksekusi menjadi **Every 1 minute** (Setiap 1 menit).
3. Simpan konfigurasi dengan menekan tombol **Create**.

---

## 5. Cara Verifikasi Eksekusi Job

1. Di cron-job.org, periksa tab **History** pada job yang baru dibuat. Pastikan response code mengembalikan **HTTP 204 No Content** (status sukses dari GitHub API).
2. Buka tab **Actions** di repositori GitHub:
   ```text
   https://github.com/SoraDev-ID/proxy-scraper/actions
   ```
3. Periksa daftar workflow run:
   - Anda akan melihat workflow `Automated Proxy Scraper` terpicu dengan deskripsi event `repository_dispatch`.
   - Fitur `concurrency` dengan `cancel-in-progress: true` akan memastikan bahwa jika scraper sebelumnya masih berjalan saat trigger baru masuk, proses lama akan dibatalkan sehingga tidak terjadi race condition saat commit proxy list.

---

## Catatan Rate Limit GitHub API
- GitHub API memberikan batas rate limit sebesar **5.000 request per jam** untuk setiap Personal Access Token (PAT).
- Menjalankan cronjob dengan interval 1 menit hanya mengonsumsi **60 request per jam** (sekitar 1,2% dari total kuota yang diizinkan), sehingga sangat aman dari limitasi GitHub API.

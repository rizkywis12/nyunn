# Pesan Suara with S3 Storage

Aplikasi `pesan-suara.html` sekarang dapat memutar audio dari S3 dan menerima upload / rekaman langsung ke storage.

## Menjalankan server

1. Pasang dependensi:
   ```bash
   pip install -r requirements.txt
   ```

2. Buat file `.env` di root proyek dengan variabel:
   ```bash
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   S3_BUCKET=rizyyn
   S3_ENDPOINT_URL=https://s3.nevaobjects.id
   S3_PUBLIC_URL=https://rizyyn.s3.nevaobjects.id
   S3_PREFIX=audio/
   ```

3. Jalankan server:
   ```bash
   python3 server.py
   ```

4. Buka browser di:
   ```
   http://127.0.0.1:5000
   ```

## Fitur

- Memutar audio dari bucket S3.
- Mengunggah file audio ke storage.
- Merekam audio langsung dari mikrofon dan mengunggah hasil rekaman.

> Jangan simpan `AWS_SECRET_ACCESS_KEY` di repo publik. Gunakan `.env` lokal atau secret manager.

# architect.md — İştek Platform 🇹🇷 Mimari Referansı

Bu dosya projenin yapısının hızlı-referans özetidir. Kod değiştikçe güncel tutun.

## Genel Bakış

Türkiye'ye özel TaskRabbit benzeri hizmet platformu — Python / Flask M�şteriler iş ilanı açar, doğrulanmış uzmanlar teklif verir. Platform; ödeme, mesajlaşma, randevu ve iş takibini uçtan uca yönetir.

## Teknoloji Yığını

- Flask
- MySQL (PyMySQL)
- requests

## Dizin Yapısı

```
.env.example
.gitignore
README.md
app.py
database.py
mail_service.py
mobil_api_service.js
requirements.txt
routes/
  api.py
  auth.py
  chat.py
  eslestir.py
  iade.py
  konum.py
  oauth_kimlik.py
  odeme.py
  takip.py
  takvim.py
  upload.py
  video.py
security.py
seed_demo.py
sms_service.py
static/
templates/
  auth/
  chat/
  dashboard/
  index.html
```

## Modüller / Kaynak Dosyalar

- `app.py` — ╔══════════════════════════════════════════════════════════════╗
- `database.py` — ╔══════════════════════════════════════════════════════════════╗
- `mail_service.py` — ╔══════════════════════════════════════════════════════════════╗
- `mobil_api_service.js` — İştek Platform — React Native API Servisi
- `security.py` — ╔══════════════════════════════════════════════════════════════╗
- `seed_demo.py` — İştek Platform — Gerçekçi Demo Veri Üretici
- `sms_service.py` — ╔══════════════════════════════════════════════════════════════╗
- `routes/api.py` — ╔══════════════════════════════════════════════════════════════╗
- `routes/auth.py` — ╔══════════════════════════════════════════════════════════════╗
- `routes/chat.py` — ╔══════════════════════════════════════════════════════════════╗
- `routes/eslestir.py` — ╔══════════════════════════════════════════════════════════════╗
- `routes/iade.py`
- `routes/konum.py` — ╔══════════════════════════════════════════════════════════════╗
- `routes/oauth_kimlik.py`
- `routes/odeme.py`
- `routes/takip.py` — ╔══════════════════════════════════════════════════════════════╗
- `routes/takvim.py` — ╔══════════════════════════════════════════════════════════════╗
- `routes/upload.py` — ╔══════════════════════════════════════════════════════════════╗
- `routes/video.py` — ╔══════════════════════════════════════════════════════════════╗

## Giriş Noktaları ve Yapılandırma

- `app.py`
- `requirements.txt`
- `templates/index.html`

## Dağıtım / Çalışma Ortamı

- GitHub: https://github.com/SHapeloglu/AIUSTA

## Diğer Dokümanlar

- `README.md`

## Mimari Kararlar

_Önemli tasarım kararlarını ve gerekçelerini buraya ekleyin (ör. "X yerine Y seçildi çünkü ...")._

# architect.md — İştek Platform Mimarisi

## Genel Yapı

Tek süreçli monolit: Flask + Flask-SocketIO (eventlet) + MySQL. Sunucu tarafında Jinja şablonları sayfaları verir; sayfalar içerikleri JSON uç noktalarından `fetch` ile çeker (`static/js/app.js`). Mobil istemci için aynı JSON API'leri CORS ile açık (`mobil_api_service.js` hazır istemci katmanı).

```
Tarayıcı / Mobil ──HTTP(JSON)──► Flask blueprint'leri ──► database.query() ──► MySQL (istek_db)
        │                              │
        └──Socket.IO (chat)────────────┤──► mail_service (Flask-Mail, thread)
                                       ├──► sms_service (Netgsm HTTP, thread)
                                       ├──► iyzico (ödeme + iade API)
                                       ├──► Google OAuth (Authlib)
                                       └──► Jitsi Meet (yalnız oda URL'i üretilir)
```

## Başlangıç Sırası (`app.py`)

1. `load_dotenv()` → `SECRET_KEY` yoksa geçici rastgele anahtar (her yeniden başlatmada oturumlar düşer).
2. `init_security(app)` — limiter, güvenlik başlıkları, cookie ayarları.
3. `SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")`, `mail.init_app`, `init_oauth`, `CORS(...)`.
4. 15 blueprint kaydı, `register_socket_events(socketio)`.
5. `__main__`: `init_db`, `init_security_db`, `init_takvim`, `init_upload_db`, `init_iade_db`, `init_takip_db`, `init_kimlik_db`, `init_video_db`, `seed_demo` → `socketio.run(port=5000)`.

## Modüller

| Dosya | Blueprint / URL öneki | Sorumluluk | Tablolar |
|---|---|---|---|
| `database.py` | — | Bağlantı, `query()`, çekirdek şema | kullanicilar, uzman_profiller, ilanlar, teklifler, mesajlar, odemeler, degerlendirmeler, bildirimler |
| `security.py` | — | Rate limit, hesap kilidi, CSRF, başlıklar, doğrulama | giriş denemeleri (`init_security_db`) |
| `routes/auth.py` | `/auth` | Kayıt, giriş, profil; `giris_gerekli`, `bildirim_olustur` yardımcıları | — |
| `routes/api.py` | `/api` | Uzman/ilan listeleme, teklif, değerlendirme, admin işlemleri | — |
| `routes/odeme.py` | `/odeme` | iyzico checkout, %12 komisyon, ödeme geçmişi | odemeler |
| `routes/iade.py` | `/iade`, `/iptal` | İade talebi/onay/red, ilan iptali, iyzico Refund | iade_talepler |
| `routes/chat.py` | `/chat` + Socket.IO | Konuşma listesi; olaylar `oda_katil`, `mesaj_gonder`, `okundu_isaretle`, `disconnect` | mesajlar |
| `routes/takvim.py` | `/takvim`, admin_extra | Müsaitlik, çakışma kontrollü randevu; ek admin uçları (kullanıcı ban, ilan kapat) | musaitlik, randevular |
| `routes/upload.py` | `/upload` | Profil/ilan/portfolyo fotoğrafı, Pillow ile küçültme | ilan_fotograflar, portfolyo |
| `routes/eslestir.py` | `/eslestir` | Uzman eşleştirme skoru (TF + kosinüs, kategori, puan, tecrübe, fiyat, şehir bonusu) | — |
| `routes/takip.py` | `/takip` | 8 adımlı iş süreci (`IS_ADIMLARI`) ve notlar | is_takip, is_notlar |
| `routes/oauth_kimlik.py` | `/oauth`, `/kimlik` | Google OAuth, kimlik belgesi yükleme + admin onayı | kimlik_dogrulama |
| `routes/konum.py` | `/konum` | Haversine ile yarıçap araması, harita pin verisi | — |
| `routes/video.py` | `/video` | Jitsi oda adı/URL üretimi (`meet.jit.si`) | video_odalar |
| `mail_service.py` | — | 8 e-posta şablonu (Gmail SMTP) | — |
| `sms_service.py` | — | 8 SMS şablonu, `05XX → 905XX` normalizasyonu | — |
| `seed_demo.py` | CLI | Gerçekçi demo veri üretici (`--temizle`, `--yeniden`, `--zorla`) | tümü |

## İş Akışı

```
İlan → Teklif → Kabul → Ödeme → Randevu → Başladı → Tamamlandı → Değerlendirildi
```
- Ödeme escrow mantığıyla platformda tutulur; komisyon %12.
- İade oranı: randevuya >24 saat → %100, 2–24 saat → %50, daha az → %0.

## Dosya Depolama

`static/uploads/{profil,ilan,portfolyo,kimlik}/` — `security.guvenli_klasor_yolu` ile path traversal engellenir, MIME tipi `dosya_mime_guvenlimi` ile kontrol edilir. Limit 8 MB (`MAX_CONTENT_LENGTH`).

## Yapılandırma

`.env` (bkz. `.env.example`): `SECRET_KEY`, `FLASK_DEBUG`, `DB_HOST/PORT/USER/PASSWORD/NAME`, `IYZICO_API_KEY/SECRET_KEY/BASE_URL`, `GOOGLE_CLIENT_ID/SECRET`, `FRONTEND_URL`, `REDIS_URL` (opsiyonel; yoksa limiter bellekte).
Not: `MAIL_*` ve `NETGSM_*` `.env.example`'da olsa da kod henüz okumuyor (bkz. `task.md`).

## Mimari Kararlar

- **Migration yerine `CREATE TABLE IF NOT EXISTS`**: her modül kendi tablosunu açılışta oluşturur. Basit ama şema değişikliklerini takip etmez.
- **ORM yok**: ince `query()` yardımcısı + DictCursor; sonuçlar doğrudan JSON'a dönüştürülür.
- **Eşleştirme saf Python**: scikit-learn bağımlılığı listede olsa da kullanılmıyor; küçük veri için yeterli.
- **Video için Jitsi**: sunucu tarafında medya altyapısı yok, sadece oda URL'i üretiliyor.

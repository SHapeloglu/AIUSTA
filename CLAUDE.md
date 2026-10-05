# CLAUDE.md — İştek Platform (AIUSTA)

Türkiye'ye özel, TaskRabbit benzeri hizmet pazaryeri. Müşteri iş ilanı açar, admin onaylı uzmanlar teklif verir. Ödeme (iyzico), mesajlaşma (Socket.IO), randevu, iade ve 8 adımlı iş takibi tek bir Flask uygulamasında.

- GitHub: https://github.com/SHapeloglu/AIUSTA (tek bir "zzzz" yükleme commit'i var; sunucuda canlı kurulumu yok)
- Mimari: `architect.md` · Görevler: `task.md` · Fikirler: `backlog.md` · Oturum günlüğü: `session.md`

## Çalıştırma

```bash
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # SECRET_KEY, DB_*, IYZICO_*, GOOGLE_* doldur
python app.py                 # http://localhost:5000 — tabloları ve demo admin'i otomatik oluşturur
python seed_demo.py           # isteğe bağlı: 40 uzman / 60 müşteri / 120 ilan
python seed_demo.py --temizle --yeniden   # demo veriyi sıfırla
```

- MySQL 8 gerekir; `istek_db` yoksa `database.init_db()` oluşturur.
- Uygulama `socketio.run(..., async_mode="eventlet")` ile başlar — `flask run` ile değil, `python app.py` ile çalıştır (Socket.IO için).
- Otomatik demo hesabı (`app.py:seed_demo`): `admin@istek.com` / `Admin123!`. README'deki `admin123` eski — doğru değer koddaki.

## Kod Haritası (kısa)

- `app.py` — Flask + SocketIO kurulumu, blueprint kaydı, sayfa rotaları (`/`, `/giris`, `/dashboard`, `/chat`, `/admin`), `KATEGORILER`/`SEHIRLER` sabitleri, başlangıçta tüm `init_*_db()` çağrıları.
- `database.py` — `query(sql, args, fetch="all"|"one"|"none")` tek DB yardımcısı (PyMySQL, DictCursor); çekirdek tablolar.
- `security.py` — rate limit (flask-limiter), hesap kilitleme (5 deneme → 15 dk), CSRF double-submit cookie, güvenlik başlıkları, girdi/MIME doğrulama.
- `routes/*.py` — her alan kendi blueprint'i ve kendi `init_*_db()` tablosu (bkz. `architect.md`).
- `mail_service.py`, `sms_service.py` — Flask-Mail ve Netgsm şablonları; gönderim thread içinde.

## Kurallar ve Tuzaklar

- **Tüm SQL `database.query()` üzerinden ve parametreli (`%s`)** yazılır; string birleştirme ile SQL kurma.
- Yeni tablo eklerken ilgili blueprint dosyasına `init_xxx_db()` yaz ve `app.py`'nin `__main__` bloğuna ekle — migration aracı yok, `CREATE TABLE IF NOT EXISTS` kullanılıyor (var olan tabloya kolon eklemek için elle `ALTER` gerekir).
- Durum değiştiren uç noktalara `@giris_gerekli` (`routes/auth.py`) ve gerekiyorsa `@csrf_dogrula` / `@hassas_islem_dogrula` (`security.py`) ekle; giriş/kayıt gibi uçlara `@limiter.limit(...)`.
- Oturum alanları: `session["kullanici_id"]`, `["kullanici_ad"]`, `["kullanici_rol"]` (`musteri` | `uzman` | `admin`).
- **Gizli bilgiler:** `mail_service.py` (`MAIL_CONFIG`) ve `sms_service.py` (`NETGSM_*`) hâlâ koda gömülü yer tutucu kullanıyor, `.env.example`'daki `MAIL_*`/`NETGSM_*` değişkenlerini okumuyor. Bunlara dokunurken `os.environ`'a taşı; gerçek değerleri asla commit etme.
- `requirements.txt`'teki `scikit-learn`/`numpy` kullanılmıyor — `routes/eslestir.py` TF ve kosinüs benzerliğini saf Python ile hesaplıyor.
- Para tutarları: komisyon %12, iade oranı randevuya kalan süreye göre (`routes/iade.py:iade_orani_hesapla`). Bu kuralları değiştirirsen README'yi de güncelle.
- Test yok. Değişiklikten sonra en azından `python -c "import app"` ve ilgili uç noktayı elle dene.
- Oturum sonunda `session.md`'ye kayıt düş, `task.md`'yi güncelle.

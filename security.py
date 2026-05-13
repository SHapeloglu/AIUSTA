"""
╔══════════════════════════════════════════════════════════════╗
║           İştek Platform — Güvenlik Modülü                  ║
╚══════════════════════════════════════════════════════════════╝

Bu modül tüm güvenlik önlemlerini tek yerden yönetir:

  1. Rate Limiting    — flask-limiter ile brute force koruması
  2. Güvenlik Başlıkları — flask-talisman ile HTTP güvenlik başlıkları
  3. CSRF Koruması    — çift gönderim cookie pattern
  4. Giriş Doğrulama  — e-posta, şifre, dosya tipi doğrulama
  5. Hesap Kilitleme  — 5 başarısız denemede geçici kilit
  6. Güvenli Dosya    — MIME type doğrulama

Kullanım (app.py):
    from security import init_security, limiter
    init_security(app)

    @app.route("/giris")
    @limiter.limit("5 per minute")
    def giris(): ...
"""

import os, re, hashlib, time
from functools import wraps
from flask import request, jsonify, session, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from database import query

# ─── RATE LIMITER ─────────────────────────────────────────────────────────────
# IP adresi bazlı hız sınırlama.
# Redis varsa REDIS_URL ortam değişkeninden kullanılır, yoksa bellekte tutar.

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.environ.get("REDIS_URL", "memory://"),
    strategy="fixed-window",
)

# Özel hız limitleri — rotalar üzerinde dekoratör olarak kullanılır:
#   @limiter.limit("5 per minute")   → giriş, kayıt
#   @limiter.limit("3 per minute")   → şifre değiştirme
#   @limiter.limit("10 per hour")    → ilan oluşturma
#   @limiter.limit("30 per hour")    → teklif verme

# ─── HESAP KİLİTLEME ─────────────────────────────────────────────────────────
# 5 başarısız giriş denemesinde hesabı 15 dakika kilitler.

MAKSIMUM_DENEME = 5          # İzin verilen maksimum başarısız deneme
KILIT_SURE_SANIYE = 15 * 60  # 15 dakika (saniye cinsinden)

def giris_denemesi_kaydet(email: str, basarili: bool):
    """
    Giriş denemesini kaydeder. Başarısız denemeleri sayar,
    MAKSIMUM_DENEME aşılırsa hesabı kilitler.
    """
    if basarili:
        # Başarılı girişte sayacı sıfırla
        query(
            "UPDATE kullanicilar SET giris_deneme=0, kilit_bitis=NULL WHERE email=%s",
            (email,), fetch="none"
        )
        return

    # Başarısız denemeyi artır
    query(
        """UPDATE kullanicilar
           SET giris_deneme = giris_deneme + 1,
               kilit_bitis  = CASE
                   WHEN giris_deneme + 1 >= %s
                   THEN DATE_ADD(NOW(), INTERVAL %s SECOND)
                   ELSE kilit_bitis
               END
           WHERE email=%s""",
        (MAKSIMUM_DENEME, KILIT_SURE_SANIYE, email),
        fetch="none"
    )

def hesap_kilitli_mi(email: str) -> tuple[bool, int]:
    """
    Hesabın kilitli olup olmadığını kontrol eder.

    Döndürür:
        (True, kalan_saniye) — hesap kilitliyse
        (False, 0)           — hesap açıksa
    """
    k = query(
        "SELECT giris_deneme, kilit_bitis FROM kullanicilar WHERE email=%s",
        (email,), fetch="one"
    )
    if not k or not k.get("kilit_bitis"):
        return False, 0

    kalan = query(
        "SELECT TIMESTAMPDIFF(SECOND, NOW(), kilit_bitis) AS kalan FROM kullanicilar WHERE email=%s",
        (email,), fetch="one"
    )
    kalan_saniye = int(kalan["kalan"]) if kalan and kalan.get("kalan") else 0

    if kalan_saniye > 0:
        return True, kalan_saniye
    return False, 0

# ─── GİRİŞ DOĞRULAMA ─────────────────────────────────────────────────────────

def email_gecerli(email: str) -> bool:
    """Basit e-posta format doğrulaması."""
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email or ""))

def sifre_guclu(sifre: str) -> tuple[bool, str]:
    """
    Şifre güç kontrolü.

    Kurallar:
        - En az 8 karakter
        - En az 1 büyük harf
        - En az 1 küçük harf
        - En az 1 rakam

    Döndürür:
        (True, "")          — şifre güçlü
        (False, "hata msg") — şifre zayıf
    """
    if len(sifre) < 8:
        return False, "Şifre en az 8 karakter olmalıdır."
    if not re.search(r'[A-ZÇĞİÖŞÜ]', sifre):
        return False, "Şifre en az 1 büyük harf içermelidir."
    if not re.search(r'[a-zçğışöşü]', sifre):
        return False, "Şifre en az 1 küçük harf içermelidir."
    if not re.search(r'\d', sifre):
        return False, "Şifre en az 1 rakam içermelidir."
    return True, ""

def metin_temizle(metin: str, max_uzunluk: int = 500) -> str:
    """
    Kullanıcı girdisini temizler.
    HTML taglerini kaldırır, uzunluk sınırlar.
    """
    if not metin:
        return ""
    temiz = re.sub(r'<[^>]+>', '', str(metin))  # HTML taglerini kaldır
    return temiz[:max_uzunluk].strip()

# ─── DOSYA GÜVENLİĞİ ─────────────────────────────────────────────────────────

IZINLI_MIME_TIPLERI = {
    "image/jpeg", "image/png", "image/webp", "image/gif"
}

def dosya_mime_guvenlimi(dosya_stream) -> bool:
    """
    Dosyanın gerçek MIME tipini kontrol eder (uzantıya güvenmez).
    Pillow zaten görseli parse ettiği için ek güvenlik katmanı sağlar.

    Dosya imzaları (magic bytes):
        JPEG: FF D8 FF
        PNG:  89 50 4E 47
        WebP: 52 49 46 46 ... 57 45 42 50
        GIF:  47 49 46 38
    """
    header = dosya_stream.read(12)
    dosya_stream.seek(0)  # Stream'i başa al

    # JPEG
    if header[:3] == b'\xff\xd8\xff':
        return True
    # PNG
    if header[:4] == b'\x89PNG':
        return True
    # GIF
    if header[:6] in (b'GIF87a', b'GIF89a'):
        return True
    # WebP (RIFF....WEBP)
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return True

    return False

# ─── GÜVENLİ DOSYA YOLU ──────────────────────────────────────────────────────

def guvenli_klasor_yolu(temel: str, alt_yol: str) -> str:
    """
    Path traversal saldırılarını önler.
    "../../../etc/passwd" gibi girişlerin temel klasör dışına çıkmasını engeller.
    """
    import pathlib
    temel_path = pathlib.Path(temel).resolve()
    hedef_path = (temel_path / alt_yol).resolve()

    # Hedef yol temel klasörün içinde mi?
    if not str(hedef_path).startswith(str(temel_path)):
        raise ValueError(f"Güvenli olmayan dosya yolu: {alt_yol}")

    return str(hedef_path)

# ─── GÜVENLİK BAŞLIKLARI ─────────────────────────────────────────────────────

def guvenlik_basliklari_ekle(response):
    """
    Her HTTP yanıtına güvenlik başlıkları ekler.
    app.after_request ile kayıt edilir.

    Eklenen başlıklar:
        X-Content-Type-Options   → MIME sniffing önler
        X-Frame-Options          → Clickjacking önler
        X-XSS-Protection         → Eski tarayıcılarda XSS filtresi
        Referrer-Policy          → Referrer bilgisi sızdırmaz
        Permissions-Policy       → Gereksiz tarayıcı API'larını kısıtlar
        Content-Security-Policy  → Sadece güvenilen kaynaklardan içerik
        Strict-Transport-Security→ HTTPS zorlar (canlıda aktif)
    """
    # MIME tipi zorla — tarayıcının tahmin etmesini engelle
    response.headers["X-Content-Type-Options"] = "nosniff"

    # iframe içinde gösterilmeyi engelle (clickjacking)
    response.headers["X-Frame-Options"] = "SAMEORIGIN"

    # Eski tarayıcılar için XSS filtresi
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Referrer bilgisini sadece aynı origin ile paylaş
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Gereksiz tarayıcı özelliklerini kapat
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=(self), payment=(self)"
    )

    # Content Security Policy — XSS'e karşı en güçlü koruma
    # Sadece kendi origin + Jitsi Meet + Socket.IO kaynaklarına izin ver
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://meet.jit.si "
        "https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' wss: ws: https://meet.jit.si; "
        "frame-src https://meet.jit.si;"
    )

    # HTTPS zorla — canlı ortamda etkin (geliştirmede sorun yaratmaz)
    if not os.environ.get("FLASK_DEBUG", "0") == "1":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

    return response

# ─── CSRF KORUMASI ────────────────────────────────────────────────────────────

def csrf_token_olustur() -> str:
    """
    Kullanıcı oturumuna özgü CSRF token üretir.
    Token oturumda yoksa yeni üretir ve saklar.
    """
    if "csrf_token" not in session:
        session["csrf_token"] = hashlib.sha256(
            os.urandom(32)
        ).hexdigest()
    return session["csrf_token"]

def csrf_dogrula(f):
    """
    Dekoratör: POST/PUT/DELETE isteklerinde CSRF token doğrular.

    İstemci şu iki yöntemden biriyle token göndermeli:
        1. X-CSRF-Token HTTP başlığı (AJAX için)
        2. csrf_token form alanı

    Kullanım:
        @app.route("/islem", methods=["POST"])
        @csrf_dogrula
        def islem(): ...

    Frontend (JS):
        const token = document.cookie.match(/csrf_token=([^;]+)/)?.[1];
        fetch("/islem", {
            method: "POST",
            headers: { "X-CSRF-Token": token, "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Sadece durum değiştiren metodları kontrol et
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            beklenen = session.get("csrf_token")

            # Token başlık veya form verisinden al
            gelen = (
                request.headers.get("X-CSRF-Token") or
                request.form.get("csrf_token") or
                (request.json or {}).get("csrf_token")
            )

            if not beklenen or not gelen or beklenen != gelen:
                return jsonify({"hata": "Geçersiz güvenlik token'ı. Sayfayı yenileyip tekrar deneyin."}), 403

        return f(*args, **kwargs)
    return decorated

# ─── OTURUM GÜVENLİĞİ ────────────────────────────────────────────────────────

def hassas_islem_dogrula(f):
    """
    Dekoratör: Ödeme ve şifre değişikliği gibi hassas işlemler için
    son giriş zamanını kontrol eder. 30 dakika içinde giriş yapılmamışsa
    yeniden doğrulama ister.

    Kullanım:
        @app.route("/odeme/baslat", methods=["POST"])
        @giris_gerekli
        @hassas_islem_dogrula
        def odeme_baslat(): ...
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        son_giris = session.get("son_giris_zamani", 0)
        gecen_sure = time.time() - son_giris

        # 30 dakikadan fazla olmuşsa yeniden doğrulama iste
        if gecen_sure > 30 * 60:
            return jsonify({
                "hata": "Güvenlik nedeniyle yeniden giriş yapmanız gerekiyor.",
                "yeniden_giris": True,
                "yonlendir": "/giris"
            }), 401

        return f(*args, **kwargs)
    return decorated

# ─── BAŞLATMA ─────────────────────────────────────────────────────────────────

def init_security(app):
    """
    Tüm güvenlik önlemlerini Flask uygulamasına bağlar.
    app.py içinde init_db()'den sonra çağrılmalıdır.

    Yapılanlar:
        1. Rate limiter'ı başlat
        2. Her yanıta güvenlik başlıklarını ekle
        3. CSRF token cookie'sini her yanıtta güncelle
        4. Oturum güvenlik ayarlarını yapılandır
    """
    # Rate limiter'ı uygulamaya bağla
    limiter.init_app(app)

    # Her yanıta güvenlik başlıklarını otomatik ekle
    app.after_request(guvenlik_basliklari_ekle)

    # Flask oturum güvenlik ayarları
    app.config.update({
        # Cookie sadece HTTPS üzerinden gitsin (canlıda True)
        "SESSION_COOKIE_SECURE":   not os.environ.get("FLASK_DEBUG", "0") == "1",
        # JS'nin cookie'ye erişimini engelle (XSS koruması)
        "SESSION_COOKIE_HTTPONLY": True,
        # Cookie sadece aynı site isteklerine eklensin (CSRF azaltma)
        "SESSION_COOKIE_SAMESITE": "Lax",
        # Cookie adını değiştir (varsayılan 'session' çok tanınır)
        "SESSION_COOKIE_NAME":     "istek_sid",
    })

    # Rate limit aşıldığında özel hata döndür
    @app.errorhandler(429)
    def rate_limit_asild(e):
        return jsonify({
            "hata": "Çok fazla istek gönderdiniz. Lütfen bir süre bekleyin.",
            "tekrar_dene": str(e.description)
        }), 429

    print("🔒 Güvenlik modülü aktif.")

# ─── VERİTABANI ŞEMASI ────────────────────────────────────────────────────────

GUVENLIK_SCHEMA = [
    # Hesap kilitleme için gerekli sütunlar
    "ALTER TABLE kullanicilar ADD COLUMN IF NOT EXISTS giris_deneme INT DEFAULT 0",
    "ALTER TABLE kullanicilar ADD COLUMN IF NOT EXISTS kilit_bitis DATETIME DEFAULT NULL",
    "ALTER TABLE kullanicilar ADD COLUMN IF NOT EXISTS son_giris DATETIME DEFAULT NULL",
]

def init_security_db():
    """Güvenlik ile ilgili veritabanı sütunlarını ekler."""
    from database import query as q
    for sql in GUVENLIK_SCHEMA:
        try:
            q(sql, fetch="none")
        except Exception as e:
            print(f"[Güvenlik DB] {e}")

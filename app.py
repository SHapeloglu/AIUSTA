"""
╔══════════════════════════════════════════════════════════════╗
║           İştek Platform — Ana Uygulama                     ║
║  Tüm blueprint'ler, güvenlik modülleri ve rotalar burada    ║
╚══════════════════════════════════════════════════════════════╝

Başlatma sırası:
  1. .env dosyası yüklenir (python-dotenv)
  2. Flask uygulaması oluşturulur
  3. Güvenlik modülü başlatılır (rate limit, headers, session)
  4. Veritabanı şeması oluşturulur
  5. Blueprint'ler kayıt edilir
  6. Socket.IO olayları bağlanır
"""

import os
from datetime import timedelta
from flask import Flask, render_template, session, jsonify, redirect
from flask_socketio import SocketIO
from flask_cors import CORS
from dotenv import load_dotenv

# .env dosyasını en başta yükle
load_dotenv()

# ─── MODÜL İMPORTLARI ─────────────────────────────────────────────────────────
from database import init_db, query
from mail_service import mail, MAIL_CONFIG
from security import init_security, init_security_db, limiter, csrf_token_olustur

from routes.auth        import auth_bp
from routes.api         import api_bp
from routes.odeme       import odeme_bp
from routes.chat        import chat_bp, register_socket_events
from routes.takvim      import takvim_bp, admin_extra_bp, init_takvim
from routes.upload      import upload_bp, init_upload_db
from routes.iade        import iade_bp, iptal_bp, init_iade_db
from routes.eslestir    import eslestir_bp
from routes.takip       import takip_bp, init_takip_db
from routes.oauth_kimlik import oauth_bp, kimlik_bp, init_kimlik_db, init_oauth
from routes.konum       import konum_bp
from routes.video       import video_bp, init_video_db

# ─── UYGULAMA OLUŞTUR ─────────────────────────────────────────────────────────
app = Flask(__name__)

# Secret key mutlaka ortam değişkeninden gelmelidir
# .env.example'dan kopyalayıp .env oluşturun ve SECRET_KEY'i güçlü bir değerle doldurun
_secret = os.environ.get("SECRET_KEY")
if not _secret or _secret == "buraya-guclu-rastgele-bir-deger-girin-degistirin":
    import secrets
    _secret = secrets.token_hex(32)
    print("⚠️  UYARI: SECRET_KEY ayarlanmamış! Geçici rastgele key kullanılıyor.")
    print("   .env dosyasında SECRET_KEY değişkenini ayarlayın.")

app.secret_key = _secret
app.permanent_session_lifetime = timedelta(days=30)
app.config.update(MAIL_CONFIG)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8MB dosya limiti

# ─── GÜVENLİK MODÜLÜ ─────────────────────────────────────────────────────────
# Güvenlik başlıkları, rate limiting ve oturum güvenliği
init_security(app)

# ─── SOCKET.IO ────────────────────────────────────────────────────────────────
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# ─── E-POSTA ──────────────────────────────────────────────────────────────────
mail.init_app(app)

# ─── OAUTH ────────────────────────────────────────────────────────────────────
init_oauth(app)

# ─── CORS — Mobil uygulama için ───────────────────────────────────────────────
CORS(app, supports_credentials=True, origins=[
    "http://localhost:3000",    # React Native geliştirme
    "http://localhost:19006",   # Expo Go
    os.environ.get("FRONTEND_URL", "https://istek.com"),  # Canlı domain
])

# ─── BLUEPRINT KAYITLARI ──────────────────────────────────────────────────────
for bp in [
    auth_bp, api_bp, odeme_bp, chat_bp,
    takvim_bp, admin_extra_bp,
    upload_bp, iade_bp, iptal_bp,
    eslestir_bp, takip_bp,
    oauth_bp, kimlik_bp,
    konum_bp, video_bp,
]:
    app.register_blueprint(bp)

register_socket_events(socketio)

# ─── CSRF TOKEN — Her yanıtta cookie olarak gönder ───────────────────────────
@app.after_request
def csrf_cookie_ekle(response):
    """Her yanıtta güncel CSRF token'ı cookie olarak gönderir."""
    try:
        from flask import has_request_context
        if has_request_context() and session:
            token = csrf_token_olustur()
            response.set_cookie(
                "csrf_token", token,
                samesite="Lax",
                httponly=False,  # JS okuyabilmeli (AJAX için)
                secure=not os.environ.get("FLASK_DEBUG", "0") == "1"
            )
    except Exception:
        pass
    return response

# ─── SABİTLER ─────────────────────────────────────────────────────────────────
KATEGORILER = [
    {"id": "temizlik",  "ad": "Ev Temizliği",     "ikon": "🧹"},
    {"id": "tamirat",   "ad": "Tamirat & Montaj",  "ikon": "🔧"},
    {"id": "nakliyat",  "ad": "Nakliyat & Taşıma", "ikon": "🚚"},
    {"id": "bahce",     "ad": "Bahçe & Peyzaj",    "ikon": "🌿"},
    {"id": "boya",      "ad": "Boya & Badana",      "ikon": "🎨"},
    {"id": "elektrik",  "ad": "Elektrik İşleri",   "ikon": "⚡"},
    {"id": "tesisaat",  "ad": "Tesisat İşleri",    "ikon": "🚿"},
    {"id": "guvenlik",  "ad": "Güvenlik & Kamera", "ikon": "🔐"},
    {"id": "klima",     "ad": "Klima & Isıtma",    "ikon": "❄️"},
    {"id": "diger",     "ad": "Diğer İşler",       "ikon": "📦"},
]
SEHIRLER = [
    "İstanbul", "Ankara", "İzmir", "Bursa", "Antalya",
    "Adana", "Konya", "Gaziantep", "Mersin", "Kayseri",
    "Eskişehir", "Trabzon", "Samsun", "Denizli", "Balıkesir",
]

# ─── SAYFA ROTALARI ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    k = None
    if "kullanici_id" in session:
        k = {
            "id":  session["kullanici_id"],
            "ad":  session["kullanici_ad"],
            "rol": session["kullanici_rol"],
        }
    return render_template("index.html",
                           kategoriler=KATEGORILER,
                           sehirler=SEHIRLER,
                           kullanici=k)

@app.route("/giris")
@app.route("/kayit")
def auth_sayfa():
    return render_template("auth/auth.html")

@app.route("/dashboard")
def dashboard():
    if "kullanici_id" not in session:
        return redirect("/giris")
    return render_template("dashboard/dashboard.html",
                           kullanici_ad=session.get("kullanici_ad"),
                           kullanici_rol=session.get("kullanici_rol"))

@app.route("/chat")
@app.route("/chat/<diger_id>")
def chat_sayfa(diger_id=None):
    if "kullanici_id" not in session:
        return redirect("/giris")
    return render_template("chat/chat.html",
                           kullanici_id=session["kullanici_id"],
                           kullanici_ad=session["kullanici_ad"],
                           hedef_id=diger_id or "")

@app.route("/admin")
def admin_sayfa():
    if session.get("kullanici_rol") != "admin":
        return redirect("/")
    return render_template("dashboard/admin.html",
                           kullanici_ad=session.get("kullanici_ad"))

# ─── HATA İŞLEYİCİLER ────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return jsonify({"hata": "Sayfa bulunamadı."}), 404

@app.errorhandler(413)
def too_large(e):
    return jsonify({"hata": "Dosya çok büyük. Maksimum 8MB."}), 413

@app.errorhandler(429)
def rate_limit(e):
    return jsonify({"hata": "Çok fazla istek. Lütfen bekleyin."}), 429

@app.errorhandler(500)
def server_error(e):
    # Canlı ortamda detayları gizle
    if os.environ.get("FLASK_DEBUG", "0") == "1":
        return jsonify({"hata": "Sunucu hatası.", "detay": str(e)}), 500
    return jsonify({"hata": "Bir hata oluştu. Lütfen tekrar deneyin."}), 500

# ─── DEMO VERİ ────────────────────────────────────────────────────────────────

def seed_demo():
    """İlk kurulumda demo hesaplar oluşturur."""
    if query("SELECT id FROM kullanicilar LIMIT 1", fetch="one"):
        return
    import bcrypt, uuid
    from datetime import datetime
    def hp(s): return bcrypt.hashpw(s.encode(), bcrypt.gensalt()).decode()

    admin_id = str(uuid.uuid4())
    query(
        "INSERT INTO kullanicilar (id,ad_soyad,email,sifre_hash,rol,sehir) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (admin_id, "Platform Admin", "admin@istek.com",
         hp("Admin123!"), "admin", "İstanbul"),
        fetch="none"
    )

    for ad, email, sehir, kat, ucret, puan, is_say, aciklama in [
        ("Mehmet Yılmaz", "mehmet@demo.com", "İstanbul", "temizlik", 150, 4.8, 142,
         "10 yıllık deneyimli temizlik uzmanı."),
        ("Ayşe Kaya",     "ayse@demo.com",   "Ankara",   "temizlik", 180, 4.9, 230,
         "Sertifikalı uzman. Ekolojik ürünlerle allerji dostu temizlik."),
        ("Ali Demir",     "ali@demo.com",    "İzmir",    "tamirat",  200, 4.7,  89,
         "15 yıl deneyimli usta."),
        ("Hasan Şahin",   "hasan@demo.com",  "İstanbul", "elektrik", 250, 4.9, 310,
         "Lisanslı elektrikçi."),
    ]:
        uid = str(uuid.uuid4())
        query(
            "INSERT INTO kullanicilar (id,ad_soyad,email,sifre_hash,rol,sehir) "
            "VALUES (%s,%s,%s,%s,'uzman',%s)",
            (uid, ad, email, hp("Demo123!"), sehir), fetch="none"
        )
        query(
            "INSERT INTO uzman_profiller "
            "(id,kullanici_id,kategori,saatlik_ucret,puan,is_tamamlanan,aciklama,onaylandi,katilim_tarihi) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,1,%s)",
            (str(uuid.uuid4()), uid, kat, ucret, puan, is_say, aciklama,
             datetime.now().strftime("%Y-%m-%d")),
            fetch="none"
        )

    musteri_id = str(uuid.uuid4())
    query(
        "INSERT INTO kullanicilar (id,ad_soyad,email,sifre_hash,rol,sehir) "
        "VALUES (%s,%s,%s,%s,'musteri',%s)",
        (musteri_id, "Demo Müşteri", "musteri@demo.com",
         hp("Demo123!"), "İstanbul"),
        fetch="none"
    )

    print("✅ Demo hesaplar oluşturuldu.")
    print("   Admin:   admin@istek.com  / Admin123!")
    print("   Uzman:   mehmet@demo.com  / Demo123!")
    print("   Müşteri: musteri@demo.com / Demo123!")

# ─── BAŞLAT ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🔌 Veritabanı hazırlanıyor...")
    init_db()
    init_security_db()
    init_takvim()
    init_upload_db()
    init_iade_db()
    init_takip_db()
    init_kimlik_db()
    init_video_db()
    seed_demo()

    # Debug modu .env'den okunur — canlıda 0 olmalı
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    if debug:
        print("⚠️  DEBUG MODU AÇIK — sadece geliştirme için!")

    print("🚀 İştek Platform → http://localhost:5000")
    socketio.run(app, debug=debug, port=5000)

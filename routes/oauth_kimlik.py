import os
"""
╔══════════════════════════════════════════════════════════════╗
║     İştek Platform — Google OAuth + Kimlik Doğrulama        ║
╚══════════════════════════════════════════════════════════════╝

Google ile sosyal giriş ve TC kimlik belgesi doğrulama sistemi.

Google OAuth Akışı:
    1. GET /oauth/google          → Google'a yönlendir
    2. Kullanıcı izin verir
    3. GET /oauth/google/callback → Token al, kullanıcı oluştur/giriş yap
    4. /dashboard'a yönlendir

Kimlik Doğrulama Akışı:
    1. Uzman belge fotoğrafı yükler (ön yüz + arka yüz)
    2. Admin panelde belgeler incelenir
    3. Onaylanırsa profilde "Doğrulandı" rozeti görünür

Kurulum (Google OAuth):
    1. console.cloud.google.com → Yeni Proje
    2. APIs & Services → Credentials → OAuth 2.0 Client ID
    3. Authorized redirect URI: http://localhost:5000/oauth/google/callback
    4. GOOGLE_CLIENT_ID ve GOOGLE_CLIENT_SECRET ortam değişkenlerini ayarla

Rotalar:
    GET  /oauth/google              → Google giriş başlat
    GET  /oauth/google/callback     → Google callback
    POST /kimlik/belge-yukle        → Kimlik belgesi yükle
    GET  /kimlik/durum              → Doğrulama durumu
    POST /kimlik/onayla/<id>        → Admin: kimliği onayla
    POST /kimlik/reddet/<id>        → Admin: kimliği reddet
    GET  /kimlik/bekleyenler        → Admin: bekleyen kimlikler
"""

import uuid, os
from flask import Blueprint, request, jsonify, session, redirect, url_for, current_app
from authlib.integrations.flask_client import OAuth
from database import query
from routes.auth import giris_gerekli, bildirim_olustur, hash_sifre

oauth_bp   = Blueprint("oauth",  __name__, url_prefix="/oauth")
kimlik_bp  = Blueprint("kimlik", __name__, url_prefix="/kimlik")

# ─── Google OAuth AYARLARI ────────────────────────────────────────────────────
GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID",     "YOUR_GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "YOUR_GOOGLE_CLIENT_SECRET")
# Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client IDs
# Authorized redirect URI: http://localhost:5000/oauth/google/callback
# ─────────────────────────────────────────────────────────────────────────────

oauth = OAuth()

def init_oauth(app):
    """app.py içinde çağrılır: init_oauth(app)"""
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

# ─── Google ile giriş ────────────────────────────────────────────────────────

@oauth_bp.route("/google")
def google_giris():
    redirect_uri = url_for("oauth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@oauth_bp.route("/google/callback")
def google_callback():
    try:
        token    = oauth.google.authorize_access_token()
        userinfo = token.get("userinfo") or oauth.google.userinfo()
    except Exception as e:
        return redirect(f"/giris?hata=google_hatasi")

    email = userinfo.get("email", "").lower()
    ad    = userinfo.get("name", "")

    if not email:
        return redirect("/giris?hata=email_alinamadi")

    # Mevcut kullanıcı mı?
    k = query("SELECT * FROM kullanicilar WHERE email=%s AND aktif=1", (email,), fetch="one")

    if k:
        # Giriş yap
        _oturum_ac(k)
    else:
        # Yeni kayıt
        uid = str(uuid.uuid4())
        query(
            "INSERT INTO kullanicilar (id, ad_soyad, email, sifre_hash, rol, email_dogrulandi) "
            "VALUES (%s,%s,%s,%s,'musteri',1)",
            (uid, ad, email, hash_sifre(uuid.uuid4().hex)),  # rastgele şifre
            fetch="none"
        )
        k = query("SELECT * FROM kullanicilar WHERE id=%s", (uid,), fetch="one")
        _oturum_ac(k)

        # Hoş geldin bildirimi
        bildirim_olustur(uid, "sistem", "İştek'e Hoş Geldiniz!",
                         "Google ile kaydoldunuz.", "/dashboard")

    return redirect("/dashboard")

def _oturum_ac(k: dict):
    session.permanent = True
    session["kullanici_id"]    = k["id"]
    session["kullanici_ad"]    = k["ad_soyad"]
    session["kullanici_rol"]   = k["rol"]
    session["kullanici_email"] = k["email"]

# ─── Kimlik Doğrulama ─────────────────────────────────────────────────────────

@kimlik_bp.route("/belge-yukle", methods=["POST"])
@giris_gerekli
def belge_yukle():
    uid      = session["kullanici_id"]
    tip      = request.form.get("tip", "tc_kimlik")   # tc_kimlik | pasaport | ehliyet

    if "on_yuz" not in request.files:
        return jsonify({"hata": "Belgenin ön yüzü zorunlu."}), 400

    on_yuz   = request.files["on_yuz"]
    arka_yuz = request.files.get("arka_yuz")

    # Kimlik belgeleri static/ DIŞINDA saklanır — doğrudan URL ile erişilemez
    import uuid as _uuid
    from PIL import Image as _Image
    from werkzeug.utils import secure_filename as _sf
    from security import dosya_mime_guvenlimi

    def kimlik_kaydet(dosya):
        if not dosya or not dosya.filename:
            return None
        if not dosya_mime_guvenlimi(dosya.stream):
            raise ValueError("Geçersiz dosya tipi.")
        uzanti  = dosya.filename.rsplit(".", 1)[-1].lower()
        ad      = f"{_uuid.uuid4().hex}.{uzanti}"
        klasor  = os.path.join("kimlik_belgeleri")
        os.makedirs(klasor, exist_ok=True)
        yol     = os.path.join(klasor, ad)
        img     = _Image.open(dosya.stream)
        if img.width > 1200:
            oran = 1200 / img.width
            img  = img.resize((1200, int(img.height * oran)), _Image.LANCZOS)
        if img.mode in ("RGBA", "P"):
            arka = _Image.new("RGB", img.size, (255,255,255))
            arka.paste(img, mask=img.split()[3] if img.mode=="RGBA" else None)
            img  = arka
        img.save(yol, "JPEG", quality=85)
        # URL değil, sadece dosya adı saklanır — güvenli erişim rotasından sunulur
        return f"kimlik_belgeleri/{ad}"

    try:
        on_url   = kimlik_kaydet(on_yuz)
        arka_url = kimlik_kaydet(arka_yuz) if arka_yuz and arka_yuz.filename else None
    except ValueError as e:
        return jsonify({"hata": str(e)}), 400

    kid = str(uuid.uuid4())
    query(
        """INSERT INTO kimlik_dogrulama
           (id, kullanici_id, tip, on_yuz_url, arka_yuz_url, durum)
           VALUES (%s,%s,%s,%s,%s,'beklemede')
           ON DUPLICATE KEY UPDATE
             tip=%s, on_yuz_url=%s, arka_yuz_url=%s, durum='beklemede', guncelleme=NOW()""",
        (kid, uid, tip, on_url, arka_url,
         tip, on_url, arka_url),
        fetch="none"
    )

    # Admin'e bildirim
    adminler = query("SELECT id FROM kullanicilar WHERE rol='admin'")
    kisi     = query("SELECT ad_soyad FROM kullanicilar WHERE id=%s", (uid,), fetch="one")
    for admin in adminler:
        bildirim_olustur(admin["id"], "kimlik",
            "Kimlik Doğrulama Talebi",
            f"{kisi['ad_soyad']} kimlik belgesi yükledi.",
            "/admin"
        )

    return jsonify({
        "basarili": True,
        "mesaj": "Belgeniz incelemeye alındı. 1-2 iş günü içinde sonuçlandırılacak."
    })

@kimlik_bp.route("/durum", methods=["GET"])
@giris_gerekli
def kimlik_durum():
    uid = session["kullanici_id"]
    kd  = query(
        "SELECT durum, tip, red_sebebi, guncelleme FROM kimlik_dogrulama WHERE kullanici_id=%s",
        (uid,), fetch="one"
    )
    if not kd:
        return jsonify({"durum": "yuklenmedi", "mesaj": "Henüz belge yüklenmedi."})
    kd["guncelleme"] = str(kd["guncelleme"]) if kd.get("guncelleme") else None
    return jsonify(kd)

@kimlik_bp.route("/onayla/<uid>", methods=["POST"])
@giris_gerekli
def kimlik_onayla(uid):
    if session.get("kullanici_rol") != "admin":
        return jsonify({"hata": "Yetkisiz."}), 403

    query(
        "UPDATE kimlik_dogrulama SET durum='onaylandi', guncelleme=NOW() WHERE kullanici_id=%s",
        (uid,), fetch="none"
    )
    query(
        "UPDATE kullanicilar SET kimlik_dogrulandi=1 WHERE id=%s", (uid,), fetch="none"
    )
    # Uzman profilinde de işaretle
    query(
        "UPDATE uzman_profiller SET belge_yuklendi=1 WHERE kullanici_id=%s", (uid,), fetch="none"
    )

    bildirim_olustur(uid, "kimlik", "Kimliğiniz Doğrulandı ✅",
                     "Kimlik doğrulamanız tamamlandı. Profilinizde rozet görünecek.")

    # SMS
    try:
        kisi = query("SELECT ad_soyad, telefon FROM kullanicilar WHERE id=%s", (uid,), fetch="one")
        if kisi and kisi.get("telefon"):
            from sms_service import send_sms
            send_sms(kisi["telefon"],
                     f"Merhaba {kisi['ad_soyad'].split()[0]}, "
                     f"Istek kimlik dogrulamaniz tamamlandi! "
                     f"Profilinizde onay rozeti gorunecek.")
    except Exception:
        pass

    return jsonify({"basarili": True})

@kimlik_bp.route("/reddet/<uid>", methods=["POST"])
@giris_gerekli
def kimlik_reddet(uid):
    if session.get("kullanici_rol") != "admin":
        return jsonify({"hata": "Yetkisiz."}), 403

    sebep = (request.json or {}).get("sebep", "Belge okunamadı veya geçersiz.")
    query(
        "UPDATE kimlik_dogrulama SET durum='reddedildi', red_sebebi=%s, guncelleme=NOW() WHERE kullanici_id=%s",
        (sebep, uid), fetch="none"
    )
    bildirim_olustur(uid, "kimlik", "Kimlik Doğrulama Reddedildi",
                     f"Sebep: {sebep} Lütfen tekrar yükleyin.")
    return jsonify({"basarili": True})

# ─── Admin: bekleyen kimlikler ────────────────────────────────────────────────

@kimlik_bp.route("/bekleyenler", methods=["GET"])
@giris_gerekli
def bekleyen_kimlikler():
    if session.get("kullanici_rol") != "admin":
        return jsonify({"hata": "Yetkisiz."}), 403

    rows = query("""
        SELECT kd.*, k.ad_soyad, k.email, k.sehir
        FROM kimlik_dogrulama kd
        JOIN kullanicilar k ON k.id=kd.kullanici_id
        WHERE kd.durum='beklemede'
        ORDER BY kd.olusturma DESC
    """)
    for r in rows:
        r["olusturma"]  = str(r["olusturma"]) if r.get("olusturma") else None
        r["guncelleme"] = str(r["guncelleme"]) if r.get("guncelleme") else None
    return jsonify(rows)

# ─── Veritabanı tabloları ─────────────────────────────────────────────────────

KIMLIK_SCHEMA = [
    """ALTER TABLE kullanicilar ADD COLUMN IF NOT EXISTS kimlik_dogrulandi TINYINT(1) DEFAULT 0""",

    """CREATE TABLE IF NOT EXISTS kimlik_dogrulama (
        id            VARCHAR(36)  PRIMARY KEY,
        kullanici_id  VARCHAR(36)  UNIQUE NOT NULL,
        tip           ENUM('tc_kimlik','pasaport','ehliyet') DEFAULT 'tc_kimlik',
        on_yuz_url    VARCHAR(255),
        arka_yuz_url  VARCHAR(255),
        durum         ENUM('beklemede','onaylandi','reddedildi') DEFAULT 'beklemede',
        red_sebebi    TEXT,
        olusturma     DATETIME DEFAULT CURRENT_TIMESTAMP,
        guncelleme    DATETIME,
        FOREIGN KEY (kullanici_id) REFERENCES kullanicilar(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
]

def init_kimlik_db():
    from database import query as q
    for sql in KIMLIK_SCHEMA:
        try:
            q(sql, fetch="none")
        except Exception as e:
            print(f"[Kimlik DB] {e}")

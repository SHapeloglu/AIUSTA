"""
╔══════════════════════════════════════════════════════════════╗
║       İştek Platform — Kimlik Doğrulama (Güvenli)           ║
╚══════════════════════════════════════════════════════════════╝

Güvenlik önlemleri:
  - Rate limiting: giriş 5/dakika, kayıt 3/dakika
  - Brute force: 5 başarısız denemede 15 dakika kilit
  - Şifre gücü: min 8 karakter, büyük/küçük/rakam zorunlu
  - Giriş zamanı session'a kaydedilir (hassas işlemler için)
"""
from flask import Blueprint, request, jsonify, session
from database import query
from security import (
    limiter, giris_denemesi_kaydet, hesap_kilitli_mi,
    email_gecerli, sifre_guclu, metin_temizle
)
import bcrypt, uuid, time
from datetime import datetime

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# ─── YARDIMCILAR ──────────────────────────────────────────────────────────────

def hash_sifre(sifre: str) -> str:
    return bcrypt.hashpw(sifre.encode(), bcrypt.gensalt()).decode()

def sifre_dogru(sifre: str, hash_: str) -> bool:
    return bcrypt.checkpw(sifre.encode(), hash_.encode())

def oturum_ac(kullanici: dict):
    session.permanent = True
    session["kullanici_id"]      = kullanici["id"]
    session["kullanici_ad"]      = kullanici["ad_soyad"]
    session["kullanici_rol"]     = kullanici["rol"]
    session["kullanici_email"]   = kullanici["email"]
    session["son_giris_zamani"]  = time.time()  # Hassas işlemler için

def giris_gerekli(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "kullanici_id" not in session:
            return jsonify({"hata": "Giriş yapmanız gerekiyor.", "yonlendir": "/giris"}), 401
        return f(*args, **kwargs)
    return decorated

def bildirim_olustur(kullanici_id, tip, baslik, metin, link=None):
    query(
        "INSERT INTO bildirimler (id, kullanici_id, tip, baslik, metin, link) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (str(uuid.uuid4()), kullanici_id, tip, baslik, metin, link),
        fetch="none"
    )

# ─── KAYIT ────────────────────────────────────────────────────────────────────

@auth_bp.route("/kayit", methods=["POST"])
@limiter.limit("3 per minute")   # Kayıt spam koruması
def kayit():
    b = request.json or {}

    # Girdileri temizle
    ad    = metin_temizle(b.get("ad_soyad", ""), 120)
    email = (b.get("email") or "").strip().lower()
    sifre = b.get("sifre") or ""
    rol   = b.get("rol", "musteri")

    # Doğrulama
    if not ad or not email or not sifre:
        return jsonify({"hata": "Ad, e-posta ve şifre zorunludur."}), 400
    if not email_gecerli(email):
        return jsonify({"hata": "Geçerli bir e-posta adresi girin."}), 400

    guclu, guc_mesaj = sifre_guclu(sifre)
    if not guclu:
        return jsonify({"hata": guc_mesaj}), 400
    if rol not in ("musteri", "uzman"):
        return jsonify({"hata": "Geçersiz hesap türü."}), 400
    if query("SELECT id FROM kullanicilar WHERE email=%s", (email,), fetch="one"):
        return jsonify({"hata": "Bu e-posta adresi zaten kayıtlıdır."}), 409

    uid = str(uuid.uuid4())
    query(
        "INSERT INTO kullanicilar (id, ad_soyad, email, sifre_hash, rol, telefon, sehir) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (uid, ad, email, hash_sifre(sifre), rol,
         metin_temizle(b.get("telefon",""), 20),
         metin_temizle(b.get("sehir",""), 80)),
        fetch="none"
    )

    if rol == "uzman":
        query(
            "INSERT INTO uzman_profiller "
            "(id, kullanici_id, kategori, saatlik_ucret, aciklama, katilim_tarihi) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (str(uuid.uuid4()), uid,
             b.get("kategori", "diger"),
             int(b.get("saatlik_ucret", 0)),
             metin_temizle(b.get("aciklama", ""), 1000),
             datetime.now().strftime("%Y-%m-%d")),
            fetch="none"
        )

    k = query("SELECT * FROM kullanicilar WHERE id=%s", (uid,), fetch="one")
    oturum_ac(k)
    return jsonify({"basarili": True, "kullanici": {"id": uid, "ad": ad, "rol": rol}}), 201

# ─── GİRİŞ ────────────────────────────────────────────────────────────────────

@auth_bp.route("/giris", methods=["POST"])
@limiter.limit("5 per minute")   # Brute force koruması
def giris():
    b     = request.json or {}
    email = (b.get("email") or "").strip().lower()
    sifre = b.get("sifre") or ""

    if not email or not sifre:
        return jsonify({"hata": "E-posta ve şifre zorunludur."}), 400

    # Hesap kilidi kontrolü
    kilitli, kalan = hesap_kilitli_mi(email)
    if kilitli:
        dakika = (kalan // 60) + 1
        return jsonify({
            "hata": f"Çok fazla başarısız deneme. {dakika} dakika sonra tekrar deneyin."
        }), 429

    k = query("SELECT * FROM kullanicilar WHERE email=%s AND aktif=1", (email,), fetch="one")

    # Şifre yanlış veya kullanıcı yok
    if not k or not sifre_dogru(sifre, k["sifre_hash"]):
        giris_denemesi_kaydet(email, basarili=False)
        # Timing attack önleme: kullanıcı olmasa bile bcrypt süresi kadar bekle
        if not k:
            bcrypt.checkpw(b"dummy", b"$2b$12$" + b"x" * 53)
        return jsonify({"hata": "E-posta veya şifre hatalı."}), 401

    # Başarılı giriş — sayacı sıfırla ve son giriş zamanını güncelle
    giris_denemesi_kaydet(email, basarili=True)
    query("UPDATE kullanicilar SET son_giris=NOW() WHERE id=%s", (k["id"],), fetch="none")
    oturum_ac(k)

    return jsonify({
        "basarili": True,
        "kullanici": {"id": k["id"], "ad": k["ad_soyad"], "email": k["email"], "rol": k["rol"]}
    })

# ─── ÇIKIŞ ────────────────────────────────────────────────────────────────────

@auth_bp.route("/cikis", methods=["POST", "GET"])
def cikis():
    session.clear()
    return jsonify({"basarili": True})

# ─── MEVCUT KULLANICI ─────────────────────────────────────────────────────────

@auth_bp.route("/ben", methods=["GET"])
def ben():
    if "kullanici_id" not in session:
        return jsonify({"giris": False}), 200

    k = query(
        "SELECT id, ad_soyad, email, rol, sehir, telefon, profil_foto "
        "FROM kullanicilar WHERE id=%s AND aktif=1",
        (session["kullanici_id"],), fetch="one"
    )
    if not k:
        session.clear()
        return jsonify({"giris": False}), 200

    extra = {}
    if k["rol"] == "uzman":
        profil = query(
            "SELECT * FROM uzman_profiller WHERE kullanici_id=%s",
            (k["id"],), fetch="one"
        )
        if profil:
            extra["profil"] = {
                "kategori":      profil["kategori"],
                "saatlik_ucret": profil["saatlik_ucret"],
                "puan":          float(profil["puan"]),
                "is_tamamlanan": profil["is_tamamlanan"],
                "onaylandi":     bool(profil["onaylandi"]),
                "uygunluk":      bool(profil["uygunluk"]),
            }

    return jsonify({"giris": True, "kullanici": {**k, **extra}})

# ─── PROFİL GÜNCELLE ──────────────────────────────────────────────────────────

@auth_bp.route("/profil-guncelle", methods=["POST"])
@giris_gerekli
@limiter.limit("10 per minute")
def profil_guncelle():
    b   = request.json or {}
    uid = session["kullanici_id"]

    query(
        "UPDATE kullanicilar SET ad_soyad=%s, telefon=%s, sehir=%s WHERE id=%s",
        (metin_temizle(b.get("ad_soyad",""), 120),
         metin_temizle(b.get("telefon",""), 20),
         metin_temizle(b.get("sehir",""), 80), uid),
        fetch="none"
    )
    if session["kullanici_rol"] == "uzman":
        query(
            "UPDATE uzman_profiller SET kategori=%s, saatlik_ucret=%s, aciklama=%s, uygunluk=%s "
            "WHERE kullanici_id=%s",
            (b.get("kategori"), int(b.get("saatlik_ucret", 0)),
             metin_temizle(b.get("aciklama",""), 1000),
             int(b.get("uygunluk", 1)), uid),
            fetch="none"
        )
    session["kullanici_ad"] = metin_temizle(b.get("ad_soyad", session["kullanici_ad"]), 120)
    return jsonify({"basarili": True})

# ─── ŞİFRE DEĞİŞTİR ──────────────────────────────────────────────────────────

@auth_bp.route("/sifre-degistir", methods=["POST"])
@giris_gerekli
@limiter.limit("3 per minute")   # Şifre değiştirme kısıtlaması
def sifre_degistir():
    b    = request.json or {}
    eski = b.get("eski_sifre", "")
    yeni = b.get("yeni_sifre", "")
    uid  = session["kullanici_id"]

    guclu, guc_mesaj = sifre_guclu(yeni)
    if not guclu:
        return jsonify({"hata": guc_mesaj}), 400

    k = query("SELECT sifre_hash FROM kullanicilar WHERE id=%s", (uid,), fetch="one")
    if not k or not sifre_dogru(eski, k["sifre_hash"]):
        return jsonify({"hata": "Mevcut şifre hatalı."}), 401

    query(
        "UPDATE kullanicilar SET sifre_hash=%s WHERE id=%s",
        (hash_sifre(yeni), uid), fetch="none"
    )
    return jsonify({"basarili": True})

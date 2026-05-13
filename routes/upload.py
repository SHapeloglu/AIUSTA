"""
╔══════════════════════════════════════════════════════════════╗
║           İştek Platform — Dosya ve Fotoğraf Yükleme        ║
╚══════════════════════════════════════════════════════════════╝

Pillow kütüphanesi ile görsel optimizasyonu yaparak dosya yükleme.

Özellikler:
    - Desteklenen formatlar: JPG, PNG, WebP, GIF
    - Maksimum boyut: 8MB (app.config ile kontrol edilir)
    - Otomatik boyut küçültme: maksimum 1200px genişlik
    - EXIF rotasyon düzeltme (telefon fotoğrafları için)
    - JPEG kalite optimizasyonu (%85)
    - Eski fotoğraf otomatik silme

Rotalar:
    POST   /upload/profil-foto              → Profil fotoğrafı (1 adet)
    POST   /upload/ilan-foto                → İlan görseli (max 5 adet)
    POST   /upload/portfolyo                → Uzman portfolyo (max 10 adet)
    GET    /upload/fotograflar/ilan/<id>    → İlan fotoğrafları
    GET    /upload/fotograflar/portfolyo/<id> → Portfolyo görselleri
    DELETE /upload/sil/ilan-foto/<id>       → İlan fotoğrafı sil
    DELETE /upload/sil/portfolyo/<id>       → Portfolyo görseli sil
"""

import os, uuid
from flask import Blueprint, request, jsonify, session, current_app
from PIL import Image
from werkzeug.utils import secure_filename
from database import query
from routes.auth import giris_gerekli

upload_bp = Blueprint("upload", __name__, url_prefix="/upload")

# ─── AYARLAR ──────────────────────────────────────────────────────────────────
UPLOAD_KLASOR   = os.path.join("static", "uploads")
KIMLIK_KLASOR   = os.path.join("kimlik_belgeleri")  # static DIŞINDA — web'e kapalı
IZIN_UZANTILAR  = {"jpg", "jpeg", "png", "webp", "gif"}
MAX_BOYUT_MB    = 8
MAX_GENISLIK    = 1200   # px — daha büyük görseller küçültülür
KALITE          = 85     # JPEG kalitesi
# ─────────────────────────────────────────────────────────────────────────────

def izinli_dosya(dosya_adi):
    return "." in dosya_adi and dosya_adi.rsplit(".", 1)[1].lower() in IZIN_UZANTILAR

def gorseli_isle(dosya, alt_klasor):
    """Dosyayı optimize eder, kaydeder, göreceli yolu döner."""
    if not izinli_dosya(dosya.filename):
        raise ValueError("Desteklenmeyen dosya türü. (jpg, png, webp, gif)")

    if dosya.content_length and dosya.content_length > MAX_BOYUT_MB * 1024 * 1024:
        raise ValueError(f"Dosya {MAX_BOYUT_MB}MB'den büyük olamaz.")

    # Gerçek MIME type doğrula — uzantıya güvenmek yeterli değil
    from security import dosya_mime_guvenlimi
    if not dosya_mime_guvenlimi(dosya.stream):
        raise ValueError("Dosya içeriği geçersiz. Sadece görsel dosyalar kabul edilir.")

    uzanti   = dosya.filename.rsplit(".", 1)[1].lower()
    uzanti   = "jpg" if uzanti == "jpeg" else uzanti
    dosya_adi = f"{uuid.uuid4().hex}.{uzanti}"
    klasor   = os.path.join(UPLOAD_KLASOR, alt_klasor)
    os.makedirs(klasor, exist_ok=True)
    tam_yol  = os.path.join(klasor, dosya_adi)

    img = Image.open(dosya.stream)

    # EXIF rotasyonu düzelt
    try:
        from PIL.ExifTags import TAGS
        exif = img._getexif()
        if exif:
            for tag, val in exif.items():
                if TAGS.get(tag) == "Orientation":
                    rotations = {3:180, 6:270, 8:90}
                    if val in rotations:
                        img = img.rotate(rotations[val], expand=True)
    except Exception:
        pass

    # Boyut küçült
    if img.width > MAX_GENISLIK:
        oran = MAX_GENISLIK / img.width
        img  = img.resize((MAX_GENISLIK, int(img.height * oran)), Image.LANCZOS)

    # RGBA → RGB (jpg için)
    if uzanti == "jpg" and img.mode in ("RGBA", "P"):
        arka = Image.new("RGB", img.size, (255, 255, 255))
        arka.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
        img = arka

    fmt = "JPEG" if uzanti == "jpg" else uzanti.upper()
    img.save(tam_yol, fmt, quality=KALITE, optimize=True)

    return f"/static/uploads/{alt_klasor}/{dosya_adi}", dosya_adi

# ── Profil fotoğrafı ──────────────────────────────────────────────────────────

@upload_bp.route("/profil-foto", methods=["POST"])
@giris_gerekli
def profil_foto():
    if "foto" not in request.files:
        return jsonify({"hata": "Dosya seçilmedi."}), 400

    dosya = request.files["foto"]
    uid   = session["kullanici_id"]

    try:
        url, dosya_adi = gorseli_isle(dosya, "profil")
    except ValueError as e:
        return jsonify({"hata": str(e)}), 400

    # Eski fotoğrafı sil
    eski = query("SELECT profil_foto FROM kullanicilar WHERE id=%s", (uid,), fetch="one")
    if eski and eski.get("profil_foto"):
        eski_yol = os.path.join("static", eski["profil_foto"].lstrip("/static/"))
        if os.path.exists(eski_yol):
            os.remove(eski_yol)

    query("UPDATE kullanicilar SET profil_foto=%s WHERE id=%s", (url, uid), fetch="none")
    return jsonify({"basarili": True, "url": url})

# ── İlan fotoğrafları (max 5) ─────────────────────────────────────────────────

@upload_bp.route("/ilan-foto", methods=["POST"])
@giris_gerekli
def ilan_foto():
    ilan_id = request.form.get("ilan_id")
    if not ilan_id:
        return jsonify({"hata": "ilan_id zorunlu."}), 400

    ilan = query("SELECT * FROM ilanlar WHERE id=%s AND musteri_id=%s",
                 (ilan_id, session["kullanici_id"]), fetch="one")
    if not ilan:
        return jsonify({"hata": "İlan bulunamadı veya yetkiniz yok."}), 404

    mevcut = query("SELECT COUNT(*) AS n FROM ilan_fotograflar WHERE ilan_id=%s",
                   (ilan_id,), fetch="one")["n"]
    if mevcut >= 5:
        return jsonify({"hata": "Bir ilana en fazla 5 fotoğraf eklenebilir."}), 400

    yuklenenler = []
    for dosya in request.files.getlist("foto"):
        try:
            url, _ = gorseli_isle(dosya, "ilan")
            fid    = str(uuid.uuid4())
            query(
                "INSERT INTO ilan_fotograflar (id, ilan_id, url, sira) VALUES (%s,%s,%s,%s)",
                (fid, ilan_id, url, mevcut + len(yuklenenler)), fetch="none"
            )
            yuklenenler.append({"id": fid, "url": url})
        except ValueError as e:
            return jsonify({"hata": str(e)}), 400

    return jsonify({"basarili": True, "fotograflar": yuklenenler})

# ── Portfolyo (uzman, max 10) ─────────────────────────────────────────────────

@upload_bp.route("/portfolyo", methods=["POST"])
@giris_gerekli
def portfolyo():
    if session["kullanici_rol"] != "uzman":
        return jsonify({"hata": "Sadece uzmanlar portfolyo ekleyebilir."}), 403

    uid     = session["kullanici_id"]
    aciklama = request.form.get("aciklama", "")

    mevcut = query("SELECT COUNT(*) AS n FROM portfolyo WHERE uzman_id=%s",
                   (uid,), fetch="one")["n"]
    if mevcut >= 10:
        return jsonify({"hata": "En fazla 10 portfolyo görseli eklenebilir."}), 400

    yuklenenler = []
    for dosya in request.files.getlist("foto"):
        try:
            url, _ = gorseli_isle(dosya, "portfolyo")
            pid    = str(uuid.uuid4())
            query(
                "INSERT INTO portfolyo (id, uzman_id, url, aciklama) VALUES (%s,%s,%s,%s)",
                (pid, uid, url, aciklama), fetch="none"
            )
            yuklenenler.append({"id": pid, "url": url, "aciklama": aciklama})
        except ValueError as e:
            return jsonify({"hata": str(e)}), 400

    return jsonify({"basarili": True, "fotograflar": yuklenenler})

# ── Fotoğraf getir ────────────────────────────────────────────────────────────

@upload_bp.route("/fotograflar/ilan/<ilan_id>", methods=["GET"])
def ilan_fotograflari(ilan_id):
    rows = query(
        "SELECT id, url, sira FROM ilan_fotograflar WHERE ilan_id=%s ORDER BY sira",
        (ilan_id,)
    )
    return jsonify(rows)

@upload_bp.route("/fotograflar/portfolyo/<uzman_id>", methods=["GET"])
def portfolyo_fotograflari(uzman_id):
    rows = query(
        "SELECT id, url, aciklama FROM portfolyo WHERE uzman_id=%s ORDER BY olusturma DESC",
        (uzman_id,)
    )
    return jsonify(rows)

# ── Fotoğraf sil ──────────────────────────────────────────────────────────────

@upload_bp.route("/sil/ilan-foto/<foto_id>", methods=["DELETE"])
@giris_gerekli
def ilan_foto_sil(foto_id):
    uid  = session["kullanici_id"]
    foto = query("""
        SELECT f.* FROM ilan_fotograflar f
        JOIN ilanlar i ON i.id=f.ilan_id
        WHERE f.id=%s AND i.musteri_id=%s
    """, (foto_id, uid), fetch="one")
    if not foto:
        return jsonify({"hata": "Fotoğraf bulunamadı."}), 404
    _dosya_sil(foto["url"])
    query("DELETE FROM ilan_fotograflar WHERE id=%s", (foto_id,), fetch="none")
    return jsonify({"basarili": True})

@upload_bp.route("/sil/portfolyo/<foto_id>", methods=["DELETE"])
@giris_gerekli
def portfolyo_sil(foto_id):
    uid  = session["kullanici_id"]
    foto = query("SELECT * FROM portfolyo WHERE id=%s AND uzman_id=%s",
                 (foto_id, uid), fetch="one")
    if not foto:
        return jsonify({"hata": "Fotoğraf bulunamadı."}), 404
    _dosya_sil(foto["url"])
    query("DELETE FROM portfolyo WHERE id=%s", (foto_id,), fetch="none")
    return jsonify({"basarili": True})

def _dosya_sil(url):
    yol = os.path.join("static", url.lstrip("/static/"))
    if os.path.exists(yol):
        try:
            os.remove(yol)
        except Exception:
            pass

# ── Veritabanı tabloları ──────────────────────────────────────────────────────

UPLOAD_SCHEMA = [
    """ALTER TABLE kullanicilar ADD COLUMN IF NOT EXISTS profil_foto VARCHAR(255) DEFAULT NULL""",
    """CREATE TABLE IF NOT EXISTS ilan_fotograflar (
        id         VARCHAR(36) PRIMARY KEY,
        ilan_id    VARCHAR(36) NOT NULL,
        url        VARCHAR(255) NOT NULL,
        sira       INT DEFAULT 0,
        olusturma  DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ilan_id) REFERENCES ilanlar(id) ON DELETE CASCADE,
        INDEX idx_ilan (ilan_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS portfolyo (
        id         VARCHAR(36) PRIMARY KEY,
        uzman_id   VARCHAR(36) NOT NULL,
        url        VARCHAR(255) NOT NULL,
        aciklama   VARCHAR(300),
        olusturma  DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (uzman_id) REFERENCES kullanicilar(id) ON DELETE CASCADE,
        INDEX idx_uzman (uzman_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
]

def init_upload_db():
    from database import query as q
    for sql in UPLOAD_SCHEMA:
        try:
            q(sql, fetch="none")
        except Exception as e:
            print(f"[Upload DB] {e}")

"""
╔══════════════════════════════════════════════════════════════╗
║           İştek Platform — Takvim ve Randevu Sistemi        ║
╚══════════════════════════════════════════════════════════════╝

Uzman müsaitlik takvimi ve çakışma kontrollü randevu sistemi.

Özellikler:
    - Uzman günlük müsaitlik ayarlama (09:00-18:00 varsayılan)
    - Haftasonu otomatik kapalı (özelleştirilebilir)
    - Çakışma kontrolü: aynı anda iki randevu olamaz
    - Randevu onay/iptal akışı + SMS + bildirim

Rotalar:
    GET  /takvim/musaitlik/<uzman_id>   → 60 günlük müsaitlik takvimi
    POST /takvim/musaitlik              → Uzman müsaitlik ayarla
    POST /takvim/randevu                → Randevu oluştur
    POST /takvim/randevu/<id>/onayla    → Randevuyu onayla
    POST /takvim/randevu/<id>/iptal     → Randevuyu iptal et
    GET  /takvim/randevularim           → Kullanıcının randevuları
"""

from flask import Blueprint, request, jsonify, session
from database import query
import uuid
from datetime import datetime, timedelta
from routes.auth import giris_gerekli, bildirim_olustur

takvim_bp = Blueprint("takvim", __name__, url_prefix="/takvim")

# ─── Takvim şeması ────────────────────────────────────────────────────────────
TAKVIM_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS musaitlik (
        id          VARCHAR(36) PRIMARY KEY,
        uzman_id    VARCHAR(36) NOT NULL,
        tarih       DATE        NOT NULL,
        baslangic   TIME        DEFAULT '09:00:00',
        bitis       TIME        DEFAULT '18:00:00',
        musait      TINYINT(1)  DEFAULT 1,
        UNIQUE KEY tek_gun (uzman_id, tarih),
        FOREIGN KEY (uzman_id) REFERENCES kullanicilar(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    """CREATE TABLE IF NOT EXISTS randevular (
        id          VARCHAR(36) PRIMARY KEY,
        ilan_id     VARCHAR(36) NOT NULL,
        uzman_id    VARCHAR(36) NOT NULL,
        musteri_id  VARCHAR(36) NOT NULL,
        tarih       DATE        NOT NULL,
        baslangic   TIME        NOT NULL,
        bitis       TIME        NOT NULL,
        durum       ENUM('beklemede','onaylandi','iptal') DEFAULT 'beklemede',
        not_metni   TEXT,
        olusturma   DATETIME    DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ilan_id)    REFERENCES ilanlar(id)      ON DELETE CASCADE,
        FOREIGN KEY (uzman_id)   REFERENCES kullanicilar(id) ON DELETE CASCADE,
        FOREIGN KEY (musteri_id) REFERENCES kullanicilar(id) ON DELETE CASCADE,
        INDEX idx_uzman_tarih (uzman_id, tarih)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
]

def init_takvim():
    from database import query as q
    for sql in TAKVIM_SCHEMA:
        q(sql, fetch="none")

# ── Uzmanın müsait günleri ────────────────────────────────────────────────────

@takvim_bp.route("/musaitlik/<uzman_id>", methods=["GET"])
def musaitlik_getir(uzman_id):
    """Bir sonraki 60 günün müsaitlik durumunu döner."""
    bugun = datetime.now().date()
    son   = bugun + timedelta(days=60)

    kayitlar = query(
        "SELECT tarih, baslangic, bitis, musait FROM musaitlik "
        "WHERE uzman_id=%s AND tarih BETWEEN %s AND %s ORDER BY tarih",
        (uzman_id, bugun.isoformat(), son.isoformat())
    )

    musait_map = {str(r["tarih"]): r for r in kayitlar}

    # Randevu olanları bul
    randevular = query(
        "SELECT tarih FROM randevular WHERE uzman_id=%s AND durum='onaylandi' "
        "AND tarih BETWEEN %s AND %s",
        (uzman_id, bugun.isoformat(), son.isoformat())
    )
    dolu_gunler = {str(r["tarih"]) for r in randevular}

    gunler = []
    d = bugun
    while d <= son:
        ds = d.isoformat()
        if ds in musait_map:
            r = musait_map[ds]
            gunler.append({
                "tarih":     ds,
                "musait":    bool(r["musait"]) and ds not in dolu_gunler,
                "baslangic": str(r["baslangic"]),
                "bitis":     str(r["bitis"]),
                "dolu":      ds in dolu_gunler,
            })
        else:
            hf = d.weekday()  # 5=Cmt, 6=Pzr
            gunler.append({
                "tarih":     ds,
                "musait":    hf < 5,
                "baslangic": "09:00",
                "bitis":     "18:00",
                "dolu":      ds in dolu_gunler,
            })
        d += timedelta(days=1)

    return jsonify(gunler)

# ── Uzman kendi müsaitliğini ayarlar ──────────────────────────────────────────

@takvim_bp.route("/musaitlik", methods=["POST"])
@giris_gerekli
def musaitlik_ayarla():
    b   = request.json or {}
    uid = session["kullanici_id"]
    if session["kullanici_rol"] != "uzman":
        return jsonify({"hata": "Sadece uzmanlar müsaitlik ayarlayabilir."}), 403

    gunler = b.get("gunler", [])   # [{tarih, musait, baslangic, bitis}]
    for g in gunler:
        query(
            """INSERT INTO musaitlik (id, uzman_id, tarih, baslangic, bitis, musait)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE baslangic=%s, bitis=%s, musait=%s""",
            (str(uuid.uuid4()), uid, g["tarih"],
             g.get("baslangic","09:00"), g.get("bitis","18:00"), int(g.get("musait",1)),
             g.get("baslangic","09:00"), g.get("bitis","18:00"), int(g.get("musait",1))),
            fetch="none"
        )
    return jsonify({"basarili": True, "guncellenen": len(gunler)})

# ── Randevu oluştur ───────────────────────────────────────────────────────────

@takvim_bp.route("/randevu", methods=["POST"])
@giris_gerekli
def randevu_olustur():
    b          = request.json or {}
    uid        = session["kullanici_id"]
    uzman_id   = b.get("uzman_id")
    tarih      = b.get("tarih")
    baslangic  = b.get("baslangic", "09:00")
    bitis      = b.get("bitis", "10:00")
    ilan_id    = b.get("ilan_id")

    # Çakışma kontrolü
    cakisma = query(
        "SELECT id FROM randevular WHERE uzman_id=%s AND tarih=%s AND durum='onaylandi' "
        "AND NOT (bitis <= %s OR baslangic >= %s)",
        (uzman_id, tarih, baslangic, bitis), fetch="one"
    )
    if cakisma:
        return jsonify({"hata": "Bu saatte uzman başka bir randevuya sahip."}), 409

    rid = str(uuid.uuid4())
    query(
        "INSERT INTO randevular (id, ilan_id, uzman_id, musteri_id, tarih, baslangic, bitis, not_metni) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (rid, ilan_id, uzman_id, uid, tarih, baslangic, bitis, b.get("not_metni","")),
        fetch="none"
    )

    # Bildirim
    uzman   = query("SELECT ad_soyad FROM kullanicilar WHERE id=%s", (uzman_id,), fetch="one")
    musteri = query("SELECT ad_soyad FROM kullanicilar WHERE id=%s", (uid,), fetch="one")

    bildirim_olustur(uzman_id, "randevu",
        f"Yeni randevu talebi",
        f"{musteri['ad_soyad']} — {tarih} {baslangic}",
        f"/takvim/randevularim")

    bildirim_olustur(uid, "randevu",
        "Randevu talebiniz alındı",
        f"{uzman['ad_soyad']} ile {tarih} {baslangic}",
        f"/takvim/randevularim")

    return jsonify({"basarili": True, "id": rid}), 201

# ── Randevuyu onayla / iptal et ───────────────────────────────────────────────

@takvim_bp.route("/randevu/<rid>/onayla", methods=["POST"])
@giris_gerekli
def randevu_onayla(rid):
    uid = session["kullanici_id"]
    r   = query("SELECT * FROM randevular WHERE id=%s AND uzman_id=%s", (rid, uid), fetch="one")
    if not r:
        return jsonify({"hata": "Randevu bulunamadı."}), 404
    query("UPDATE randevular SET durum='onaylandi' WHERE id=%s", (rid,), fetch="none")
    bildirim_olustur(r["musteri_id"], "randevu", "Randevunuz Onaylandı ✅",
                     f"{r['tarih']} {r['baslangic']} randevunuz onaylandı.")
    return jsonify({"basarili": True})

@takvim_bp.route("/randevu/<rid>/iptal", methods=["POST"])
@giris_gerekli
def randevu_iptal(rid):
    uid = session["kullanici_id"]
    r   = query("SELECT * FROM randevular WHERE id=%s AND (uzman_id=%s OR musteri_id=%s)",
                (rid, uid, uid), fetch="one")
    if not r:
        return jsonify({"hata": "Randevu bulunamadı."}), 404
    query("UPDATE randevular SET durum='iptal' WHERE id=%s", (rid,), fetch="none")
    hedef = r["musteri_id"] if r["uzman_id"] == uid else r["uzman_id"]
    bildirim_olustur(hedef, "randevu", "Randevu İptal Edildi",
                     f"{r['tarih']} {r['baslangic']} randevusu iptal edildi.")
    return jsonify({"basarili": True})

# ── Kullanıcının randevuları ───────────────────────────────────────────────────

@takvim_bp.route("/randevularim", methods=["GET"])
@giris_gerekli
def randevularim():
    uid = session["kullanici_id"]
    rol = session["kullanici_rol"]

    if rol == "uzman":
        rows = query("""
            SELECT r.*, i.baslik AS ilan_baslik, k.ad_soyad AS musteri_ad
            FROM randevular r
            JOIN ilanlar i ON i.id=r.ilan_id
            JOIN kullanicilar k ON k.id=r.musteri_id
            WHERE r.uzman_id=%s ORDER BY r.tarih, r.baslangic
        """, (uid,))
    else:
        rows = query("""
            SELECT r.*, i.baslik AS ilan_baslik, k.ad_soyad AS uzman_ad
            FROM randevular r
            JOIN ilanlar i ON i.id=r.ilan_id
            JOIN kullanicilar k ON k.id=r.uzman_id
            WHERE r.musteri_id=%s ORDER BY r.tarih, r.baslangic
        """, (uid,))

    for r in rows:
        r["tarih"]     = str(r["tarih"])
        r["baslangic"] = str(r["baslangic"])
        r["bitis"]     = str(r["bitis"])
        r["olusturma"] = str(r["olusturma"])
    return jsonify(rows)


# ─── Eksik Admin API Rotaları ─────────────────────────────────────────────────

admin_extra_bp = Blueprint("admin_extra", __name__, url_prefix="/api/admin")

def admin_gerekli(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("kullanici_rol") != "admin":
            return jsonify({"hata": "Yetkisiz."}), 403
        return f(*args, **kwargs)
    return decorated

@admin_extra_bp.route("/son-kullanicilar")
@giris_gerekli
@admin_gerekli
def son_kullanicilar():
    rows = query(
        "SELECT id, ad_soyad, email, rol, sehir, aktif, kayit_tarihi "
        "FROM kullanicilar ORDER BY kayit_tarihi DESC LIMIT 10"
    )
    for r in rows:
        if r.get("kayit_tarihi"): r["kayit_tarihi"] = str(r["kayit_tarihi"])
    return jsonify(rows)

@admin_extra_bp.route("/kullanicilar")
@giris_gerekli
@admin_gerekli
def tum_kullanicilar():
    rol = request.args.get("rol","")
    sql = "SELECT id, ad_soyad, email, rol, sehir, aktif, kayit_tarihi FROM kullanicilar WHERE 1=1"
    p   = []
    if rol: sql += " AND rol=%s"; p.append(rol)
    sql += " ORDER BY kayit_tarihi DESC"
    rows = query(sql, p)
    for r in rows:
        if r.get("kayit_tarihi"): r["kayit_tarihi"] = str(r["kayit_tarihi"])
    return jsonify(rows)

@admin_extra_bp.route("/kullanici-ban/<uid>", methods=["POST"])
@giris_gerekli
@admin_gerekli
def kullanici_ban(uid):
    query("UPDATE kullanicilar SET aktif=0 WHERE id=%s AND rol!='admin'", (uid,), fetch="none")
    return jsonify({"basarili": True})

@admin_extra_bp.route("/ilan-kapat/<ilan_id>", methods=["POST"])
@giris_gerekli
@admin_gerekli
def ilan_kapat(ilan_id):
    query("UPDATE ilanlar SET durum='iptal' WHERE id=%s", (ilan_id,), fetch="none")
    return jsonify({"basarili": True})

@admin_extra_bp.route("/son-mesajlar")
@giris_gerekli
@admin_gerekli
def son_mesajlar():
    rows = query("""
        SELECT m.*, g.ad_soyad AS gonderen_ad, a.ad_soyad AS alici_ad
        FROM mesajlar m
        JOIN kullanicilar g ON g.id=m.gonderen_id
        JOIN kullanicilar a ON a.id=m.alici_id
        ORDER BY m.tarih DESC LIMIT 50
    """)
    for r in rows:
        if r.get("tarih"): r["tarih"] = str(r["tarih"])
    return jsonify(rows)

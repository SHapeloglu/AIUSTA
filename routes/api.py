"""
╔══════════════════════════════════════════════════════════════╗
║           İştek Platform — Ana API Rotaları                 ║
╚══════════════════════════════════════════════════════════════╝

Platform'un temel iş mantığı rotaları.

Rotalar:
    GET  /api/uzmanlar              → Uzman listesi (filtre + sıralama)
    GET  /api/uzman/<id>            → Tek uzman detayı + yorumlar
    GET  /api/ilanlar               → Aktif ilan listesi
    POST /api/ilanlar               → Yeni ilan oluştur (giriş gerekli)
    POST /api/teklif                → İlana teklif ver (uzman)
    POST /api/degerlendirme         → İş sonrası yorum yaz
    GET  /api/bildirimler           → Kullanıcı bildirimleri
    POST /api/bildirimler/okundu    → Tümünü okundu işaretle
    GET  /api/istatistik            → Platform geneli istatistikler

    Admin rotaları (/api/admin/*):
    GET  /api/admin/ozet            → Genel platform özeti
    GET  /api/admin/uzmanlar-bekleyen → Onay bekleyen uzmanlar
    POST /api/admin/uzman-onayla/<id> → Uzmanı onayla
"""

from flask import Blueprint, request, jsonify, session
from database import query
import uuid
from datetime import datetime

api_bp = Blueprint("api", __name__, url_prefix="/api")
from routes.auth import giris_gerekli, bildirim_olustur

KATEGORILER = [
    {"id":"temizlik","ad":"Ev Temizliği","ikon":"🧹"},
    {"id":"tamirat","ad":"Tamirat & Montaj","ikon":"🔧"},
    {"id":"nakliyat","ad":"Nakliyat & Taşıma","ikon":"🚚"},
    {"id":"bahce","ad":"Bahçe & Peyzaj","ikon":"🌿"},
    {"id":"boya","ad":"Boya & Badana","ikon":"🎨"},
    {"id":"elektrik","ad":"Elektrik İşleri","ikon":"⚡"},
    {"id":"tesisaat","ad":"Tesisat İşleri","ikon":"🚿"},
    {"id":"guvenlik","ad":"Güvenlik & Kamera","ikon":"🔐"},
    {"id":"klima","ad":"Klima & Isıtma","ikon":"❄️"},
    {"id":"diger","ad":"Diğer İşler","ikon":"📦"},
]

# ── Uzmanlar ──────────────────────────────────────────────────────────────────

@api_bp.route("/uzmanlar", methods=["GET"])
def uzmanlar():
    kategori = request.args.get("kategori","")
    sehir    = request.args.get("sehir","")
    arama    = request.args.get("arama","")
    siralama = request.args.get("siralama","puan")  # puan | ucret | is

    sql = """
        SELECT k.id, k.ad_soyad, k.sehir, k.email,
               p.kategori, p.saatlik_ucret, p.puan, p.is_tamamlanan,
               p.aciklama, p.uygunluk, p.onaylandi
        FROM kullanicilar k
        JOIN uzman_profiller p ON p.kullanici_id = k.id
        WHERE k.aktif=1 AND p.onaylandi=1
    """
    params = []
    if kategori: sql += " AND p.kategori=%s";                  params.append(kategori)
    if sehir:    sql += " AND k.sehir=%s";                     params.append(sehir)
    if arama:
        sql += " AND (k.ad_soyad LIKE %s OR p.aciklama LIKE %s)"
        params += [f"%{arama}%", f"%{arama}%"]

    if siralama == "ucret":  sql += " ORDER BY p.saatlik_ucret ASC"
    elif siralama == "is":   sql += " ORDER BY p.is_tamamlanan DESC"
    else:                    sql += " ORDER BY p.puan DESC"

    rows = query(sql, params)
    for r in rows:
        r["puan"]    = float(r["puan"])
        r["avatar"]  = r["ad_soyad"][0]
        r["fiyat"]   = r["saatlik_ucret"]
        r["isTamamlanan"] = r["is_tamamlanan"]
    return jsonify(rows)

# ── Uzman Detay ───────────────────────────────────────────────────────────────

@api_bp.route("/uzman/<uzman_id>", methods=["GET"])
def uzman_detay(uzman_id):
    k = query("""
        SELECT k.id, k.ad_soyad, k.sehir,
               p.kategori, p.saatlik_ucret, p.puan, p.is_tamamlanan,
               p.aciklama, p.uygunluk, p.onaylandi
        FROM kullanicilar k
        JOIN uzman_profiller p ON p.kullanici_id=k.id
        WHERE k.id=%s AND k.aktif=1
    """, (uzman_id,), fetch="one")
    if not k:
        return jsonify({"hata": "Uzman bulunamadı."}), 404

    k["puan"]   = float(k["puan"])
    k["avatar"] = k["ad_soyad"][0]
    k["fiyat"]  = k["saatlik_ucret"]

    yorumlar = query("""
        SELECT d.puan, d.yorum, k2.ad_soyad AS musteri_ad, d.tarih
        FROM degerlendirmeler d
        JOIN kullanicilar k2 ON k2.id=d.musteri_id
        WHERE d.uzman_id=%s ORDER BY d.tarih DESC LIMIT 5
    """, (uzman_id,))
    for y in yorumlar:
        if y.get("tarih"): y["tarih"] = str(y["tarih"])

    k["yorumlar"] = yorumlar
    return jsonify(k)

# ── İlanlar ───────────────────────────────────────────────────────────────────

@api_bp.route("/ilanlar", methods=["GET"])
def ilanlar():
    kategori = request.args.get("kategori","")
    sehir    = request.args.get("sehir","")
    sql = """
        SELECT i.*, COUNT(t.id) AS teklif_sayisi
        FROM ilanlar i
        LEFT JOIN teklifler t ON t.ilan_id=i.id
        WHERE i.durum='aktif'
    """
    p = []
    if kategori: sql += " AND i.kategori=%s"; p.append(kategori)
    if sehir:    sql += " AND i.sehir=%s";    p.append(sehir)
    sql += " GROUP BY i.id ORDER BY i.olusturma_tarihi DESC"
    rows = query(sql, p)
    for r in rows:
        if r.get("olusturma_tarihi"): r["tarih"] = str(r["olusturma_tarihi"])
        r["teklifSayisi"] = int(r["teklif_sayisi"])
    return jsonify(rows)

# ── İlan Oluştur ──────────────────────────────────────────────────────────────

@api_bp.route("/ilanlar", methods=["POST"])
@giris_gerekli
def ilan_olustur():
    b  = request.json or {}
    uid = session["kullanici_id"]
    kid = query("SELECT ad_soyad FROM kullanicilar WHERE id=%s",(uid,),fetch="one")
    ilan_id = str(uuid.uuid4())
    query(
        "INSERT INTO ilanlar (id,baslik,kategori,sehir,butce,aciklama,musteri_id,musteri_ad) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (ilan_id, b.get("baslik"), b.get("kategori"), b.get("sehir"),
         b.get("butce",0), b.get("aciklama"), uid,
         kid["ad_soyad"] if kid else "Misafir"),
        fetch="none"
    )
    return jsonify({"basarili": True, "id": ilan_id}), 201

# ── Teklif Ver ────────────────────────────────────────────────────────────────

@api_bp.route("/teklif", methods=["POST"])
@giris_gerekli
def teklif_ver():
    b       = request.json or {}
    uid     = session["kullanici_id"]
    ilan_id = b.get("ilan_id")

    ilan = query("SELECT * FROM ilanlar WHERE id=%s AND durum='aktif'", (ilan_id,), fetch="one")
    if not ilan:
        return jsonify({"hata": "İlan bulunamadı veya kapalı."}), 404

    var = query("SELECT id FROM teklifler WHERE ilan_id=%s AND uzman_id=%s",(ilan_id,uid),fetch="one")
    if var:
        return jsonify({"hata": "Bu ilana zaten teklif verdiniz."}), 409

    tid = str(uuid.uuid4())
    query(
        "INSERT INTO teklifler (id,ilan_id,uzman_id,fiyat,mesaj) VALUES (%s,%s,%s,%s,%s)",
        (tid, ilan_id, uid, b.get("fiyat",0), b.get("mesaj","")),
        fetch="none"
    )

    uzman = query("SELECT ad_soyad FROM kullanicilar WHERE id=%s",(uid,),fetch="one")
    if ilan.get("musteri_id"):
        bildirim_olustur(
            ilan["musteri_id"], "teklif",
            f"Yeni teklif: {ilan['baslik']}",
            f"{uzman['ad_soyad']} ₺{b.get('fiyat',0)} teklif verdi.",
            f"/ilan/{ilan_id}"
        )

    return jsonify({"basarili": True, "id": tid}), 201

# ── Değerlendirme ─────────────────────────────────────────────────────────────

@api_bp.route("/degerlendirme", methods=["POST"])
@giris_gerekli
def degerlendirme_ekle():
    b        = request.json or {}
    uid      = session["kullanici_id"]
    uzman_id = b.get("uzman_id")
    ilan_id  = b.get("ilan_id")
    puan     = int(b.get("puan", 0))

    if not (1 <= puan <= 5):
        return jsonify({"hata": "Puan 1-5 arası olmalı."}), 400

    var = query("SELECT id FROM degerlendirmeler WHERE ilan_id=%s AND musteri_id=%s",
                (ilan_id, uid), fetch="one")
    if var:
        return jsonify({"hata": "Bu ilana zaten değerlendirme yaptınız."}), 409

    query(
        "INSERT INTO degerlendirmeler (id,ilan_id,uzman_id,musteri_id,puan,yorum) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (str(uuid.uuid4()), ilan_id, uzman_id, uid, puan, b.get("yorum","")),
        fetch="none"
    )

    # Ortalama puanı güncelle
    ort = query(
        "SELECT AVG(puan) AS p, COUNT(*) AS n FROM degerlendirmeler WHERE uzman_id=%s",
        (uzman_id,), fetch="one"
    )
    query(
        "UPDATE uzman_profiller SET puan=%s, is_tamamlanan=%s WHERE kullanici_id=%s",
        (round(float(ort["p"]),1), ort["n"], uzman_id), fetch="none"
    )
    return jsonify({"basarili": True})

# ── Bildirimler ───────────────────────────────────────────────────────────────

@api_bp.route("/bildirimler", methods=["GET"])
@giris_gerekli
def bildirimler():
    uid = session["kullanici_id"]
    rows = query(
        "SELECT * FROM bildirimler WHERE kullanici_id=%s ORDER BY tarih DESC LIMIT 20",
        (uid,)
    )
    for r in rows:
        if r.get("tarih"): r["tarih"] = str(r["tarih"])
    return jsonify(rows)

@api_bp.route("/bildirimler/okundu", methods=["POST"])
@giris_gerekli
def bildirimleri_okundu():
    uid = session["kullanici_id"]
    query("UPDATE bildirimler SET okundu=1 WHERE kullanici_id=%s", (uid,), fetch="none")
    return jsonify({"basarili": True})

# ── İstatistik ────────────────────────────────────────────────────────────────

@api_bp.route("/istatistik", methods=["GET"])
def istatistik():
    uzman = query("SELECT COUNT(*) AS n FROM uzman_profiller WHERE onaylandi=1",fetch="one")["n"]
    ilan  = query("SELECT COUNT(*) AS n FROM ilanlar WHERE durum='aktif'",fetch="one")["n"]
    tamam = query("SELECT COUNT(*) AS n FROM ilanlar WHERE durum='tamamlandi'",fetch="one")["n"]
    puan  = query("SELECT AVG(puan) AS p FROM uzman_profiller WHERE onaylandi=1",fetch="one")["p"] or 4.8
    return jsonify({
        "uzmanSayisi": uzman + 1200,
        "gorevSayisi": ilan  + 8400,
        "tamamlanan":  tamam + 7800,
        "memnuniyet":  round(float(puan),1),
    })

# ── Admin ─────────────────────────────────────────────────────────────────────

def admin_gerekli(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("kullanici_rol") != "admin":
            return jsonify({"hata": "Yetkisiz erişim."}), 403
        return f(*args, **kwargs)
    return decorated

@api_bp.route("/admin/uzmanlar-bekleyen", methods=["GET"])
@giris_gerekli
@admin_gerekli
def admin_bekleyen():
    rows = query("""
        SELECT k.id, k.ad_soyad, k.email, k.sehir, k.kayit_tarihi,
               p.kategori, p.saatlik_ucret, p.aciklama
        FROM kullanicilar k
        JOIN uzman_profiller p ON p.kullanici_id=k.id
        WHERE p.onaylandi=0
        ORDER BY k.kayit_tarihi DESC
    """)
    for r in rows:
        if r.get("kayit_tarihi"): r["kayit_tarihi"] = str(r["kayit_tarihi"])
    return jsonify(rows)

@api_bp.route("/admin/uzman-onayla/<uzman_id>", methods=["POST"])
@giris_gerekli
@admin_gerekli
def admin_onayla(uzman_id):
    query("UPDATE uzman_profiller SET onaylandi=1 WHERE kullanici_id=%s",(uzman_id,),fetch="none")
    bildirim_olustur(uzman_id,"sistem","Profiliniz onaylandı!",
                     "Artık iş ilanlarına teklif verebilirsiniz.","/dashboard")
    return jsonify({"basarili": True})

@api_bp.route("/admin/ozet", methods=["GET"])
@giris_gerekli
@admin_gerekli
def admin_ozet():
    return jsonify({
        "toplam_kullanici": query("SELECT COUNT(*) AS n FROM kullanicilar",fetch="one")["n"],
        "toplam_uzman":     query("SELECT COUNT(*) AS n FROM uzman_profiller",fetch="one")["n"],
        "bekleyen_uzman":   query("SELECT COUNT(*) AS n FROM uzman_profiller WHERE onaylandi=0",fetch="one")["n"],
        "aktif_ilan":       query("SELECT COUNT(*) AS n FROM ilanlar WHERE durum='aktif'",fetch="one")["n"],
        "toplam_odeme":     query("SELECT COALESCE(SUM(tutar),0) AS t FROM odemeler WHERE durum='onaylandi'",fetch="one")["t"],
        "toplam_mesaj":     query("SELECT COUNT(*) AS n FROM mesajlar",fetch="one")["n"],
    })

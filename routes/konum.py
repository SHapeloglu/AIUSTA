"""
╔══════════════════════════════════════════════════════════════╗
║           İştek Platform — GPS ve Konum Servisi             ║
╚══════════════════════════════════════════════════════════════╝

Haversine formülü ile mesafe hesaplama ve şehir otomatik algılama.

Özellikler:
    - 15 büyük Türkiye şehri koordinat veritabanı
    - GPS koordinatından en yakın şehri bulma (reverse geocode)
    - Yarıçap bazlı uzman arama (varsayılan 50 km)
    - Leaflet.js / Google Maps uyumlu harita pin verisi
    - Aynı şehirdeki uzmanlar için küçük konum sapması (pin çakışma önleme)

Rotalar:
    POST /konum/yakinimda          → GPS koordinatına göre yakın uzmanlar
    GET  /konum/sehir-bul          → lat/lng → en yakın şehir adı
    GET  /konum/uzmanlar-harita    → Tüm uzmanların harita pin koordinatları
    GET  /konum/sehirler           → Şehir listesi ve koordinatları
"""

from flask import Blueprint, request, jsonify, session
from database import query
import math, requests as req

konum_bp = Blueprint("konum", __name__, url_prefix="/konum")

# ─── Türkiye şehir koordinatları ─────────────────────────────────────────────
SEHIR_KOORDINATLARI = {
    "İstanbul":  {"lat": 41.0082,  "lng": 28.9784},
    "Ankara":    {"lat": 39.9334,  "lng": 32.8597},
    "İzmir":     {"lat": 38.4237,  "lng": 27.1428},
    "Bursa":     {"lat": 40.1885,  "lng": 29.0610},
    "Antalya":   {"lat": 36.8969,  "lng": 30.7133},
    "Adana":     {"lat": 37.0000,  "lng": 35.3213},
    "Konya":     {"lat": 37.8746,  "lng": 32.4932},
    "Gaziantep": {"lat": 37.0662,  "lng": 37.3833},
    "Mersin":    {"lat": 36.8121,  "lng": 34.6415},
    "Kayseri":   {"lat": 38.7312,  "lng": 35.4787},
    "Eskişehir": {"lat": 39.7767,  "lng": 30.5206},
    "Trabzon":   {"lat": 41.0015,  "lng": 39.7178},
    "Samsun":    {"lat": 41.2867,  "lng": 36.3300},
    "Denizli":   {"lat": 37.7765,  "lng": 29.0864},
    "Balıkesir": {"lat": 39.6484,  "lng": 27.8826},
}

def haversine_km(lat1, lng1, lat2, lng2) -> float:
    """İki koordinat arasındaki mesafeyi km cinsinden hesaplar."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2)
    return R * 2 * math.asin(math.sqrt(a))

def en_yakin_sehir(lat: float, lng: float) -> str:
    """Verilen koordinata en yakın Türkiye şehrini döner."""
    en_yakin, min_mesafe = "İstanbul", float("inf")
    for sehir, koord in SEHIR_KOORDINATLARI.items():
        d = haversine_km(lat, lng, koord["lat"], koord["lng"])
        if d < min_mesafe:
            min_mesafe, en_yakin = d, sehir
    return en_yakin

# ── Yakındaki uzmanlar ────────────────────────────────────────────────────────

@konum_bp.route("/yakinimda", methods=["POST"])
def yakin_uzmanlar():
    b        = request.json or {}
    lat      = float(b.get("lat", 0))
    lng      = float(b.get("lng", 0))
    yaricap  = float(b.get("yaricap_km", 50))  # varsayılan 50 km
    kategori = b.get("kategori", "")

    if not lat or not lng:
        return jsonify({"hata": "lat ve lng zorunlu."}), 400

    # En yakın şehri bul
    sehir = en_yakin_sehir(lat, lng)

    sql = """
        SELECT k.id, k.ad_soyad, k.sehir,
               p.kategori, p.saatlik_ucret, p.puan,
               p.is_tamamlanan, p.aciklama, p.uygunluk
        FROM kullanicilar k
        JOIN uzman_profiller p ON p.kullanici_id = k.id
        WHERE k.aktif=1 AND p.onaylandi=1 AND p.uygunluk=1
    """
    params = []
    if kategori:
        sql += " AND p.kategori=%s"
        params.append(kategori)

    uzmanlar = query(sql, params)

    sonuc = []
    for u in uzmanlar:
        uzman_sehir  = u.get("sehir", "")
        sehir_koord  = SEHIR_KOORDINATLARI.get(uzman_sehir)
        if not sehir_koord:
            continue

        mesafe = haversine_km(lat, lng, sehir_koord["lat"], sehir_koord["lng"])
        if mesafe <= yaricap:
            sonuc.append({
                "id":            u["id"],
                "ad_soyad":      u["ad_soyad"],
                "sehir":         uzman_sehir,
                "kategori":      u["kategori"],
                "puan":          float(u["puan"] or 0),
                "saatlik_ucret": u["saatlik_ucret"],
                "aciklama":      u["aciklama"],
                "avatar":        u["ad_soyad"][0],
                "mesafe_km":     round(mesafe, 1),
                "lat":           sehir_koord["lat"],
                "lng":           sehir_koord["lng"],
            })

    sonuc.sort(key=lambda x: x["mesafe_km"])
    return jsonify({
        "sehir":        sehir,
        "yaricap_km":   yaricap,
        "uzman_sayisi": len(sonuc),
        "uzmanlar":     sonuc,
    })

# ── Şehir bul (reverse geocode) ───────────────────────────────────────────────

@konum_bp.route("/sehir-bul", methods=["GET"])
def sehir_bul():
    try:
        lat = float(request.args.get("lat", 0))
        lng = float(request.args.get("lng", 0))
    except ValueError:
        return jsonify({"hata": "Geçersiz koordinat."}), 400

    sehir = en_yakin_sehir(lat, lng)
    koord = SEHIR_KOORDINATLARI[sehir]
    mesafe = haversine_km(lat, lng, koord["lat"], koord["lng"])

    return jsonify({
        "sehir":       sehir,
        "mesafe_km":   round(mesafe, 1),
        "lat":         lat,
        "lng":         lng,
    })

# ── Harita verisi ─────────────────────────────────────────────────────────────

@konum_bp.route("/uzmanlar-harita", methods=["GET"])
def uzmanlar_harita():
    """Leaflet.js veya Google Maps için uzman pin verileri."""
    kategori = request.args.get("kategori", "")
    sql = """
        SELECT k.id, k.ad_soyad, k.sehir,
               p.kategori, p.saatlik_ucret, p.puan
        FROM kullanicilar k
        JOIN uzman_profiller p ON p.kullanici_id=k.id
        WHERE k.aktif=1 AND p.onaylandi=1 AND p.uygunluk=1
    """
    params = []
    if kategori:
        sql += " AND p.kategori=%s"
        params.append(kategori)

    uzmanlar = query(sql, params)
    sonuc = []
    for u in uzmanlar:
        koord = SEHIR_KOORDINATLARI.get(u["sehir"])
        if not koord:
            continue
        # Küçük rastgele sapma — aynı şehirdeki uzmanlar üst üste görünmesin
        import random
        random.seed(u["id"])
        sonuc.append({
            "id":     u["id"],
            "ad":     u["ad_soyad"],
            "sehir":  u["sehir"],
            "kat":    u["kategori"],
            "puan":   float(u["puan"] or 0),
            "ucret":  u["saatlik_ucret"],
            "lat":    koord["lat"] + random.uniform(-0.08, 0.08),
            "lng":    koord["lng"] + random.uniform(-0.08, 0.08),
        })

    return jsonify(sonuc)

# ── Şehirler listesi + koordinat ─────────────────────────────────────────────

@konum_bp.route("/sehirler", methods=["GET"])
def sehirler():
    return jsonify([
        {"ad": sehir, **koord}
        for sehir, koord in SEHIR_KOORDINATLARI.items()
    ])

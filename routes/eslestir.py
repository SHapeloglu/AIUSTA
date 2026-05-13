"""
╔══════════════════════════════════════════════════════════════╗
║           İştek Platform — AI Uzman Eşleştirme Motoru       ║
╚══════════════════════════════════════════════════════════════╝

TF-IDF tabanlı metin analizi ve çok faktörlü puanlama ile
ilana en uygun uzmanları otomatik sıralar.

Skor Bileşenleri (toplam 100 puan):
    ┌─────────────────────────┬──────┐
    │ Metin benzerliği (TF-IDF)│  30  │
    │ Kategori eşleşmesi       │  25  │
    │ Uzman puanı (1-5 yıldız) │  20  │
    │ Tecrübe (is_tamamlanan)  │  15  │
    │ Fiyat uyumu              │  10  │
    └─────────────────────────┴──────┘
    + Aynı şehir bonusu: +5 puan

Rotalar:
    GET  /eslestir/<ilan_id>          → En uygun N uzman (varsayılan 5)
    POST /eslestir/anlik              → Metin bazlı anlık eşleştirme
    GET  /eslestir/neden/<u>/<i>      → Eşleştirme skor detayı
"""

from flask import Blueprint, request, jsonify, session
from database import query
from routes.auth import giris_gerekli
import math, re
from datetime import datetime

eslestir_bp = Blueprint("eslestir", __name__, url_prefix="/eslestir")

# ─── Türkçe stop words ────────────────────────────────────────────────────────
STOP_WORDS = {
    "ve","ile","bir","bu","da","de","mi","mu","mü","için","gibi","daha",
    "çok","en","her","hem","ya","veya","ama","fakat","ancak","olan","olan",
    "olarak","kadar","sonra","önce","göre","beri","karşı","arasında","üzere",
    "yani","hatta","bile","sadece","sadece","yalnızca","pek","hiç","artık",
    "zaten","henüz","şimdi","içinde","üzerinde","altında","yanında","etmek",
    "yapmak","olmak","vermek","almak","gitmek","gelmek","bulmak","istemek",
    "ise","ki","ne","ya","ah","oh","ben","sen","biz","siz","onlar","o",
}

# Kategori → anahtar kelimeler
KAT_KELIMELER = {
    "temizlik":  ["temizlik","temizleme","temiz","süpürge","silme","yıkama","deterjan","dezenfektan","hijyen","ev","daire","ofis","derin"],
    "tamirat":   ["tamirat","tamir","montaj","kurulum","bozuk","kırık","arıza","onarım","vida","çivi","raf","mobilya","ikea"],
    "nakliyat":  ["nakliyat","taşıma","taşınma","kutu","mobilya","eşya","kamyon","yük","piyano","koltuk"],
    "bahce":     ["bahçe","bitki","çimen","çiçek","budama","peyzaj","ağaç","yaprak","sulama","toprak"],
    "boya":      ["boya","badana","boyama","duvar","tavan","boya","renk","fırça","rulo","astar"],
    "elektrik":  ["elektrik","elektrikçi","sigorta","priz","aydınlatma","kablo","tesisat","arıza","panel","akım"],
    "tesisaat":  ["tesisat","tesisatçı","boru","su","musluk","klozet","lavabo","kombi","ısıtma","sızdırma","kaçak","tıkanıklık"],
    "guvenlik":  ["güvenlik","kamera","alarm","kilit","çelik kapı","kartlı geçiş","nvr","dvr","ip kamera"],
    "klima":     ["klima","ısıtma","soğutma","split","inverter","montaj","bakım","filtre","gaz","freon"],
    "diger":     [],
}

# ─── Yardımcı: TF-IDF benzeri skor ───────────────────────────────────────────

def tokenize(metin: str) -> list:
    metin = metin.lower()
    metin = re.sub(r"[^\w\sçğıöşüÇĞİÖŞÜ]", " ", metin)
    return [w for w in metin.split() if w not in STOP_WORDS and len(w) > 2]

def kosinüs_benzerlik(a: dict, b: dict) -> float:
    """İki TF sözlüğünün kosinüs benzerliği."""
    ortak = set(a) & set(b)
    if not ortak:
        return 0.0
    pay    = sum(a[k] * b[k] for k in ortak)
    payda  = math.sqrt(sum(v**2 for v in a.values())) * math.sqrt(sum(v**2 for v in b.values()))
    return pay / payda if payda else 0.0

def tf(kelimeler: list) -> dict:
    sayac = {}
    for k in kelimeler:
        sayac[k] = sayac.get(k, 0) + 1
    return sayac

def ilan_metni_olustur(ilan: dict) -> str:
    parcalar = [
        ilan.get("baslik", ""),
        ilan.get("aciklama", ""),
        ilan.get("kategori", ""),
        " ".join(KAT_KELIMELER.get(ilan.get("kategori", ""), [])),
    ]
    return " ".join(filter(None, parcalar))

def uzman_metni_olustur(uzman: dict) -> str:
    parcalar = [
        uzman.get("ad_soyad", ""),
        uzman.get("aciklama", ""),
        uzman.get("kategori", ""),
        " ".join(KAT_KELIMELER.get(uzman.get("kategori", ""), [])),
    ]
    return " ".join(filter(None, parcalar))

# ─── Ana eşleştirme fonksiyonu ────────────────────────────────────────────────

def uzman_skoru_hesapla(ilan: dict, uzman: dict) -> dict:
    """
    Uzman için 0-100 arası bileşik skor döner.
    Bileşenler:
      - metin_benzerlik  (30 puan) — TF-IDF kosinüs
      - kategori_eslesme (25 puan) — birebir kategori eşleşmesi
      - puan             (20 puan) — uzman puanı
      - tecrube          (15 puan) — tamamlanan iş sayısı
      - fiyat_uyum       (10 puan) — bütçeye yakınlık
    """
    skor_detay = {}

    # 1. Metin benzerliği
    ilan_tf  = tf(tokenize(ilan_metni_olustur(ilan)))
    uzman_tf = tf(tokenize(uzman_metni_olustur(uzman)))
    benzerlik = kosinüs_benzerlik(ilan_tf, uzman_tf)
    metin_puan = round(benzerlik * 30, 2)
    skor_detay["metin_benzerlik"] = metin_puan

    # 2. Kategori eşleşmesi
    if uzman.get("kategori") == ilan.get("kategori"):
        kat_puan = 25
    else:
        kat_puan = 0
    skor_detay["kategori_eslesme"] = kat_puan

    # 3. Uzman puanı (max 5.0 → 20 puan)
    puan = float(uzman.get("puan") or 0)
    puan_skoru = round((puan / 5.0) * 20, 2)
    skor_detay["puan"] = puan_skoru

    # 4. Tecrübe (tamamlanan iş sayısı, log ölçekli, max 15)
    is_say = int(uzman.get("is_tamamlanan") or 0)
    tec_puan = round(min(math.log1p(is_say) / math.log1p(300) * 15, 15), 2)
    skor_detay["tecrube"] = tec_puan

    # 5. Fiyat uyumu (bütçeye ne kadar yakın, max 10)
    butce        = int(ilan.get("butce") or 0)
    saatlik_ucret = int(uzman.get("saatlik_ucret") or uzman.get("fiyat") or 0)
    if butce > 0 and saatlik_ucret > 0:
        oran = saatlik_ucret / butce
        if oran <= 1.0:
            fiyat_puan = round(10 * (1 - abs(1 - oran)), 2)
        else:
            fiyat_puan = round(max(0, 10 - (oran - 1) * 20), 2)
    else:
        fiyat_puan = 5  # bilinmiyorsa orta puan
    skor_detay["fiyat_uyum"] = fiyat_puan

    # Toplam
    toplam = sum(skor_detay.values())
    skor_detay["toplam"] = round(toplam, 1)

    # Eşleştirme sebebi (kullanıcıya gösterilecek)
    sebepler = []
    if kat_puan == 25:
        sebepler.append(f"Kategori tam eşleşiyor ({ilan.get('kategori')})")
    if metin_puan >= 15:
        sebepler.append("İlan açıklamasıyla yüksek metin uyumu")
    if puan >= 4.7:
        sebepler.append(f"⭐ {puan} puan — üst düzey uzman")
    if is_say >= 50:
        sebepler.append(f"{is_say} tamamlanan iş — deneyimli")
    if fiyat_puan >= 8:
        sebepler.append("Bütçenize uygun fiyatlandırma")
    if not sebepler:
        sebepler.append("Genel profil uyumu")

    return {**skor_detay, "sebepler": sebepler}

# ─── API: İlana göre eşleştir ─────────────────────────────────────────────────

@eslestir_bp.route("/<ilan_id>", methods=["GET"])
def ilan_eslestir(ilan_id):
    limit = int(request.args.get("limit", 5))

    ilan = query("SELECT * FROM ilanlar WHERE id=%s", (ilan_id,), fetch="one")
    if not ilan:
        return jsonify({"hata": "İlan bulunamadı."}), 404

    uzmanlar = query("""
        SELECT k.id, k.ad_soyad, k.sehir, k.email,
               p.kategori, p.saatlik_ucret, p.puan,
               p.is_tamamlanan, p.aciklama, p.uygunluk
        FROM kullanicilar k
        JOIN uzman_profiller p ON p.kullanici_id = k.id
        WHERE k.aktif=1 AND p.onaylandi=1 AND p.uygunluk=1
    """)

    # Şehir filtresi (varsa önce şehir uyanları daha yükseğe taşı)
    ilan_sehir = ilan.get("sehir", "")

    skorlu = []
    for u in uzmanlar:
        skor = uzman_skoru_hesapla(ilan, u)

        # Aynı şehir bonusu
        if u.get("sehir") == ilan_sehir:
            skor["toplam"] = min(100, skor["toplam"] + 5)
            skor["sebepler"].insert(0, f"📍 Aynı şehirde ({ilan_sehir})")

        skorlu.append({
            "uzman": {
                "id":          u["id"],
                "ad_soyad":    u["ad_soyad"],
                "sehir":       u["sehir"],
                "kategori":    u["kategori"],
                "puan":        float(u["puan"] or 0),
                "is_tamamlanan": u["is_tamamlanan"],
                "saatlik_ucret": u["saatlik_ucret"],
                "aciklama":    u["aciklama"],
                "avatar":      u["ad_soyad"][0],
            },
            "eslestirme_skoru": skor["toplam"],
            "sebepler":         skor["sebepler"],
            "detay":            skor,
        })

    skorlu.sort(key=lambda x: x["eslestirme_skoru"], reverse=True)

    return jsonify({
        "ilan_id":   ilan_id,
        "ilan":      {"baslik": ilan["baslik"], "kategori": ilan["kategori"], "sehir": ilan_sehir},
        "eslestirmeler": skorlu[:limit],
        "toplam_uzman":  len(skorlu),
    })

# ─── API: Anlık metin bazlı eşleştirme ───────────────────────────────────────

@eslestir_bp.route("/anlik", methods=["POST"])
def anlik_eslestir():
    b = request.json or {}
    sahte_ilan = {
        "baslik":   b.get("baslik", ""),
        "aciklama": b.get("aciklama", ""),
        "kategori": b.get("kategori", ""),
        "butce":    b.get("butce", 0),
        "sehir":    b.get("sehir", ""),
    }
    limit = int(b.get("limit", 5))

    uzmanlar = query("""
        SELECT k.id, k.ad_soyad, k.sehir,
               p.kategori, p.saatlik_ucret, p.puan,
               p.is_tamamlanan, p.aciklama, p.uygunluk
        FROM kullanicilar k
        JOIN uzman_profiller p ON p.kullanici_id = k.id
        WHERE k.aktif=1 AND p.onaylandi=1 AND p.uygunluk=1
    """)

    skorlu = []
    for u in uzmanlar:
        skor = uzman_skoru_hesapla(sahte_ilan, u)
        if u.get("sehir") == sahte_ilan.get("sehir"):
            skor["toplam"] = min(100, skor["toplam"] + 5)
        skorlu.append({
            "id":              u["id"],
            "ad_soyad":        u["ad_soyad"],
            "sehir":           u["sehir"],
            "kategori":        u["kategori"],
            "puan":            float(u["puan"] or 0),
            "saatlik_ucret":   u["saatlik_ucret"],
            "eslestirme_skoru": skor["toplam"],
            "sebepler":        skor["sebepler"],
            "avatar":          u["ad_soyad"][0],
        })

    skorlu.sort(key=lambda x: x["eslestirme_skoru"], reverse=True)
    return jsonify(skorlu[:limit])

# ─── API: Eşleştirme açıklaması ───────────────────────────────────────────────

@eslestir_bp.route("/neden/<uzman_id>/<ilan_id>", methods=["GET"])
def eslestirme_neden(uzman_id, ilan_id):
    ilan  = query("SELECT * FROM ilanlar WHERE id=%s", (ilan_id,), fetch="one")
    uzman = query("""
        SELECT k.*, p.kategori, p.saatlik_ucret, p.puan, p.is_tamamlanan, p.aciklama
        FROM kullanicilar k
        JOIN uzman_profiller p ON p.kullanici_id=k.id
        WHERE k.id=%s
    """, (uzman_id,), fetch="one")

    if not ilan or not uzman:
        return jsonify({"hata": "İlan veya uzman bulunamadı."}), 404

    skor = uzman_skoru_hesapla(ilan, uzman)
    return jsonify({
        "uzman_ad":   uzman["ad_soyad"],
        "ilan_baslik": ilan["baslik"],
        "toplam_skor": skor["toplam"],
        "sebepler":    skor["sebepler"],
        "detay": {
            "Metin uyumu":       f"{skor['metin_benzerlik']:.1f} / 30",
            "Kategori eşleşmesi": f"{skor['kategori_eslesme']:.0f} / 25",
            "Uzman puanı":       f"{skor['puan']:.1f} / 20",
            "Tecrübe":           f"{skor['tecrube']:.1f} / 15",
            "Fiyat uyumu":       f"{skor['fiyat_uyum']:.1f} / 10",
        }
    })

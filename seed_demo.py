"""
İştek Platform — Gerçekçi Demo Veri Üretici
Çalıştır: python seed_demo.py
Temizle:  python seed_demo.py --temizle
"""
import sys, uuid, random, bcrypt
from datetime import datetime, timedelta, date
from database import get_db, query, init_db
from routes.takvim import init_takvim
from routes.upload import init_upload_db
from routes.iade import init_iade_db
from routes.takip import init_takip_db
from routes.oauth_kimlik import init_kimlik_db
from routes.video import init_video_db

# ─── Yardımcılar ──────────────────────────────────────────────────────────────

def uid(): return str(uuid.uuid4())
def hp(s): return bcrypt.hashpw(s.encode(), bcrypt.gensalt()).decode()
def rastgele_tarih(gun_geri=365, gun_ileri=0):
    baz = datetime.now() - timedelta(days=gun_geri)
    return baz + timedelta(days=random.randint(0, gun_geri + gun_ileri))
def rastgele_saat():
    return f"{random.randint(8,18):02d}:{random.choice(['00','30'])}"

# ─── SABİT VERİ HAVUZLARI ─────────────────────────────────────────────────────

ERKEK_ADLAR = [
    "Ahmet","Mehmet","Ali","Mustafa","Hüseyin","İbrahim","Hasan","Ömer",
    "Yusuf","Murat","Emre","Burak","Serkan","Tolga","Onur","Kerem",
    "Berk","Arda","Can","Kaan","Furkan","Oğuzhan","Enes","Berkay",
]
KADIN_ADLAR = [
    "Ayşe","Fatma","Zeynep","Elif","Merve","Selin","Büşra","Derya",
    "Esra","Gül","Hülya","İrem","Kübra","Leyla","Melis","Neslihan",
    "Özge","Pınar","Rabia","Sevgi","Tuğba","Ümit","Vildan","Yasemin",
]
SOYADLAR = [
    "Yılmaz","Kaya","Demir","Şahin","Çelik","Öztürk","Arslan","Doğan",
    "Kılıç","Aslan","Çetin","Koç","Kurt","Özdemir","Aydın","Güneş",
    "Bulut","Yıldız","Polat","Ateş","Bozkurt","Karaca","Güler","Toprak",
    "Acar","Erdoğan","Çakır","Keskin","Kaplan","Yücel","Güven","Sarı",
]
SEHIRLER = [
    "İstanbul","İstanbul","İstanbul","Ankara","Ankara","İzmir","İzmir",
    "Bursa","Antalya","Adana","Konya","Gaziantep","Mersin","Kayseri",
    "Eskişehir","Trabzon","Samsun","Denizli","Balıkesir",
]
KATEGORILER = [
    "temizlik","temizlik","temizlik",
    "tamirat","tamirat",
    "elektrik","elektrik",
    "tesisaat",
    "boya",
    "nakliyat","nakliyat",
    "bahce",
    "klima",
    "guvenlik",
    "diger",
]
KAT_ACIKLAMA = {
    "temizlik": [
        "Ev, ofis ve işyeri temizliğinde 8 yıllık deneyimim var. Profesyonel ekipman ve ürünlerle hijyenik ortam sağlıyorum. Cam silme, halı yıkama ve derin temizlik yapıyorum.",
        "Sertifikalı temizlik uzmanıyım. Ekolojik ve allerji dostu ürünlerle temizlik yapıyorum. Bebek odası ve hassas yüzey temizliğinde uzmanım.",
        "10 yıldır kurumsal ve bireysel müşterilere temizlik hizmeti veriyorum. İnşaat sonrası temizlik ve taşınma temizliğinde deneyimliyim.",
        "Günlük, haftalık veya aylık periyodik temizlik hizmeti sunuyorum. Mutfak ve banyo dezenfeksiyonunda uzmanım. Müşteri memnuniyeti önceliğimdir.",
        "Profesyonel temizlik ekibimle birlikte çalışıyorum. Büyük daireler ve villalar için ekip temizliği yapıyorum.",
    ],
    "tamirat": [
        "15 yıllık tamirat ustasıyım. IKEA ve her marka mobilya montajı, raf ve dolap kurulumu yapıyorum. Küçük onarımlar için de arayabilirsiniz.",
        "Genel tadilat ve tamirat işleri yapıyorum. Kapı-pencere onarımı, alçıpan, sıhhi tesisat bağlantıları konularında deneyimliyim.",
        "Ev tamircilik hizmetleri: kırık kiremit, akan musluk, sıkışan kapı, dökülen sıva. Küçük veya büyük tüm tamiratlar için beni arayın.",
    ],
    "elektrik": [
        "Lisanslı elektrik ustasıyım. Komple elektrik tesisatı, pano kurulumu, aydınlatma değişimi ve arıza tespiti yapıyorum. Acil servis mevcuttur.",
        "20 yıllık elektrikçiyim. Konut ve ticari projelerde çalışıyorum. Sigorta patlaması, topraklama, akıllı ev sistemleri kurulumu yapıyorum.",
        "İnşaat elektriği ve tadilat elektriği yapıyorum. LED aydınlatma dönüşümü, fotoselli sistemler ve kombi elektriği konularında uzmanım.",
    ],
    "tesisaat": [
        "Sertifikalı tesisatçıyım. Kombi montajı ve bakımı, su tesisatı, kalorifer tesisatı ve banyo-mutfak yenileme işleri yapıyorum.",
        "Tıkanıklık açma, sızıntı tespiti ve onarımı, musluk ve batarya değişimi konularında uzmanım. Aynı gün hizmet veriyorum.",
        "Kombi servis uzmanıyım. Tüm marka kombiler için periyodik bakım, parça değişimi ve arıza tespiti yapıyorum.",
    ],
    "boya": [
        "İç ve dış cephe boyası, dekoratif boya teknikleri, alçıpan uygulaması konularında 12 yıllık deneyimim var.",
        "Badana ve boya ustasıyım. Duvar kağıdı uygulama, fayans derz dolgusu ve alçı sıva işleri de yapıyorum.",
        "Dekoratif boyama ve özel efekt boya uygulamalarında uzmanım. İtalyan sıvası, beton görünümlü boya ve çocuk odası temalı boyamalar yapıyorum.",
    ],
    "nakliyat": [
        "Sigortalı nakliyat hizmeti veriyorum. Asansörlü taşımacılık, ambalajlama ve montaj dahil tam hizmet sunuyorum.",
        "Kurumsal ve bireysel taşıma hizmetleri. Piyano, kasa ve kıymetli eşya taşımada uzmanım. İstanbul içi ve şehirlerarası taşıma yapıyorum.",
        "Mini nakliyat ve parça eşya taşıma hizmeti. Tek koltuk, çamaşır makinesi veya birkaç kutu için bile hizmet veriyorum.",
    ],
    "bahce": [
        "Peyzaj mimarı ve bahçe bakım uzmanıyım. Çim biçimi, budama, dikim ve otomatik sulama sistemi kurulumu yapıyorum.",
        "Balkon ve teras bahçeciliği, iç mekân bitki bakımı ve peyzaj tasarımı konularında hizmet veriyorum.",
        "Bahçe düzenleme ve bakım hizmetleri. Çim ekimi, ağaç kesimi, çit budama ve mevsimlik çiçek dikimi yapıyorum.",
    ],
    "klima": [
        "Tüm marka klimaların montajı, bakımı ve onarımını yapıyorum. Gaz dolumu ve filtre temizliği konularında uzmanım.",
        "Klima montaj ve servis ustasıyım. Split, kaset ve VRF sistemleri kuruyorum. Yılda bir bakım paketim mevcuttur.",
    ],
    "guvenlik": [
        "IP kamera sistemi kurulumu, alarm sistemleri ve akıllı kilit montajı yapıyorum. 7/24 teknik destek sağlıyorum.",
        "Güvenlik kamerası ve alarm sistemi uzmanıyım. Konut, işyeri ve site güvenlik sistemleri kuruyorum.",
    ],
    "diger": [
        "Genel ev işleri, mobilya montajı, alışveriş yardımı ve küçük taşıma işleri için beni arayabilirsiniz.",
        "Handyman hizmetleri: küçük onarımlar, montaj işleri, boya badana ve genel tadilat.",
    ],
}
ILAN_SABLONLARI = {
    "temizlik": [
        ("3+1 daire genel temizliği", "Bursa'da 3+1 150m² dairemizin genel temizliği yapılacak. Mutfak, banyo ve yatak odaları dahil. Hafta sonu müsaitiz.", 400, 600),
        ("Ofis temizliği haftada 2 gün", "15 kişilik küçük ofisimizin haftada 2 gün temizliği gerekiyor. Sabah erken saatlerde yapılabilir.", 800, 1200),
        ("Taşınma sonrası ev temizliği", "Yeni eve taşındık, önceki kiracıdan kalan derin temizlik gerekiyor. 2+1 daire, yaklaşık 85m².", 350, 500),
        ("Haftalık ev temizliği (düzenli)", "İstanbul Kadıköy'de 2+1 dairem için düzenli haftalık temizlik arıyorum. Uzun vadeli çalışmak istiyorum.", 300, 450),
        ("Cam ve balkon temizliği", "4 katlı müstakil evin tüm dış camları ve balkonları temizlenecek. Güvenlik ekipmanı gerekebilir.", 500, 800),
        ("İnşaat sonrası temizlik", "Yeni biten dairenin inşaat tozu ve kiri temizlenecek. 3+1, 130m². Fayans ve pencerelerde kireç var.", 700, 1000),
    ],
    "tamirat": [
        ("IKEA dolap montajı (3 adet)", "3 adet PAX dolap ve 1 adet KALLAX raf sisteminin montajını yaptırmak istiyorum. Malzeme elimde mevcut.", 300, 500),
        ("Kapı kilidi değişimi ve ayarı", "2 oda kapısının kilidi çalışmıyor, 1 kapı da kapanmıyor. Aynı günde halledebilecek biri arıyorum.", 150, 250),
        ("Banyo tadilatı küçük onarımlar", "Küvet sifonunun değişimi, ayna montajı ve duvar askılarının takılması gerekiyor.", 200, 350),
        ("Çatı onarımı — kiremit değişimi", "Geçen yağmurda birkaç kiremit kırıldı. Yaklaşık 10-15 kiremit değişimi ve derz dolgusu gerekiyor.", 400, 700),
        ("Parke zemin onarımı", "Salonun parke zemininde birkaç tahta şişti ve kalktı. Yerinde onarım ve cilalama istiyorum.", 500, 800),
    ],
    "elektrik": [
        ("Komple daire elektrik tesisatı", "100m² yeni daire için sıfır elektrik tesisatı çekilecek. Pano, prizler, aydınlatma dahil.", 2000, 4000),
        ("Sigorta panosu yenileme", "Eski sigorta panosu değiştirilecek ve topraklama eklenecek. Daire 3+1.", 600, 1000),
        ("Avize ve spot montajı", "Salon için avize ve 3 oda için spot aydınlatma montajı. Malzeme müşteride mevcut.", 300, 500),
        ("Akıllı ev sistemi kurulumu", "Işık, perde ve klima kontrolü için akıllı ev sistemi kurulmak isteniyor. 4+1 villa.", 3000, 6000),
        ("Acil arıza — elektrik kesintisi", "Dairemizin bir bölümünde elektrik gitti. Sigorta atmaya devam ediyor. Acil yardım lazım.", 200, 400),
    ],
    "tesisaat": [
        ("Kombi montajı ve devreye alma", "Yeni aldığım Vaillant kombiyi takmak istiyorum. Eski kombi sökümü de dahil olsun.", 500, 800),
        ("Mutfak tezgahı sifon değişimi", "Mutfak lavabosunun altından su sızıyor, sifon ve bağlantı hortumları değiştirilecek.", 150, 250),
        ("Banyo komple tadilat tesisatı", "Banyoyu yeniliyoruz. Klozet, lavabo ve duşakabin değişimi için tesisat gerekiyor.", 800, 1500),
        ("Tıkanıklık açma — mutfak", "Mutfak lavabo tıkandı, tel veya makineyle açılması gerekiyor. Aynı gün hizmet lazım.", 100, 200),
        ("Radyatör sökme ve takma", "Odaları boyayacağız, 5 adet radyatörün sökülüp boyadıktan sonra takılması gerekiyor.", 400, 600),
    ],
    "boya": [
        ("3+1 daire komple boyası", "120m² 3+1 dairenin tüm odaları boyanacak. Beyaz + 1 aksan renk. Malzeme müşteride.", 2000, 3500),
        ("Balkon ve dış cephe boyası", "Apartmanın balkonu ve dış cephesi boyama ihtiyacı var. 6 katlı bina, yaklaşık 200m².", 3000, 5000),
        ("Çocuk odası temalı boyama", "Kızımın odasına unicorn temalı duvar resmi ve pembe tonlarında boyama istiyorum.", 800, 1500),
        ("Salon accent wall (vurgu duvarı)", "Salonda tek bir duvar farklı renk ve desenle boyanacak. Yaklaşık 12m².", 300, 500),
        ("İtalyan sıvası uygulama", "Yatak odası ve koridor için İtalyan sıvası istiyorum. Yaklaşık 40m².", 1200, 2000),
    ],
    "nakliyat": [
        ("3+1 daire taşınması", "Kadıköy'den Üsküdar'a taşınıyoruz. 3+1 daire, asansör var. Paketleme yardımı da istiyoruz.", 1500, 2500),
        ("Piyano taşıma (baby grand)", "Baby grand piyanomuzu 3. kattan aşağıya indirip başka semte taşımak istiyoruz.", 800, 1500),
        ("Ofis taşıma (küçük ofis)", "10 kişilik ofisimizi aynı ilçede başka bir binaya taşıyacağız. Hafta sonu tercihimiz.", 2000, 3500),
        ("Tek eşya taşıma — kanepe", "3'lü koltuk takımını depoya taşıtmak istiyorum. Tek kat, asansör mevcut.", 300, 500),
        ("Şehirlerarası taşınma", "Ankara'dan İzmir'e taşınıyoruz. 2+1 daire içeriği, sigortalı taşıma istiyoruz.", 3000, 5000),
    ],
    "bahce": [
        ("Bahçe düzenleme ve peyzaj", "Villa bahçemiz 200m². Çim ekimi, çit budama ve çiçek dikimi istiyoruz.", 1500, 3000),
        ("Haftalık bahçe bakımı", "Yazlığımız için haftalık bahçe bakım hizmeti arıyorum. Mayıs-Ekim arası.", 400, 600),
        ("Ağaç kesimi ve budama", "Bahçede 3 büyük ağaç budanacak, 1 tanesi tamamen kesilecek. Güvenlik önlemleri lazım.", 600, 1200),
        ("Balkon bahçesi düzenleme", "Küçük balkonumuzu yeşil bir alana dönüştürmek istiyoruz. Saksı, toprak ve bitkiler dahil.", 500, 900),
    ],
    "klima": [
        ("2 adet split klima montajı", "Yatak odası ve salon için 12.000 BTU split klima montajı. Malzeme müşteride.", 600, 900),
        ("Klima bakım ve gaz dolumu", "3 adet klima yaz öncesi bakıma çekilecek, gerekirse gaz dolumu yapılacak.", 400, 700),
        ("VRF sistem kurulumu (ofis)", "2 katlı ofisimiz için VRF klima sistemi kurulacak. Teklif bekliyoruz.", 8000, 15000),
    ],
    "guvenlik": [
        ("IP kamera sistemi kurulumu", "Villa için dışarıya 6 adet IP kamera ve iç mekana 2 adet kamera kurulacak.", 2000, 4000),
        ("Alarm sistemi kurulumu", "Dükkanımız için hırsız alarmı, hareket sensörü ve SMS uyarı sistemi kurulacak.", 1500, 2500),
    ],
    "diger": [
        ("Mobilya montajı ve yerleştirme", "Yeni eve taşındık, çeşitli mobilyaların montajı ve yerleştirilmesi gerekiyor.", 400, 700),
        ("Genel ev bakımı paketi", "Aylık genel ev bakım hizmeti: küçük onarımlar, ampul değişimi, vs.", 300, 500),
    ],
}
YORUM_SABLONLARI = [
    ("Çok memnun kaldım, kesinlikle tavsiye ederim!", 5),
    ("İşini çok iyi yapıyor, dakik ve güvenilir biri.", 5),
    ("Harika hizmet, beklentilerimin üzerinde bir iş çıkardı.", 5),
    ("Fiyat performans açısından mükemmel, tekrar çalışacağım.", 5),
    ("Çok titiz ve özenli çalışıyor, teşekkürler.", 5),
    ("Gayet iyi bir hizmet aldık, memnunuz.", 4),
    ("İşini biliyor ama biraz geç geldi, sonuç iyi.", 4),
    ("Kaliteli iş çıkardı, fiyatı biraz yüksekti ama değdi.", 4),
    ("Genel olarak memnunum, küçük detayları kaçırdı.", 4),
    ("İyi hizmet, bir sonraki işte de çalışabiliriz.", 4),
    ("Ortalama bir deneyimdi, daha iyisi bulunabilir.", 3),
    ("İş tamam ama iletişimi biraz zayıftı.", 3),
]

# ─── VERİ OLUŞTURMA FONKSİYONLARI ────────────────────────────────────────────

def rastgele_isim():
    cinsiyet = random.choice(["e","k"])
    ad  = random.choice(ERKEK_ADLAR if cinsiyet=="e" else KADIN_ADLAR)
    soy = random.choice(SOYADLAR)
    return f"{ad} {soy}"

def rastgele_email(isim):
    ad_soyad = isim.lower()
    for tr,en in [("ı","i"),("ğ","g"),("ü","u"),("ş","s"),("ö","o"),("ç","c"),(" ",".")]:
        ad_soyad = ad_soyad.replace(tr, en)
    domain = random.choice(["gmail.com","hotmail.com","yahoo.com","outlook.com","yandex.com"])
    return f"{ad_soyad}{random.randint(1,99)}@{domain}"

def rastgele_telefon():
    return f"05{random.choice(['30','31','32','33','36','37','38','39','50','51','52','53','54','55','56','57','58','59'])}{random.randint(1000000,9999999)}"

def uzman_olustur(uid_val, isim, email, sehir, kategori, kayit_tarihi):
    query(
        "INSERT INTO kullanicilar (id,ad_soyad,email,sifre_hash,rol,telefon,sehir,aktif,email_dogrulandi,kayit_tarihi) "
        "VALUES (%s,%s,%s,%s,'uzman',%s,%s,1,1,%s)",
        (uid_val, isim, email, hp("demo123"),
         rastgele_telefon(), sehir,
         kayit_tarihi.strftime("%Y-%m-%d %H:%M:%S")),
        fetch="none"
    )
    puan       = round(random.uniform(3.8, 5.0), 1)
    is_say     = random.randint(5, 350)
    ucret      = random.choice([100,120,150,160,180,200,220,250,280,300,350,400])
    aciklama   = random.choice(KAT_ACIKLAMA.get(kategori, KAT_ACIKLAMA["diger"]))
    onaylandi  = 1 if random.random() > 0.1 else 0

    query(
        "INSERT INTO uzman_profiller (id,kullanici_id,kategori,saatlik_ucret,puan,"
        "is_tamamlanan,aciklama,onaylandi,uygunluk,katilim_tarihi) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (uid(), uid_val, kategori, ucret, puan, is_say, aciklama,
         onaylandi, 1, kayit_tarihi.strftime("%Y-%m-%d")),
        fetch="none"
    )
    return puan, is_say, ucret

def musteri_olustur(uid_val, isim, email, sehir, kayit_tarihi):
    query(
        "INSERT INTO kullanicilar (id,ad_soyad,email,sifre_hash,rol,telefon,sehir,aktif,email_dogrulandi,kayit_tarihi) "
        "VALUES (%s,%s,%s,%s,'musteri',%s,%s,1,1,%s)",
        (uid_val, isim, email, hp("demo123"),
         rastgele_telefon(), sehir,
         kayit_tarihi.strftime("%Y-%m-%d %H:%M:%S")),
        fetch="none"
    )

def ilan_olustur(musteri_id, musteri_ad, kategori, sehir, olusturma):
    sablonlar = ILAN_SABLONLARI.get(kategori, ILAN_SABLONLARI["diger"])
    sablon    = random.choice(sablonlar)
    baslik, aciklama, min_b, max_b = sablon
    butce  = random.randint(min_b, max_b)
    durum  = random.choices(
        ["aktif","tamamlandi","tamamlandi","tamamlandi","iptal"],
        weights=[2,5,5,5,1]
    )[0]
    ilan_id = uid()
    query(
        "INSERT INTO ilanlar (id,baslik,kategori,sehir,butce,aciklama,musteri_id,musteri_ad,durum,olusturma_tarihi) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (ilan_id, baslik, kategori, sehir, butce, aciklama,
         musteri_id, musteri_ad, durum,
         olusturma.strftime("%Y-%m-%d %H:%M:%S")),
        fetch="none"
    )
    return ilan_id, durum, butce

def teklif_olustur(ilan_id, uzman_id, butce, ilan_durum, teklif_tarihi):
    fiyat   = int(butce * random.uniform(0.8, 1.2))
    mesajlar = [
        f"Merhaba, ilanınızı inceledim. ₺{fiyat} karşılığında bu işi yapabilirim. En kısa sürede başlayabilirim.",
        f"İyi günler, deneyimli biri olarak bu işi ₺{fiyat}'a gerçekleştirebilirim. Referanslarımı paylaşabilirim.",
        f"Merhaba, belirttiğiniz iş için ₺{fiyat} teklif veriyorum. Aynı gün başlayabilirim.",
        f"Hizmetiniz için ₺{fiyat} uygun buluyorum. İş bitiminde memnun kalmazsanız ücretsiz düzeltme yapıyorum.",
    ]
    durum = "kabul" if ilan_durum == "tamamlandi" else random.choice(["beklemede","beklemede","kabul","red"])
    teklif_id = uid()
    query(
        "INSERT INTO teklifler (id,ilan_id,uzman_id,fiyat,mesaj,durum,tarih) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (teklif_id, ilan_id, uzman_id, fiyat,
         random.choice(mesajlar), durum,
         teklif_tarihi.strftime("%Y-%m-%d %H:%M:%S")),
        fetch="none"
    )
    return teklif_id, fiyat, durum

def odeme_olustur(ilan_id, musteri_id, uzman_id, tutar, odeme_tarihi):
    komisyon  = round(tutar * 0.12, 2)
    odeme_id  = uid()
    query(
        "INSERT INTO odemeler (id,ilan_id,musteri_id,uzman_id,tutar,komisyon,durum,iyzico_odeme_id,tarih) "
        "VALUES (%s,%s,%s,%s,%s,%s,'onaylandi',%s,%s)",
        (odeme_id, ilan_id, musteri_id, uzman_id,
         tutar, komisyon,
         f"pay_{uid().replace('-','')[:16]}",
         odeme_tarihi.strftime("%Y-%m-%d %H:%M:%S")),
        fetch="none"
    )
    return odeme_id

def degerlendirme_olustur(ilan_id, uzman_id, musteri_id, degerlendirme_tarihi):
    sablon = random.choice(YORUM_SABLONLARI)
    yorum, puan = sablon
    query(
        "INSERT INTO degerlendirmeler (id,ilan_id,uzman_id,musteri_id,puan,yorum,tarih) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (uid(), ilan_id, uzman_id, musteri_id, puan, yorum,
         degerlendirme_tarihi.strftime("%Y-%m-%d %H:%M:%S")),
        fetch="none"
    )

def mesaj_olustur(gonderen_id, alici_id, ilan_id, tarih):
    mesajlar = [
        "Merhaba, ilanınızla ilgili birkaç sorum vardı.",
        "Randevu için ne zaman müsaitsiniz?",
        "Peki, o gün saat 10'da uygun mu?",
        "Tabii ki, o saatte orada olacağım.",
        "İşin ne kadar süreceğini tahmin edebilir misiniz?",
        "Yaklaşık 3-4 saat sürer, malzemelere bağlı.",
        "Teşekkürler, bekliyoruz.",
        "İş tamamlandı, memnun kaldınız mı?",
        "Evet, çok güzel oldu teşekkürler!",
        "Rica ederim, iyi günler.",
    ]
    for i in range(random.randint(2, 6)):
        gonderen = gonderen_id if i % 2 == 0 else alici_id
        alici    = alici_id    if i % 2 == 0 else gonderen_id
        t        = tarih + timedelta(minutes=random.randint(5, 120) * i)
        query(
            "INSERT INTO mesajlar (id,gonderen_id,alici_id,ilan_id,metin,okundu,tarih) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (uid(), gonderen, alici, ilan_id,
             random.choice(mesajlar), 1,
             t.strftime("%Y-%m-%d %H:%M:%S")),
            fetch="none"
        )

def is_takip_olustur(ilan_id, uzman_id, olusturma):
    from routes.takip import adim_olustur, IS_ADIMLARI
    tamamlanan = random.randint(3, len(IS_ADIMLARI))
    for i, adim in enumerate(IS_ADIMLARI[:tamamlanan]):
        t = olusturma + timedelta(hours=i*2 + random.randint(0,4))
        query(
            "INSERT INTO is_takip (id,ilan_id,adim_kodu,adim_adi,tamamlandi,tarih,aciklama,ekleyen_id) "
            "VALUES (%s,%s,%s,%s,1,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE tamamlandi=1",
            (uid(), ilan_id, adim["kod"], adim["ad"],
             t.strftime("%Y-%m-%d %H:%M:%S"),
             f"{adim['ad']} tamamlandı.", uzman_id),
            fetch="none"
        )

def randevu_olustur(ilan_id, uzman_id, musteri_id, tarih):
    saat = rastgele_saat()
    bitis_saat = f"{int(saat[:2]) + random.randint(2,5):02d}:{saat[3:]}"
    if int(bitis_saat[:2]) > 22:
        bitis_saat = "20:00"
    query(
        "INSERT INTO randevular (id,ilan_id,uzman_id,musteri_id,tarih,baslangic,bitis,durum) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,'onaylandi')",
        (uid(), ilan_id, uzman_id, musteri_id,
         tarih.strftime("%Y-%m-%d"), saat, bitis_saat),
        fetch="none"
    )

def bildirim_olustur_demo(kullanici_id, tip, baslik, metin, tarih):
    query(
        "INSERT INTO bildirimler (id,kullanici_id,tip,baslik,metin,okundu,tarih) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (uid(), kullanici_id, tip, baslik, metin,
         random.choice([0,0,0,1,1]),
         tarih.strftime("%Y-%m-%d %H:%M:%S")),
        fetch="none"
    )

# ─── ANA SEED FONKSİYONU ─────────────────────────────────────────────────────

def seed():
    print("\n🌱 Gerçekçi demo veriler oluşturuluyor...\n")

    # Admin
    admin_id = uid()
    query(
        "INSERT INTO kullanicilar (id,ad_soyad,email,sifre_hash,rol,telefon,sehir,aktif,email_dogrulandi) "
        "VALUES (%s,%s,%s,%s,'admin',%s,%s,1,1)",
        (admin_id,"Platform Admin","admin@istek.com",hp("admin123"),"05001234567","İstanbul"),
        fetch="none"
    )
    print("✅ Admin hesabı oluşturuldu")

    # ── 40 Uzman ──────────────────────────────────────────────────────────────
    uzman_listesi = []
    kullanilan_emailler = set()
    print("👷 40 uzman oluşturuluyor...")
    for i in range(40):
        isim  = rastgele_isim()
        email = rastgele_email(isim)
        while email in kullanilan_emailler:
            email = rastgele_email(isim)
        kullanilan_emailler.add(email)

        sehir    = random.choice(SEHIRLER)
        kategori = random.choice(KATEGORILER)
        kayit    = rastgele_tarih(730, 0)
        u_id     = uid()

        puan, is_say, ucret = uzman_olustur(u_id, isim, email, sehir, kategori, kayit)
        uzman_listesi.append({
            "id": u_id, "isim": isim, "email": email,
            "sehir": sehir, "kategori": kategori,
            "puan": puan, "is_say": is_say, "ucret": ucret,
        })

    print(f"   ✅ {len(uzman_listesi)} uzman oluşturuldu")

    # ── 60 Müşteri ────────────────────────────────────────────────────────────
    musteri_listesi = []
    print("🛍️  60 müşteri oluşturuluyor...")
    for i in range(60):
        isim  = rastgele_isim()
        email = rastgele_email(isim)
        while email in kullanilan_emailler:
            email = rastgele_email(isim)
        kullanilan_emailler.add(email)

        sehir = random.choice(SEHIRLER)
        kayit = rastgele_tarih(365, 0)
        m_id  = uid()

        musteri_olustur(m_id, isim, email, sehir, kayit)
        musteri_listesi.append({
            "id": m_id, "isim": isim,
            "email": email, "sehir": sehir,
        })

    # Test müşterisi
    test_musteri_id = uid()
    musteri_olustur(test_musteri_id, "Test Müşteri", "musteri@demo.com", "İstanbul",
                    datetime.now() - timedelta(days=30))
    musteri_listesi.append({"id": test_musteri_id, "isim": "Test Müşteri",
                             "email": "musteri@demo.com", "sehir": "İstanbul"})

    # Test uzmanı
    test_uzman_id = uid()
    uzman_olustur(test_uzman_id, "Test Uzman", "uzman@demo.com", "İstanbul",
                  "temizlik", datetime.now() - timedelta(days=60))
    uzman_listesi.append({"id": test_uzman_id, "isim": "Test Uzman",
                           "email": "uzman@demo.com", "sehir": "İstanbul",
                           "kategori": "temizlik", "puan": 4.7, "is_say": 45, "ucret": 180})

    print(f"   ✅ {len(musteri_listesi)} müşteri oluşturuldu")

    # ── 120 İlan + tam iş akışı ───────────────────────────────────────────────
    print("📋 120 ilan ve tam iş akışı oluşturuluyor...")
    ilan_sayisi  = 0
    odeme_sayisi = 0
    mesaj_sayisi = 0

    for musteri in musteri_listesi:
        ilan_adedi = random.randint(1, 4)
        for _ in range(ilan_adedi):
            if ilan_sayisi >= 120:
                break

            kategori  = random.choice(KATEGORILER)
            sehir     = musteri["sehir"]
            olusturma = rastgele_tarih(300, 0)

            ilan_id, durum, butce = ilan_olustur(
                musteri["id"], musteri["isim"],
                kategori, sehir, olusturma
            )
            ilan_sayisi += 1

            # Kategoriye uygun uzmanlar
            uygun_uzmanlar = [u for u in uzman_listesi
                              if u.get("kategori") == kategori or random.random() < 0.15]
            if not uygun_uzmanlar:
                uygun_uzmanlar = uzman_listesi

            # 1-4 teklif
            teklif_sayisi = random.randint(1, 4)
            secilen_uzman = None
            secilen_fiyat = butce

            for j, uzman in enumerate(random.sample(uygun_uzmanlar,
                                                      min(teklif_sayisi, len(uygun_uzmanlar)))):
                teklif_tarihi = olusturma + timedelta(hours=random.randint(1, 48))
                teklif_id, fiyat, teklif_durum = teklif_olustur(
                    ilan_id, uzman["id"], butce, durum, teklif_tarihi
                )
                if teklif_durum == "kabul" and secilen_uzman is None:
                    secilen_uzman = uzman
                    secilen_fiyat = fiyat

            # Tamamlanan ilanlar için tam akış
            if durum == "tamamlandi" and secilen_uzman:
                odeme_tarihi = olusturma + timedelta(days=random.randint(1, 5))

                # Ödeme
                odeme_olustur(ilan_id, musteri["id"], secilen_uzman["id"],
                               secilen_fiyat, odeme_tarihi)
                odeme_sayisi += 1

                # Randevu
                randevu_tarihi = odeme_tarihi + timedelta(days=random.randint(1, 7))
                randevu_olustur(ilan_id, secilen_uzman["id"],
                                 musteri["id"], randevu_tarihi)

                # İş takip adımları
                is_takip_olustur(ilan_id, secilen_uzman["id"], olusturma)

                # Değerlendirme (%80 ihtimalle)
                if random.random() < 0.80:
                    deg_tarihi = randevu_tarihi + timedelta(days=random.randint(1, 3))
                    degerlendirme_olustur(ilan_id, secilen_uzman["id"],
                                           musteri["id"], deg_tarihi)

                # Mesajlar
                mesaj_tarihi = olusturma + timedelta(hours=random.randint(2, 12))
                mesaj_olustur(musteri["id"], secilen_uzman["id"],
                               ilan_id, mesaj_tarihi)
                mesaj_sayisi += 1

                # Bildirimler
                bildirim_olustur_demo(musteri["id"], "odeme",
                    "Ödemeniz alındı",
                    f"₺{secilen_fiyat} tutarındaki ödemeniz onaylandı.",
                    odeme_tarihi)
                bildirim_olustur_demo(secilen_uzman["id"], "teklif",
                    "Teklifiniz kabul edildi!",
                    f"Yeni bir iş aldınız: ₺{secilen_fiyat}",
                    odeme_tarihi)

            elif durum == "aktif":
                # Aktif ilanlar için bazı bildirimler
                if random.random() < 0.5:
                    bildirim_olustur_demo(musteri["id"], "teklif",
                        "Yeni teklif geldi",
                        f"İlanınıza yeni bir teklif geldi.",
                        olusturma + timedelta(hours=random.randint(2, 24)))

        if ilan_sayisi >= 120:
            break

    print(f"   ✅ {ilan_sayisi} ilan oluşturuldu")
    print(f"   ✅ {odeme_sayisi} ödeme oluşturuldu")
    print(f"   ✅ {mesaj_sayisi} konuşma oluşturuldu")

    # ── Uzman puanlarını güncelle ─────────────────────────────────────────────
    print("⭐ Uzman puanları güncelleniyor...")
    for uzman in uzman_listesi:
        ort = query(
            "SELECT AVG(puan) AS p, COUNT(*) AS n FROM degerlendirmeler WHERE uzman_id=%s",
            (uzman["id"],), fetch="one"
        )
        if ort and ort["p"]:
            query(
                "UPDATE uzman_profiller SET puan=%s, is_tamamlanan=%s WHERE kullanici_id=%s",
                (round(float(ort["p"]), 1), ort["n"] + uzman.get("is_say", 0), uzman["id"]),
                fetch="none"
            )

    # ── Özet ──────────────────────────────────────────────────────────────────
    print("\n" + "─"*50)
    print("✅ Demo veriler başarıyla oluşturuldu!\n")
    print("📊 Özet:")
    print(f"   👤 Admin:      1 hesap")
    print(f"   👷 Uzman:      {len(uzman_listesi)} hesap")
    print(f"   🛍️  Müşteri:   {len(musteri_listesi)} hesap")
    print(f"   📋 İlan:       {ilan_sayisi}")
    print(f"   💳 Ödeme:      {odeme_sayisi}")
    print(f"   💬 Konuşma:    {mesaj_sayisi}")
    print("\n🔑 Test hesapları:")
    print("   Admin:   admin@istek.com   / admin123")
    print("   Uzman:   uzman@demo.com    / demo123")
    print("   Müşteri: musteri@demo.com  / demo123")
    print("─"*50 + "\n")

def temizle():
    print("🗑️  Tüm veriler siliniyor...")
    tablolar = [
        "bildirimler","mesajlar","degerlendirmeler","is_takip","is_notlar",
        "randevular","musaitlik","teklifler","odemeler","iade_talepler",
        "portfolyo","ilan_fotograflar","kimlik_dogrulama","video_odalar",
        "ilanlar","uzman_profiller","kullanicilar",
    ]
    for tablo in tablolar:
        try:
            query(f"DELETE FROM {tablo}", fetch="none")
            print(f"   ✅ {tablo}")
        except Exception as e:
            print(f"   ⚠️  {tablo}: {e}")
    print("✅ Temizlendi!\n")

# ─── ÇALIŞTIR ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🔌 Veritabanı hazırlanıyor...")
    init_db()
    init_takvim()
    init_upload_db()
    init_iade_db()
    init_takip_db()
    init_kimlik_db()
    init_video_db()

    if "--temizle" in sys.argv:
        temizle()
        if "--yeniden" not in sys.argv:
            sys.exit(0)

    if query("SELECT id FROM kullanicilar LIMIT 1", fetch="one"):
        if "--zorla" not in sys.argv:
            print("⚠️  Veritabanında zaten veri var!")
            print("   Temizleyip yeniden oluşturmak için: python seed_demo.py --temizle --yeniden")
            print("   Üzerine yazmak için: python seed_demo.py --zorla")
            sys.exit(0)

    seed()

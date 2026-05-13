"""
╔══════════════════════════════════════════════════════════════╗
║           İştek Platform — Veritabanı Modülü                ║
║  Tüm ayarlar .env dosyasından os.environ ile okunur         ║
╚══════════════════════════════════════════════════════════════╝
"""
import os
import pymysql
import pymysql.cursors
from dotenv import load_dotenv

# .env dosyasını yükle — olmasa da hata vermez, ortam değişkenlerini kullanır
load_dotenv()

# ─── VERİTABANI AYARLARI — .env'den okunur ───────────────────────────────────
DB_CONFIG = {
    "host":      os.environ.get("DB_HOST", "localhost"),
    "port":      int(os.environ.get("DB_PORT", 3306)),
    "user":      os.environ.get("DB_USER", "root"),
    "password":  os.environ.get("DB_PASSWORD", ""),
    "db":        os.environ.get("DB_NAME", "istek_db"),
    "charset":   "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}

def get_db():
    """Yeni MySQL bağlantısı açar."""
    return pymysql.connect(**DB_CONFIG)

def query(sql, args=None, fetch="all"):
    """
    SQL sorgusu çalıştıran yardımcı fonksiyon.
    fetch: "all" | "one" | "none" | "id"
    """
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            if fetch == "all":    return cur.fetchall()
            elif fetch == "one":  return cur.fetchone()
            elif fetch == "id":   return cur.lastrowid
            else:                 return None
    finally:
        conn.close()

# ─── ŞEMA ─────────────────────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS kullanicilar (
    id                VARCHAR(36)   PRIMARY KEY,
    ad_soyad          VARCHAR(120)  NOT NULL,
    email             VARCHAR(150)  UNIQUE NOT NULL,
    sifre_hash        VARCHAR(255)  NOT NULL,
    rol               ENUM('musteri','uzman','admin') DEFAULT 'musteri',
    telefon           VARCHAR(20),
    sehir             VARCHAR(80),
    profil_foto       VARCHAR(255),
    aktif             TINYINT(1)    DEFAULT 1,
    email_dogrulandi  TINYINT(1)    DEFAULT 0,
    kimlik_dogrulandi TINYINT(1)    DEFAULT 0,
    giris_deneme      INT           DEFAULT 0,
    kilit_bitis       DATETIME      DEFAULT NULL,
    son_giris         DATETIME      DEFAULT NULL,
    kayit_tarihi      DATETIME      DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_rol   (rol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS uzman_profiller (
    id              VARCHAR(36)   PRIMARY KEY,
    kullanici_id    VARCHAR(36)   UNIQUE NOT NULL,
    kategori        VARCHAR(50),
    saatlik_ucret   INT           DEFAULT 0,
    aciklama        TEXT,
    puan            DECIMAL(3,1)  DEFAULT 0.0,
    is_tamamlanan   INT           DEFAULT 0,
    onaylandi       TINYINT(1)    DEFAULT 0,
    belge_yuklendi  TINYINT(1)    DEFAULT 0,
    uygunluk        TINYINT(1)    DEFAULT 1,
    katilim_tarihi  DATE,
    FOREIGN KEY (kullanici_id) REFERENCES kullanicilar(id) ON DELETE CASCADE,
    INDEX idx_kat  (kategori),
    INDEX idx_onay (onaylandi)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ilanlar (
    id               VARCHAR(36)   PRIMARY KEY,
    baslik           VARCHAR(200)  NOT NULL,
    kategori         VARCHAR(50)   NOT NULL,
    sehir            VARCHAR(80)   NOT NULL,
    butce            INT           DEFAULT 0,
    aciklama         TEXT,
    musteri_id       VARCHAR(36),
    musteri_ad       VARCHAR(100),
    durum            ENUM('aktif','tamamlandi','iptal') DEFAULT 'aktif',
    olusturma_tarihi DATETIME      DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_kat   (kategori),
    INDEX idx_sehir (sehir),
    INDEX idx_durum (durum),
    FOREIGN KEY (musteri_id) REFERENCES kullanicilar(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS teklifler (
    id        VARCHAR(36)  PRIMARY KEY,
    ilan_id   VARCHAR(36)  NOT NULL,
    uzman_id  VARCHAR(36)  NOT NULL,
    fiyat     INT,
    mesaj     TEXT,
    durum     ENUM('beklemede','kabul','red') DEFAULT 'beklemede',
    tarih     DATETIME     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ilan_id)  REFERENCES ilanlar(id)      ON DELETE CASCADE,
    FOREIGN KEY (uzman_id) REFERENCES kullanicilar(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mesajlar (
    id           VARCHAR(36)  PRIMARY KEY,
    gonderen_id  VARCHAR(36)  NOT NULL,
    alici_id     VARCHAR(36)  NOT NULL,
    ilan_id      VARCHAR(36),
    metin        TEXT         NOT NULL,
    okundu       TINYINT(1)   DEFAULT 0,
    tarih        DATETIME     DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (gonderen_id) REFERENCES kullanicilar(id) ON DELETE CASCADE,
    FOREIGN KEY (alici_id)    REFERENCES kullanicilar(id) ON DELETE CASCADE,
    INDEX idx_konusma (gonderen_id, alici_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS odemeler (
    id               VARCHAR(36)    PRIMARY KEY,
    ilan_id          VARCHAR(36)    NOT NULL,
    musteri_id       VARCHAR(36)    NOT NULL,
    uzman_id         VARCHAR(36)    NOT NULL,
    tutar            DECIMAL(10,2)  NOT NULL,
    komisyon         DECIMAL(10,2)  DEFAULT 0,
    durum            ENUM('beklemede','onaylandi','iade','basarisiz') DEFAULT 'beklemede',
    iyzico_token     VARCHAR(255),
    iyzico_odeme_id  VARCHAR(255),
    tarih            DATETIME       DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ilan_id)    REFERENCES ilanlar(id)      ON DELETE CASCADE,
    FOREIGN KEY (musteri_id) REFERENCES kullanicilar(id) ON DELETE CASCADE,
    FOREIGN KEY (uzman_id)   REFERENCES kullanicilar(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS degerlendirmeler (
    id          VARCHAR(36)  PRIMARY KEY,
    ilan_id     VARCHAR(36)  NOT NULL,
    uzman_id    VARCHAR(36)  NOT NULL,
    musteri_id  VARCHAR(36)  NOT NULL,
    puan        TINYINT      NOT NULL CHECK (puan BETWEEN 1 AND 5),
    yorum       TEXT,
    tarih       DATETIME     DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY tek_degerlendirme (ilan_id, musteri_id),
    FOREIGN KEY (uzman_id)   REFERENCES kullanicilar(id) ON DELETE CASCADE,
    FOREIGN KEY (musteri_id) REFERENCES kullanicilar(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS bildirimler (
    id           VARCHAR(36)   PRIMARY KEY,
    kullanici_id VARCHAR(36)   NOT NULL,
    tip          VARCHAR(50),
    baslik       VARCHAR(200),
    metin        TEXT,
    okundu       TINYINT(1)    DEFAULT 0,
    link         VARCHAR(255),
    tarih        DATETIME      DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (kullanici_id) REFERENCES kullanicilar(id) ON DELETE CASCADE,
    INDEX idx_kullanici (kullanici_id),
    INDEX idx_okundu    (okundu)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

def init_db():
    """Veritabanı ve tabloları oluşturur."""
    conn0 = pymysql.connect(
        host=DB_CONFIG["host"], port=DB_CONFIG["port"],
        user=DB_CONFIG["user"], password=DB_CONFIG["password"],
        charset="utf8mb4", autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )
    with conn0.cursor() as cur:
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['db']}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    conn0.close()

    for stmt in [s.strip() for s in SCHEMA.split(";") if s.strip()]:
        satirlar = [l for l in stmt.splitlines() if not l.strip().startswith("--")]
        temiz = "\n".join(satirlar).strip()
        if temiz:
            query(temiz, fetch="none")

    print("✅ Veritabanı şeması hazır.")

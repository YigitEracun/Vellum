# -*- coding: utf-8 -*-
"""Sohbetin yazma araçlarının birim testleri.

Model çağrılmaz, ağa çıkılmaz: araçlar doğrudan çalıştırılır. Gerçek takvim ve
projects/ klasörüne dokunmaz — geçici dizinler kullanır.

Kullanım:  python scripts/test_sohbet_araclari.py
"""

import io
import json
import os
import shutil
import sys
import tempfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "panel"))

import beyin    # noqa: E402
import takvim   # noqa: E402

sonuclar = []


def dene(ad, olan, beklenen):
    durum = "GECTI" if olan == beklenen else "KALDI"
    print("[%s] %-52s olan=%r" % (durum, ad, olan))
    sonuclar.append(durum == "GECTI")
    return durum == "GECTI"


def cagir(arac, **kw):
    """@beta_tool sarmalayıcısının altındaki asıl fonksiyonu çalıştırır."""
    f = getattr(arac, "_function", None) or getattr(arac, "func", None) or arac
    return f(**kw)


def gecici_kok():
    """KOK'u geçici bir dizine alır: projects/ gerçek veriye dokunulmasın."""
    yol = tempfile.mkdtemp(prefix="vellum-test-")
    os.makedirs(os.path.join(yol, "projects"))
    beyin.KOK = yol
    return yol


# ------------------------------------------------------------------ takvim


def takvim_testleri():
    print("--- takvim_ekle / takvim_iptal ---")
    fd, depo = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.remove(depo)
    takvim.DOSYA = depo

    c = cagir(beyin.takvim_ekle, baslik="Ayşe ile görüşme",
              baslangic="2026-09-15T14:00:00+03:00", tur="gorusme")
    dene("etkinlik eklendi", c.startswith("takvime eklendi:"), True)
    kayitlar = takvim.turet()
    dene("depoda tek etkinlik", len(kayitlar), 1)
    dene("baslik dogru", kayitlar[0]["baslik"], "Ayşe ile görüşme")
    dene("tur dogru", kayitlar[0]["tur"], "gorusme")
    dene("kaynak sohbet", kayitlar[0]["kaynak"], "sohbet")

    cagir(beyin.takvim_ekle, baslik="Vergi son günü",
          baslangic="2026-09-30", tur="son_tarih", saatli=False)
    dene("saatsiz etkinlik", takvim.turet()[-1]["saatli"], False)

    cagir(beyin.takvim_ekle, baslik="Bilinmeyen tür", baslangic="2026-10-01",
          tur="saclisapanli")
    dene("gecersiz tur digere duser", takvim.turet()[-1]["tur"], "diger")

    dene("basliksiz etkinlik reddedilir",
         cagir(beyin.takvim_ekle, baslik="  ", baslangic="2026-10-01")
         .startswith("HATA"), True)
    dene("tarihsiz etkinlik reddedilir",
         cagir(beyin.takvim_ekle, baslik="X", baslangic="").startswith("HATA"), True)
    dene("reddedilenler depoya girmedi", len(takvim.turet()), 3)

    kimlik = kayitlar[0]["id"]
    dene("iptal calisir",
         cagir(beyin.takvim_iptal, kimlik=kimlik), "iptal edildi: " + kimlik)
    dene("iptal sonrasi iki etkinlik", len(takvim.turet()), 2)
    dene("olmayan kimlik reddedilir",
         cagir(beyin.takvim_iptal, kimlik="evt_yok").startswith("HATA"), True)

    os.remove(depo)


# ------------------------------------------------------------------- proje


def proje_testleri():
    print("--- proje_ac / proje_olay_ekle ---")
    kok = gecici_kok()
    try:
        c = cagir(beyin.proje_ac, ad="Kayalar Sözleşmesi", ozet="Fiyat konuşuluyor.")
        dene("turkce harfler cevrildi", c, "proje acildi: kayalar-sozlesmesi")
        ad = "kayalar-sozlesmesi"
        klasor = os.path.join(kok, "projects", ad)
        dene("proje.md yazildi", os.path.isfile(os.path.join(klasor, "proje.md")), True)
        dene("olaylar.jsonl acildi",
             os.path.isfile(os.path.join(klasor, "olaylar.jsonl")), True)
        dene("ayni proje ikinci kez acilmaz",
             cagir(beyin.proje_ac, ad=ad), "zaten var: " + ad)
        dene("bos ad reddedilir",
             cagir(beyin.proje_ac, ad="!!!").startswith("HATA"), True)
        dene("bosluk ve alt tire tireye doner",
             beyin._slug("Kayalar  Sözleşme_Dosyası"), "kayalar-sozlesme-dosyasi")
        dene("bastaki sondaki tire kirpilir", beyin._slug(" -Ayşe- "), "ayse")

        c = cagir(beyin.proje_olay_ekle, proje=ad,
                  baslik="Ayşe fiyat revizesi istedi", tip="blokaj",
                  detay="Mevcut teklif bütçeyi aşıyor.", etiket="fiyat, sozlesme")
        dene("olay eklendi", c.startswith("olay eklendi:"), True)

        satirlar = [json.loads(s) for s in
                    io.open(os.path.join(klasor, "olaylar.jsonl"), encoding="utf-8")
                    if s.strip()]
        dene("tek olay yazildi", len(satirlar), 1)
        o = satirlar[0]
        dene("tip korundu", o["tip"], "blokaj")
        dene("etiketler ayrildi", o["etiket"], ["fiyat", "sozlesme"])
        dene("kaynak sohbet", o["kaynak"], "sohbet")
        dene("onay beklemez", o["onaylanmamis"], False)

        dene("olmayan proje reddedilir",
             cagir(beyin.proje_olay_ekle, proje="yok-boyle",
                   baslik="X").startswith("HATA:"), True)
        dene("gecersiz tip reddedilir",
             cagir(beyin.proje_olay_ekle, proje=ad, baslik="X",
                   tip="zibidi").startswith("HATA"), True)
        dene("basliksiz olay reddedilir",
             cagir(beyin.proje_olay_ekle, proje=ad, baslik=" ").startswith("HATA"),
             True)
        dene("reddedilenler dosyaya yazilmadi",
             len(io.open(os.path.join(klasor, "olaylar.jsonl"),
                         encoding="utf-8").read().strip().split("\n")), 1)

        # Yol kacisi: proje adi klasor disina cikamaz.
        dene("ust klasore kacilamaz",
             cagir(beyin.proje_olay_ekle, proje="../../secrets",
                   baslik="X").startswith("HATA"), True)

        # Izolasyon: durum tazeleme sunucunun KOK'unu kullaniyor. Kokler
        # ayrisiksa gercek projects/ klasorune yazmamali — bir kez yazdi.
        gercek = os.path.join(KOK, "projects", ad)
        dene("gercek projects/ klasorune sizmadi", os.path.exists(gercek), False)
    finally:
        shutil.rmtree(kok, ignore_errors=True)


def arac_listesi_testleri():
    print("--- arac listeleri ---")
    adlar = [a.name for a in beyin.SOHBET_ARACLARI]
    dene("sohbet takvime yazabiliyor", "takvim_ekle" in adlar, True)
    dene("sohbet projeye yazabiliyor", "proje_olay_ekle" in adlar, True)
    dene("sohbet dosya_yaz alamaz", "dosya_yaz" in adlar, False)
    dene("sohbet dosya_ekle alamaz", "dosya_ekle" in adlar, False)
    dene("okuma araclari duruyor", "dosya_oku" in adlar, True)


def main():
    takvim_testleri()
    proje_testleri()
    arac_listesi_testleri()
    gecen = sum(1 for s in sonuclar if s)
    print("\n%d/%d test gecti" % (gecen, len(sonuclar)))
    return 0 if gecen == len(sonuclar) else 1


if __name__ == "__main__":
    sys.exit(main())

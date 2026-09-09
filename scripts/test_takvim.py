# -*- coding: utf-8 -*-
"""Takvim deposu ve hatırlatma mantığının birim testleri.

Gerçek veriye dokunmaz: geçici bir depo dosyası kullanır.

Kullanım:  python scripts/test_takvim.py
"""

import os
import sys
import tempfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "panel"))
sys.path.insert(0, os.path.join(KOK, "scripts"))

import takvim  # noqa: E402

sonuclar = []


def dene(ad, olan, beklenen):
    durum = "GECTI" if olan == beklenen else "KALDI"
    print("[%s] %-52s olan=%r" % (durum, ad, olan))
    sonuclar.append(durum == "GECTI")
    return durum == "GECTI"


def temiz_depo():
    fd, yol = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.remove(yol)
    takvim.DOSYA = yol
    return yol


def depo_testleri():
    print("--- depo ---")
    temiz_depo()

    a = takvim.ekle("Mülakat", "2026-09-13T14:00:00+03:00", tur="mulakat")
    takvim.ekle("Diş hekimi", "2026-09-20T10:30:00+03:00")
    dene("iki etkinlik eklendi", len(takvim.turet()), 2)

    # Duzeltme: ayni id ile yeni satir oncekini golgeler
    takvim.ekle("Mülakat — saat değişti", "2026-09-13T16:00:00+03:00",
                tur="mulakat", kimlik=a["id"])
    guncel = [e for e in takvim.turet() if e["id"] == a["id"]][0]
    dene("duzeltme golgeliyor (baslik)", guncel["baslik"], "Mülakat — saat değişti")
    dene("duzeltme golgeliyor (saat)", guncel["baslangic"][11:16], "16:00")
    dene("duzeltme yeni kayit uretmiyor", len(takvim.turet()), 2)

    # Iptal
    dene("iptal islendi", takvim.iptal_et(a["id"]), True)
    dene("iptal sonrasi listede yok", len(takvim.turet()), 1)
    dene("olmayan id iptal edilemez", takvim.iptal_et("evt_yok"), False)

    # Pencere filtresi
    takvim.ekle("Eski toplantı", "2026-01-05T09:00:00+03:00")
    dene("aralik filtresi", len(takvim.etkinlikler("2026-09-01", "2026-09-30")), 1)

    # Kaynak tekrari
    temiz_depo()
    takvim.mailden_ekle("6550", {"baslik": "Mülakat", "tur": "mulakat",
                                 "baslangic": "2026-09-13T14:00:00+03:00"})
    ikinci = takvim.mailden_ekle("6550", {"baslik": "Mülakat", "tur": "mulakat",
                                          "baslangic": "2026-09-13T14:00:00+03:00"})
    dene("ayni mail ikinci kez yazilmaz", ikinci, None)
    dene("tek etkinlik var", len(takvim.turet()), 1)

    # Kullanici kaldirdiysa tarama geri getirmemeli
    kimlik = takvim.turet()[0]["id"]
    takvim.iptal_et(kimlik)
    dene("iptal edilen mail etkinligi geri gelmiyor",
         takvim.mailden_ekle("6550", {"baslik": "Mülakat",
                                      "baslangic": "2026-09-13T14:00:00+03:00"}), None)

    # Yalnizca gun verilmisse
    temiz_depo()
    k = takvim.mailden_ekle("777", {"baslik": "Son tarih", "baslangic": "2026-09-13",
                                    "tur": "son_tarih"})
    dene("gun-only kabul edildi", bool(k), True)
    dene("gun-only saatsiz isaretlendi", k["saatli"], False)

    # Uydurma / eksik veri reddedilir
    temiz_depo()
    dene("baslangicsiz etkinlik reddedilir",
         takvim.mailden_ekle("1", {"baslik": "X"}), None)
    dene("bozuk tarih reddedilir",
         takvim.mailden_ekle("2", {"baslik": "X", "baslangic": "gelecek hafta"}), None)
    dene("etkinlik nesnesi degilse reddedilir", takvim.mailden_ekle("3", None), None)


def hatirlatma_testleri():
    print("\n--- hatirlatma ---")
    import izleyici
    temiz_depo()
    fd, kayit_yolu = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd); os.remove(kayit_yolu)
    izleyici.HATIRLATMA_DOSYASI = kayit_yolu

    from datetime import datetime, timedelta
    TZ = takvim.TZ
    bugun = datetime(2026, 9, 13, 8, 30, tzinfo=TZ)      # etkinlik gunu sabahi
    dun = datetime(2026, 9, 12, 8, 30, tzinfo=TZ)        # bir gun oncesi sabah
    onceki_aksam = datetime(2026, 9, 11, 20, 0, tzinfo=TZ)

    takvim.ekle("Mülakat", "2026-09-13T14:00:00+03:00", tur="mulakat")

    dene("iki gun once hatirlatma yok", len(izleyici.hatirlatilacaklar(onceki_aksam)), 0)

    bir_gun_once = izleyici.hatirlatilacaklar(dun)
    dene("bir gun once tetiklendi", len(bir_gun_once), 1)
    dene("metinde 'yarın' geciyor", "yarın" in bir_gun_once[0]["alt"].lower(), True)
    dene("saat yaziliyor", "14:00" in bir_gun_once[0]["alt"], True)

    izleyici.hatirlatma_isaretle(bir_gun_once[0])
    dene("ayni pencere ikinci kez tetiklenmiyor",
         len(izleyici.hatirlatilacaklar(dun)), 0)

    gun_sabahi = izleyici.hatirlatilacaklar(bugun)
    dene("etkinlik sabahi tetiklendi", len(gun_sabahi), 1)
    dene("metinde 'bugün' geciyor", "bugün" in gun_sabahi[0]["alt"].lower(), True)

    # Gecmis etkinlik hatirlatilmaz
    temiz_depo()
    takvim.ekle("Geçmiş toplantı", "2026-09-01T10:00:00+03:00")
    dene("gecmis etkinlik hatirlatilmaz", len(izleyici.hatirlatilacaklar(bugun)), 0)

    # Saatsiz etkinlikte saat cumlesi kurulmaz
    temiz_depo()
    takvim.ekle("Son tarih", "2026-09-13T09:00:00+03:00", saatli=False, tur="son_tarih")
    saatsiz = izleyici.hatirlatilacaklar(bugun)
    dene("saatsiz etkinlik tetikleniyor", len(saatsiz), 1)
    dene("saatsizde saat yazilmiyor", "09:00" in saatsiz[0]["alt"], False)

    # Sabahtan once hatirlatma verilmez
    temiz_depo()
    takvim.ekle("Mülakat", "2026-09-13T14:00:00+03:00")
    gece = datetime(2026, 9, 13, 3, 0, tzinfo=TZ)
    dene("sabah 08:00'den once tetiklenmiyor", len(izleyici.hatirlatilacaklar(gece)), 0)


if __name__ == "__main__":
    depo_testleri()
    hatirlatma_testleri()
    print("\n%d/%d gecti" % (sum(sonuclar), len(sonuclar)))
    sys.exit(0 if all(sonuclar) else 1)

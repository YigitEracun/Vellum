# -*- coding: utf-8 -*-
"""Hafıza deposunun ve sayımın birim testleri.

Ağa çıkmaz, model çağırmaz, gerçek hafızaya dokunmaz: geçici dosya kullanır.

Kullanım:  python scripts/test_hafiza.py
"""

import io
import json
import os
import sys
import tempfile
from datetime import timedelta

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "panel"))

import hafiza  # noqa: E402
import sayim   # noqa: E402

sonuclar = []


def dene(ad, olan, beklenen):
    durum = "GECTI" if olan == beklenen else "KALDI"
    print("[%s] %-54s olan=%r" % (durum, ad, olan))
    sonuclar.append(durum == "GECTI")
    return durum == "GECTI"


def temiz_depo():
    fd, yol = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.remove(yol)
    hafiza.DOSYA = yol
    return yol


def geri_tarihle(kimlik, gun):
    """Bir olgunun son görülme tarihini geçmişe çeker — bayatlamayı denemek için."""
    satirlar = [json.loads(s) for s in
                io.open(hafiza.DOSYA, encoding="utf-8") if s.strip()]
    eski = (hafiza.simdi() - timedelta(days=gun)).isoformat()
    with io.open(hafiza.DOSYA, "w", encoding="utf-8") as f:
        for k in satirlar:
            if k.get("id") == kimlik:
                k["son_gorulme"] = eski
                k["t"] = eski
            f.write(json.dumps(k, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------- depo


def depo_testleri():
    print("--- depo ---")
    temiz_depo()

    dene("bos depo bos liste", hafiza.turet(), [])
    dene("bos depoda ozet yok", hafiza.ozet(), "")

    o = hafiza.yaz("meslek", "mimarlık", "Kullanıcı mimar",
                   kelimeler=["mimar", "ruhsat"])
    dene("olgu yazildi", len(hafiza.turet()), 1)
    dene("varsayilan agirlik turden geldi", o["agirlik"], 25)
    dene("ilk gorulme bir", o["gorulme"], 1)
    dene("kelimeler kucuk harf", o["kelimeler"], ["mimar", "mimarlık", "ruhsat"])

    # Ayni anahtar yeniden ogrenilince pekisir, ikinci olgu acilmaz.
    o2 = hafiza.yaz("meslek", "Mimarlık", "Mimar, ruhsat işleriyle uğraşıyor",
                    kelimeler=["imar"])
    dene("ayni anahtar yeni olgu acmaz", len(hafiza.turet()), 1)
    dene("ayni kimlik korundu", o2["id"], o["id"])
    dene("gorulme artti", o2["gorulme"], 2)
    dene("kelimeler birlesti", o2["kelimeler"],
         ["imar", "mimar", "mimarlık", "ruhsat"])
    dene("aciklama guncellendi",
         hafiza.turet()[0]["deger"], "Mimar, ruhsat işleriyle uğraşıyor")

    hafiza.yaz("yer", "Bodrum", "Yazları Bodrum'a gidiyor")
    dene("farkli tur ayri olgu", len(hafiza.turet()), 2)

    # Unutma: satir silinmez, uzerine unutma satiri yazilir.
    dene("unut calisir", hafiza.unut(o["id"]), True)
    dene("unutulan listede yok", len(hafiza.turet()), 1)
    ham = [s for s in io.open(hafiza.DOSYA, encoding="utf-8") if s.strip()]
    dene("ozgun satirlar duruyor", len(ham), 4)
    dene("olmayan kimlik unutulamaz", hafiza.unut("h_yok"), False)

    dene("bos anahtar reddedilir",
         _hata_verir(lambda: hafiza.yaz("ilg" + "i", "  ", "x")), True)
    dene("gecersiz tur reddedilir",
         _hata_verir(lambda: hafiza.yaz("zibidi", "x", "y")), True)


def _hata_verir(f):
    try:
        f()
        return False
    except ValueError:
        return True


def agirlik_testleri():
    print("--- agirlik ve bayatlama ---")
    temiz_depo()

    o = hafiza.yaz("ilgi", "yelken", "Yelken yapıyor")
    dene("ilgi varsayilani", hafiza.guncel_agirlik(o), 15)

    geri_tarihle(o["id"], 100)
    taze = hafiza.turet()[0]
    dene("90 gun sonra yariya iner", hafiza.guncel_agirlik(taze), 7)

    geri_tarihle(o["id"], 200)
    taze = hafiza.turet()[0]
    dene("180 gun sonra ceyrege iner", hafiza.guncel_agirlik(taze), 3)

    # Elle ayarlanan agirlik bayatlamaz.
    dene("agirlik degistirilir", hafiza.agirlik_degistir(o["id"], 40), True)
    taze = hafiza.turet()[0]
    dene("elle agirlik bayatlamaz", hafiza.guncel_agirlik(taze), 40)
    dene("elle kaynagi isaretlendi", taze["kaynak"], "elle")
    dene("olmayan olgunun agirligi degismez",
         hafiza.agirlik_degistir("h_yok", 10), False)

    hafiza.yaz("meslek", "abartı", "x", agirlik=999)
    dene("agirlik tavanda kirpilir",
         max(o["agirlik"] for o in hafiza.turet()), hafiza.EN_COK)


def okuyan_testleri():
    print("--- skorlama girdisi ve ozet ---")
    temiz_depo()
    dene("bos hafiza bos girdi", hafiza.skorlama_girdisi(),
         {"kelimeler": [], "kisiler": {}})

    hafiza.yaz("meslek", "mimarlık", "Mimar", kelimeler=["mimar", "ruhsat"])
    hafiza.yaz("kisi", "Ayşe", "Haftalık görüşüyor", adres="ayse@ornek.com")

    g = hafiza.skorlama_girdisi()
    dene("kelimeler cikti", sorted(k["kelime"] for k in g["kelimeler"]),
         ["ayşe", "mimar", "mimarlık", "ruhsat"])
    dene("kisi adresi cikti", g["kisiler"], {"ayse@ornek.com": 20})
    dene("kelime agirligi tasindi",
         [k["agirlik"] for k in g["kelimeler"] if k["kelime"] == "ruhsat"], [25])

    ozet = hafiza.ozet()
    dene("ozet meslegi anlatiyor", "Mimar" in ozet, True)
    dene("ozet adresi tasiyor", "ayse@ornek.com" in ozet, True)
    dene("ozet sinirin altinda", len(ozet.split("\n")) <= hafiza.OZET_SINIR, True)

    # Tamamen bayatlamis olgu skorlamaya hic gitmez.
    temiz_depo()
    k = hafiza.yaz("alistigi", "kahve", "Sabah kahvesi")   # agirlik 10
    geri_tarihle(k["id"], 200)                             # 10 // 4 = 2
    dene("cok bayat olgu hala az da olsa sayilir",
         len(hafiza.skorlama_girdisi()["kelimeler"]), 1)


def gruplu_testleri():
    print("--- panel gorunumu ---")
    temiz_depo()
    hafiza.yaz("meslek", "mimarlık", "Mimar")
    hafiza.yaz("yer", "Bodrum", "Yazlık")
    g = hafiza.gruplu()
    dene("turlere gore gruplandi", [x["tur"] for x in g], ["meslek", "yer"])
    dene("baslik turkce", g[0]["baslik"], "İşi")
    dene("guncel agirlik hesaplandi",
         g[0]["olgular"][0]["guncel_agirlik"], 25)
    dene("bayat isareti yok", g[0]["olgular"][0]["bayat"], False)


# -------------------------------------------------------------------- sayim


def sayim_testleri():
    print("--- sayim (modelsiz) ---")

    # Kisi sikligi: gonderilen + gelen sayilir, esigin altindakiler elenir.
    gonderilen = {"ayse@ornek.com": 8, "mehmet@ornek.com": 2,
                  "bulten@magaza.com": 40}
    maddeler = [
        {"gonderen": "Ayşe <ayse@ornek.com>", "konu": "Kayalar sözleşmesi",
         "ham_skor": 80},
        {"gonderen": "Ayşe <ayse@ornek.com>", "konu": "Kayalar revizesi",
         "ham_skor": 75},
        {"gonderen": "Mehmet <mehmet@ornek.com>", "konu": "merhaba",
         "ham_skor": 30},
        {"gonderen": "Mağaza <bulten@magaza.com>", "konu": "İndirim",
         "ham_skor": 10, "toplu": True},
    ]

    kisiler = sayim.kisiler(gonderilen, maddeler)
    adresler = {k["adres"]: k for k in kisiler}
    dene("sik yazisan secildi", "ayse@ornek.com" in adresler, True)
    dene("iki kez yazisan elendi", "mehmet@ornek.com" in adresler, False)
    dene("bulten adresi elendi", "bulten@magaza.com" in adresler, False)
    dene("agirlik sikliga gore olcekli",
         hafiza.VARSAYILAN_AGIRLIK["kisi"] <= adresler["ayse@ornek.com"]["agirlik"]
         <= 25, True)

    # Tekrar eden adlar: 3+ kez, 2+ farkli gonderici.
    adlar = sayim.adlar(maddeler)
    dene("iki kez gecen ad alinmaz", adlar, [])

    cok = maddeler + [
        {"gonderen": "Ali <ali@ornek.com>", "konu": "Kayalar toplantısı",
         "ham_skor": 70},
    ]
    adlar = sayim.adlar(cok)
    dene("uc kez iki gondericiden gecen ad alindi",
         [a["ad"] for a in adlar], ["Kayalar"])

    dusuk = [dict(m, ham_skor=10) for m in cok]
    dene("esigin altindaki mailler sayilmaz", sayim.adlar(dusuk), [])


# ----------------------------------------------------------------- skorlama


def skorlama_testleri():
    print("--- skorlamaya etkisi ---")
    import skorlama

    mail = {"gonderen": "Biri <biri@ornek.com>", "konu": "Ruhsat dosyası",
            "govde": "Ruhsat başvurusu için evrak lazım."}

    bos = skorlama.Skorlayici(kullanici="ben@ornek.com",
                              vip=[], gurultu=[],
                              hafiza_girdisi={"kelimeler": [], "kisiler": {}})
    once = bos.skorla(mail)["ham_skor"]

    girdi = {"kelimeler": [{"kelime": "ruhsat", "agirlik": 25,
                            "anahtar": "mimarlık", "id": "h_1"}],
             "kisiler": {}}
    dolu = skorlama.Skorlayici(kullanici="ben@ornek.com", vip=[], gurultu=[],
                               hafiza_girdisi=girdi)
    sonuc = dolu.skorla(mail)
    dene("hafiza skoru yukseltti", sonuc["ham_skor"], once + 25)
    dene("sinyal anahtarla goruntulendi",
         "hafiza:mimarlık +25" in sonuc["sinyaller"], True)

    # Ek duyarli: "ruhsatı" da yakalanmali.
    cekimli = dict(mail, govde="Ruhsatı bekliyoruz.", konu="Durum")
    dene("cekim eki yakalandi",
         any(s.startswith("hafiza:") for s in dolu.skorla(cekimli)["sinyaller"]),
         True)

    # Alakasiz mail etkilenmemeli.
    alakasiz = {"gonderen": "Biri <biri@ornek.com>", "konu": "Merhaba",
                "govde": "Nasılsın"}
    dene("alakasiz mail etkilenmedi",
         dolu.skorla(alakasiz)["ham_skor"], bos.skorla(alakasiz)["ham_skor"])

    # Tavan: cok sayida olgu tek maile sinirsiz puan yagdiramaz.
    cok = {"kelimeler": [{"kelime": "ruhsat", "agirlik": 40, "anahtar": "a", "id": "1"},
                         {"kelime": "evrak", "agirlik": 40, "anahtar": "b", "id": "2"},
                         {"kelime": "dosya", "agirlik": 40, "anahtar": "c", "id": "3"}],
           "kisiler": {}}
    tavanli = skorlama.Skorlayici(kullanici="ben@ornek.com", vip=[], gurultu=[],
                                  hafiza_girdisi=cok)
    fark = tavanli.skorla(mail)["ham_skor"] - once
    dene("hafiza katkisi tavanda kirpildi", fark, skorlama.HAFIZA_TAVANI)

    # Kisi: VIP ya da yazistiginiz-kisi zaten saydiysa tekrarlanmaz.
    kisili = {"kelimeler": [], "kisiler": {"biri@ornek.com": 20}}
    s = skorlama.Skorlayici(kullanici="ben@ornek.com", vip=[], gurultu=[],
                            hafiza_girdisi=kisili)
    s.yazistiklarim = set()
    dene("sik yazisilan sinyali eklendi",
         "sik-yazisilan +20" in s.skorla(mail)["sinyaller"], True)

    s2 = skorlama.Skorlayici(kullanici="ben@ornek.com",
                             vip=["biri@ornek.com"], gurultu=[],
                             hafiza_girdisi=kisili)
    dene("vip varken hafiza kisisi tekrarlamaz",
         any(x.startswith("sik-yazisilan") for x in s2.skorla(mail)["sinyaller"]),
         False)

    # Bultende hafiza sinyali sayilmaz.
    bulten = dict(mail, toplu=True)
    dene("bultende hafiza sinyali yok",
         any(x.startswith("hafiza:") for x in dolu.skorla(bulten)["sinyaller"]),
         False)


def main():
    depo_testleri()
    agirlik_testleri()
    okuyan_testleri()
    gruplu_testleri()
    sayim_testleri()
    skorlama_testleri()
    gecen = sum(1 for s in sonuclar if s)
    print("\n%d/%d test gecti" % (gecen, len(sonuclar)))
    return 0 if gecen == len(sonuclar) else 1


if __name__ == "__main__":
    sys.exit(main())

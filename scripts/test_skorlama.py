# -*- coding: utf-8 -*-
"""Kural motorunun birim testleri.

Gerçek adres kullanılmaz: testler kimin makinesinde çalıştığından bağımsız geçmeli.

Kullanım:  python scripts/test_skorlama.py
"""

import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "panel"))

import skorlama  # noqa: E402

BEN = "ben@ornek.com"


def mail(**k):
    """Varsayılan alanlarla bir ham mail kaydı üretir."""
    temel = {
        "id": "1", "gonderen": "Biri <biri@ornek.com>", "alici": [BEN], "cc": [],
        "konu": "konu", "tarih": "2026-09-08T10:00:00+03:00", "thread_id": "t1",
        "govde": "govde", "ekler": [], "toplu": False,
    }
    temel.update(k)
    return temel


def esit(ad, olan, beklenen):
    durum = "GECTI" if olan == beklenen else "KALDI"
    print("[%s] %-46s olan=%s beklenen=%s" % (durum, ad, olan, beklenen))
    return durum == "GECTI"


def buyuk(ad, olan, esik):
    durum = "GECTI" if olan >= esik else "KALDI"
    print("[%s] %-46s skor=%s (>= %s olmali)" % (durum, ad, olan, esik))
    return durum == "GECTI"


def kucuk(ad, olan, esik):
    durum = "GECTI" if olan < esik else "KALDI"
    print("[%s] %-46s skor=%s (< %s olmali)" % (durum, ad, olan, esik))
    return durum == "GECTI"


def calistir():
    s = skorlama.Skorlayici(kullanici=BEN, vip=["patron@firma.com"],
                            gurultu=["spam@reklam.com"])
    t = []

    # --- taban ve dogrudan yazilma
    t.append(esit("taban + dogrudan yazilmis",
                  s.skorla(mail())["ham_skor"], 50))
    t.append(esit("CC'de olmak dogrudan sayilmaz",
                  s.skorla(mail(alici=["baskasi@ornek.com"], cc=[BEN]))["ham_skor"], 15))

    # --- listeler
    t.append(buyuk("VIP gonderen", s.skorla(mail(gonderen="P <patron@firma.com>"))["ham_skor"], 90))
    t.append(kucuk("gurultu listesindeki gonderen",
                   s.skorla(mail(gonderen="R <spam@reklam.com>"))["ham_skor"], 40))

    # --- toplu gonderim (List-Unsubscribe vb.)
    t.append(kucuk("toplu gonderim basligi tasiyan mail",
                   s.skorla(mail(toplu=True))["ham_skor"], 40))
    t.append(kucuk("noreply gondereni",
                   s.skorla(mail(gonderen="X <no-reply@sirket.com>"))["ham_skor"], 40))

    # --- icerik sinyalleri
    t.append(buyuk("fatura/odeme konusu",
                   s.skorla(mail(konu="Ağustos faturanız ve ödeme bilgisi"))["ham_skor"], 70))
    t.append(buyuk("son tarih iceren mail",
                   s.skorla(mail(govde="Cuma 17:00'a kadar dönebilir misiniz?"))["ham_skor"], 70))

    # Pazarlama maili her zaman tarih, fiyat ve soru tasir; bunlar toplu gonderim
    # cezasini geri kapatmamali. Bultende gecen tarih sizin son tarihiniz degil.
    reklam = mail(gonderen="Kampanya <no-reply@magaza.com>",
                  konu="Son 3 gün! %40 indirim — kaçırmak ister misiniz?",
                  govde="Cuma 23:59'a kadar geçerli. Fiyatlar 199 TL'den başlıyor.")
    t.append(kucuk("bultendeki tarih/fiyat/soru sayilmaz", s.skorla(reklam)["ham_skor"], 40))
    # Ama VIP'ten gelen ayni icerik sayilir.
    t.append(buyuk("VIP'ten gelen tarihli mail sayilir",
                   s.skorla(mail(gonderen="P <patron@firma.com>",
                                 govde="Cuma 17:00'a kadar lazım"))["ham_skor"], 70))

    # --- is basvurusu ayrimi (kullanicinin acik tercihi)
    onaylar = [
        ("Thank you for applying to Acme", "Acme <notification@sr.com>"),
        ("Başvurunuz Başarıyla İletilmiştir", "Mplus <m@talently.com>"),
        ("Indeed Başvuru: Backend Developer", "Indeed <indeedapply@indeed.com>"),
        ("Köszönjük, hogy benyújtottad jelentkezésed", "Ornek AG <notification@sr.com>"),
    ]
    for konu, gon in onaylar:
        t.append(kucuk("basvuru ONAYI onemsiz: %.32s" % konu,
                       s.skorla(mail(konu=konu, gonderen=gon))["ham_skor"], 40))

    ilerlemeler = [
        "Mülakat daveti — Salı 14:00",
        "Görüşme talebi: Backend Developer pozisyonu",
        "Interview invitation for Senior Developer",
        "We would like to move forward — next step",
        "İş teklifi: Yazılım Geliştirici",
    ]
    for konu in ilerlemeler:
        t.append(buyuk("sirketten ILERLEME onemli: %.32s" % konu,
                       s.skorla(mail(konu=konu, gonderen="IK <ik@sirket.com>"))["ham_skor"], 70))

    # Ayrim gonderene degil konuya bakar: ayni adresten ikisi de gelebilir.
    ayni = "Kariyer <kariyer@sirket.com>"
    t.append(kucuk("ayni adresten onay",
                   s.skorla(mail(gonderen=ayni, konu="Başvurunuz alındı"))["ham_skor"], 40))
    t.append(buyuk("ayni adresten mulakat daveti",
                   s.skorla(mail(gonderen=ayni, konu="Mülakat daveti"))["ham_skor"], 70))

    # Bultenin govdesinde gecen "interview" mulakat daveti degildir; ama ayni
    # kelime bir basvuru sistemi (ATS) mailinde geciyorsa onemlidir.
    t.append(kucuk("bulten govdesindeki 'interview' sayilmaz",
                   s.skorla(mail(gonderen="Glassdoor <noreply@glassdoor.com>", toplu=True,
                                 konu="NewTechWood: What You Need to Know",
                                 govde="Interview tips for your next job"))["ham_skor"], 40))
    t.append(buyuk("ATS'ten (noreply) gelen mulakat daveti onemli",
                   s.skorla(mail(gonderen="Kariyer <noreply@smartrecruiters.com>", toplu=False,
                                 konu="Mülakat daveti — Perşembe 11:00"))["ham_skor"], 70))

    # --- Turkce ek duyarli eslesme
    # Turkce sondan eklemeli: sozluk "fatura" yazar, metin "faturanız" der.
    # Kapanis \b olmadan "kaza" govdesi "kazandınız" icinde eslesiyordu.
    kalip = skorlama.kalip_kur(["fatura", "sözleşme", "ödeme", "mülakat",
                                "kaza", "ders", "vize", "alın", "son tarih"])
    for metin in ("faturanız", "sözleşmeyi", "ödemenizi", "mülakata", "fatura",
                  "son tarihe kadar", "SÖZLEŞMENİN", "alındı", "alınmıştır",
                  "vizeniz", "kaza raporu"):
        t.append(esit("ek duyarli: %-18s yakalanmali" % metin,
                      bool(kalip.search(metin)), True))
    for metin in ("kazandınız", "kazanç", "derslik", "vizyon", "davetiye",
                  "faturalandırma sistemi"):
        t.append(esit("yanlis pozitif degil: %-14s" % metin,
                      bool(kalip.search(metin)), False))

    # `...` yazimi: araya kelime girebilir.
    yakin = skorlama.kalip_kur(["başvurunuz ... iletil"])
    t.append(esit("yakinlik: 'Başvurunuz Başarıyla İletilmiştir'",
                  bool(yakin.search("Başvurunuz Başarıyla İletilmiştir")), True))
    t.append(esit("yakinlik: 30 karakterden uzak eslesmez",
                  bool(yakin.search("Başvurunuz " + "x" * 40 + " iletildi")), False))

    # --- sozluk ayristirma
    sz = skorlama.sozluk()
    t.append(esit("sozluk kategorileri okundu", len(sz) >= 8, True))
    t.append(esit("agirlik dogru okundu", sz["para-sozlesme"]["agirlik"], 30))
    t.append(esit("negatif agirlik okundu", sz["is-basvurusu-onayi"]["agirlik"], -40))
    t.append(esit("bicim basliklari kategori sayilmadi",
                  any(a in sz for a in ("biçim", "bicim", "anahtar")), False))

    # --- kimlik bagimsizligi
    bos = skorlama.Skorlayici(kullanici=None)
    r = bos.skorla(mail())
    t.append(esit("kullanici bilinmiyorsa dogrudan/CC sinyali atlanir",
                  any(x.startswith("dogrudan") or x.startswith("cc") for x in r["sinyaller"]),
                  False))
    baskasi = skorlama.Skorlayici(kullanici="baska@kisi.com")
    t.append(esit("baska kullanicida dogrudan sinyali tetiklenmez",
                  baskasi.skorla(mail())["ham_skor"], 30))

    # --- kirpma ve siralama alanlari
    r = s.skorla(mail(gonderen="P <patron@firma.com>",
                      konu="Sözleşme — cuma son tarih, fatura ekte"))
    t.append(buyuk("ham skor 100'u asabilir", r["ham_skor"], 101))
    t.append(esit("gosterilen skor 0-100'e kirpilir", r["skor"], 100)
             and esit("kirpilan skor ham'dan kucuk", r["skor"] < r["ham_skor"], True))
    t.append(esit("negatif skor 0'a kirpilir",
                  s.skorla(mail(toplu=True, gonderen="X <noreply@a.com>"))["skor"], 0))

    print("\n%d/%d gecti" % (sum(t), len(t)))
    return all(t)


if __name__ == "__main__":
    sys.exit(0 if calistir() else 1)

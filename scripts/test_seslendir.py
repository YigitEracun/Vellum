# -*- coding: utf-8 -*-
"""Seslendirme katmanının birim testleri.

Ağa çıkmaz: edge-tts çağrısı taklit edilir. Gerçek ses üretimi
`python panel/seslendir.py "deneme"` ile ayrıca denenir.

Kullanım:  python scripts/test_seslendir.py
"""

import os
import shutil
import sys
import tempfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "panel"))

import seslendir  # noqa: E402

sonuclar = []


def dene(ad, olan, beklenen):
    durum = "GECTI" if olan == beklenen else "KALDI"
    print("[%s] %-52s olan=%r" % (durum, ad, olan))
    sonuclar.append(durum == "GECTI")
    return durum == "GECTI"


def temiz_klasor():
    yol = tempfile.mkdtemp(prefix="vellum-ses-")
    seslendir.KLASOR = yol
    return yol


class SahteUretim(object):
    """_uret yerine geçer: ağa çıkmaz, kaç kez çağrıldığını sayar."""

    def __init__(self, hata=None):
        self.sayac = 0
        self.cagrilar = []
        self.hata = hata

    def __call__(self, metin, yol, ses, hiz):
        self.sayac += 1
        self.cagrilar.append({"metin": metin, "ses": ses, "hiz": hiz})
        if self.hata:
            raise self.hata
        with open(yol, "wb") as d:
            d.write(b"ID3sahte-ses")


# ------------------------------------------------------------------ metin


def metin_testleri():
    print("--- okunacak hale getirme ---")
    g = seslendir.okunacak_hale_getir

    dene("yildizlar atilir", g("**Kayalar** sözleşmesi"), "Kayalar sözleşmesi")
    dene("alt cizgi atilir", g("_önemli_ konu"), "önemli konu")
    dene("baslik isareti atilir", g("## Bugün"), "Bugün")
    dene("madde imi atilir", g("- ilk madde"), "ilk madde")
    dene("baglanti atilir",
         g("Detay https://ornek.com/a/b adresinde"), "Detay adresinde")
    dene("kod blogu atilir", g("şu `kod` burada"), "şu burada")
    dene("uzun cizgi virgule doner",
         g("Kayalar — 17:00"), "Kayalar , 17:00")
    dene("emoji atilir", g("Tamamdır 👍"), "Tamamdır")
    dene("bos satirlar tekillesir", g("bir\n\n\niki"), "bir\niki")
    dene("bos metin bos doner", g(""), "")
    dene("bosluk metni bos doner", g("   \n  "), "")
    dene("None cokmez", g(None), "")
    dene("duz metin korunur",
         g("Yarın saat üçte görüşelim."), "Yarın saat üçte görüşelim.")


def anahtar_testleri():
    print("--- cache anahtari ---")
    a = seslendir.anahtar("merhaba")
    dene("ayni metin ayni anahtar", seslendir.anahtar("merhaba"), a)
    dene("farkli metin farkli anahtar", seslendir.anahtar("merhabaa") != a, True)
    dene("ses degisince anahtar degisir",
         seslendir.anahtar("merhaba", ses="tr-TR-EmelNeural") != a, True)
    dene("hiz degisince anahtar degisir",
         seslendir.anahtar("merhaba", hiz="+30%") != a, True)
    dene("anahtar dosya adina uygun",
         all(c in "0123456789abcdef" for c in a), True)


# ------------------------------------------------------------------ uretim


def uretim_testleri():
    print("--- uretim ve cache ---")
    klasor = temiz_klasor()
    asil = seslendir._uret
    sahte = SahteUretim()
    seslendir._uret = sahte
    try:
        yol = seslendir.seslendir("Merhaba.")
        dene("mp3 uretildi", bool(yol) and os.path.isfile(yol), True)
        dene("dosya ses klasorunde",
             os.path.dirname(yol) == klasor, True)
        dene("uretim bir kez cagrildi", sahte.sayac, 1)

        ayni = seslendir.seslendir("Merhaba.")
        dene("ikinci cagri ayni dosya", ayni, yol)
        dene("ikinci cagri aga gitmedi", sahte.sayac, 1)

        seslendir.seslendir("Baska bir cumle.")
        dene("farkli metin yeniden uretti", sahte.sayac, 2)

        seslendir.seslendir("**Merhaba.**")
        dene("markdown temizlenince cache tutar", sahte.sayac, 2)

        seslendir.seslendir("Merhaba.", ses="tr-TR-EmelNeural")
        dene("ses degisince yeniden uretti", sahte.sayac, 3)
        dene("istenen ses iletildi",
             sahte.cagrilar[-1]["ses"], "tr-TR-EmelNeural")

        dene("bos metin uretmez", seslendir.seslendir("   "), None)
        dene("bos metin aga gitmedi", sahte.sayac, 3)

        uzun = "cumle " * 500
        seslendir.seslendir(uzun)
        dene("uzun metin tavanda kirpildi",
             len(sahte.cagrilar[-1]["metin"]) <= seslendir.TAVAN, True)
    finally:
        seslendir._uret = asil
        shutil.rmtree(klasor, ignore_errors=True)


def hata_testleri():
    print("--- hata halinde sessizlik ---")
    klasor = temiz_klasor()
    asil = seslendir._uret
    seslendir._uret = SahteUretim(hata=RuntimeError("ag yok"))
    try:
        dene("uretim patlayinca None doner",
             seslendir.seslendir("Merhaba."), None)
        dene("yarim dosya birakilmadi", os.listdir(klasor), [])
    finally:
        seslendir._uret = asil
        shutil.rmtree(klasor, ignore_errors=True)


def yol_testleri():
    print("--- dosya yolu guvenligi ---")
    klasor = temiz_klasor()
    try:
        ad = "abc123def456abcd.mp3"
        open(os.path.join(klasor, ad), "wb").write(b"x")
        dene("gecerli ad bulunur",
             seslendir.dosya_yolu(ad), os.path.join(klasor, ad))
        dene("olmayan dosya None", seslendir.dosya_yolu("0000aaaa.mp3"), None)
        dene("ust klasor reddedilir",
             seslendir.dosya_yolu("../../secrets/.env"), None)
        dene("mp3 disi reddedilir", seslendir.dosya_yolu("abc123.txt"), None)
        dene("bos ad reddedilir", seslendir.dosya_yolu(""), None)
        dene("None reddedilir", seslendir.dosya_yolu(None), None)
    finally:
        shutil.rmtree(klasor, ignore_errors=True)


def main():
    metin_testleri()
    anahtar_testleri()
    uretim_testleri()
    hata_testleri()
    yol_testleri()
    gecen = sum(1 for s in sonuclar if s)
    print("\n%d/%d test gecti" % (gecen, len(sonuclar)))
    return 0 if gecen == len(sonuclar) else 1


if __name__ == "__main__":
    sys.exit(main())

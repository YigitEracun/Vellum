# -*- coding: utf-8 -*-
"""Demo veriyi tamamlar: state/raw/ekler/ altina ornek sozlesme PDF'i uretir.

gmail.json icinde ek adi olarak gecen sozlesme_rev3.pdf gercekte yoktu.
Gmail baglandiginda gmail_fetch.py ekleri ayni klasore indirecek; bu script
o klasorun sozlesmesini simdiden dolduruyor ki ek okuma akisi denenebilsin.

Bagimlilik yok - PDF elle, minimal yapiyla yaziliyor.
"""

import io
import os

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEDEF = os.path.join(KOK, "state", "raw", "ekler", "sozlesme_rev3.pdf")

SATIRLAR = [
    "TEDARIK SOZLESMESI - Revizyon 3",
    "",
    "Taraflar: Ornek Ltd. ile Tedarik Firma A.S.",
    "Duzenleme tarihi: 24 Agustos 2026",
    "",
    "MADDE 4 - BIRIM FIYAT (REVIZE EDILDI)",
    "Aylik siparis adedi 800 adet olarak guncellenmistir.",
    "800 adet ve uzeri siparislerde birim fiyat 325 TL olarak",
    "uygulanir. Onceki revizyondaki 340 TL bedeli gecersizdir.",
    "Fiyat, sozlesme suresince sabittir.",
    "",
    "MADDE 7 - TESLIM SURESI",
    "Siparis onayindan itibaren azami 6 hafta.",
    "",
    "MADDE 11 - CAYMA (HUKUKI INCELEMEDE DEGISTIRILDI)",
    "Taraflar 30 gun onceden yazili bildirimle sozlesmeyi",
    "feshedebilir.",
    "",
    "MADDE 14 - GIZLILIK (HUKUKI INCELEMEDE DEGISTIRILDI)",
    "Gizlilik yukumlulugu sozlesme bitiminden sonra 2 yil",
    "surer. Onceki metinde bu sure 5 yildi.",
    "",
    "MADDE 19 - GECIKME CEZASI (YENI EKLENDI)",
    "Teslimde her gecikme haftasi icin siparis bedelinin",
    "yuzde 2'si oraninda ceza uygulanir.",
    "",
    "Imza icin son tarih: 28 Agustos 2026, saat 17:00",
]


def kacir(s):
    return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def pdf_yaz(yol, satirlar):
    icerik = ["BT", "/F1 11 Tf", "14 TL", "56 780 Td"]
    for s in satirlar:
        icerik.append("(%s) Tj" % kacir(s))
        icerik.append("T*")
    icerik.append("ET")
    akis = "\n".join(icerik).encode("latin-1", "replace")

    nesneler = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(akis) + akis + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    govde = b"%PDF-1.4\n"
    ofsetler = []
    for i, n in enumerate(nesneler, start=1):
        ofsetler.append(len(govde))
        govde += b"%d 0 obj\n" % i + n + b"\nendobj\n"

    xref = len(govde)
    govde += b"xref\n0 %d\n" % (len(nesneler) + 1)
    govde += b"0000000000 65535 f \n"
    for o in ofsetler:
        govde += b"%010d 00000 n \n" % o
    govde += (b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
              % (len(nesneler) + 1, xref))

    os.makedirs(os.path.dirname(yol), exist_ok=True)
    io.open(yol, "wb").write(govde)


pdf_yaz(HEDEF, SATIRLAR)
print("yazildi:", os.path.relpath(HEDEF, KOK), os.path.getsize(HEDEF), "bayt")

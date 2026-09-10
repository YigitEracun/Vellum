# -*- coding: utf-8 -*-
"""Instagram çekicisinin birim testleri. API'ye gidilmez, yanıtlar taklit edilir.

Kullanım:  python scripts/test_instagram.py
"""

import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "panel"))
sys.path.insert(0, os.path.join(KOK, "scripts"))

import instagram_fetch as ig  # noqa: E402

sonuclar = []


def dene(ad, olan, beklenen):
    durum = "GECTI" if olan == beklenen else "KALDI"
    print("[%s] %-50s olan=%r" % (durum, ad, olan))
    sonuclar.append(durum == "GECTI")


BEN = "1784"

YANITLAR = {
    "/me": {"user_id": BEN, "username": "ornek_hesap"},
    "/me/conversations": {"data": [{"id": "c1"}, {"id": "c2"}]},
    "/c1": {"messages": {"data": [{"id": "m1"}, {"id": "m2"}]}},
    "/c2": {"messages": {"data": [{"id": "m3"}]}},
    # Sirasi bilerek ters: cekici kronolojik siralamali
    "/m1": {"id": "m1", "created_time": "2026-09-09T09:02:00+0000",
            "from": {"id": BEN, "username": "ornek_hesap"}, "message": "Dönüş yapacağım."},
    "/m2": {"id": "m2", "created_time": "2026-09-09T08:15:00+0000",
            "from": {"id": "999", "username": "marka"}, "message": "Bütçeniz nedir?"},
    "/m3": {"id": "m3", "created_time": "2026-09-08T20:00:00+0000",
            "from": {"id": "555", "username": "spam"}, "message": "TEBRİKLER " + "x" * 2500},
}


def sahte_cagir(url, parametreler=None):
    for yol, cevap in YANITLAR.items():
        if url.endswith(yol):
            return cevap
    raise AssertionError("beklenmeyen url: " + url)


def calistir():
    ig._cagir = sahte_cagir
    ig.token_oku = lambda: {"access_token": "sahte"}
    veri = ig.cek()

    # --- sema sozlesmesi (seed_ornek_veri.py ile ayni olmali)
    dene("ust alanlar", set(veri), {"cekildi", "hesap", "konusmalar"})
    k = veri["konusmalar"][0]
    dene("konusma alanlari", set(k), {"id", "kisi", "mesajlar"})
    dene("mesaj alanlari", set(k["mesajlar"][0]), {"yon", "t", "metin"})

    # --- icerik
    dene("hesap adi @ ile", veri["hesap"], "@ornek_hesap")
    dene("konusma sayisi", len(veri["konusmalar"]), 2)
    dene("kisi karsi taraftan alinir", k["kisi"], "@marka")
    dene("kendi mesajim 'giden'",
         [m["yon"] for m in k["mesajlar"]], ["gelen", "giden"])
    dene("kronolojik siralandi",
         k["mesajlar"][0]["t"] < k["mesajlar"][1]["t"], True)
    dene("zaman yerel saate cevrildi", k["mesajlar"][0]["t"][-6:], "+03:00")

    # --- kirpma: uzun metin modele oldugu gibi gitmemeli
    uzun = veri["konusmalar"][1]["mesajlar"][0]["metin"]
    dene("uzun metin kirpildi", len(uzun) <= ig.METIN_SINIR + 10, True)
    dene("kirpma isareti var", uzun.endswith("[…]"), True)

    # --- karsi taraf yoksa cokmemeli
    YANITLAR["/c2"] = {"messages": {"data": [{"id": "m4"}]}}
    YANITLAR["/m4"] = {"id": "m4", "created_time": "2026-09-08T20:00:00+0000",
                       "from": {"id": BEN, "username": "ornek_hesap"}, "message": "tek yonlu"}
    veri2 = ig.cek()
    dene("yalniz kendi mesajim varsa kisi bilinmeyen",
         veri2["konusmalar"][1]["kisi"], "@bilinmeyen")

    # --- bos konusma listesi
    YANITLAR["/me/conversations"] = {"data": []}
    dene("bos kutu cokmez", len(ig.cek()["konusmalar"]), 0)

    print("\n%d/%d gecti" % (sum(sonuclar), len(sonuclar)))
    return all(sonuclar)


if __name__ == "__main__":
    sys.exit(0 if calistir() else 1)

# -*- coding: utf-8 -*-
"""Sahte veriyle state/ ve projects/ klasörlerini doldurur.

Gerçek hesap bağlantısı kurulmadan önce akışı uçtan uca denemek için.
Faz 1'de gmail_fetch.py devreye girince state/raw/gmail.json bu scriptin
ürettiği formatta gelecek — şema sözleşmesi burada tanımlı sayılır.

Kullanım:  python scripts/seed_ornek_veri.py
"""

import io
import json
import os
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=3))
# Demo verisi her zaman "bugüne" göre üretilir; sabit bir tarihe bağlanırsa
# ajanda geçmişte kalır ve panel boş görünür.
SIMDI = datetime.now(TZ).replace(hour=8, minute=0, second=0, microsecond=0)
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def iso(dt):
    return dt.isoformat()


def gun(n):
    """n gün önce."""
    return SIMDI - timedelta(days=n)


def yaz(yol, veri):
    tam = os.path.join(KOK, yol)
    os.makedirs(os.path.dirname(tam), exist_ok=True)
    if isinstance(veri, str):
        io.open(tam, "w", encoding="utf-8").write(veri)
    else:
        io.open(tam, "w", encoding="utf-8").write(
            json.dumps(veri, ensure_ascii=False, indent=2)
        )
    print("  " + yol)


def jsonl(yol, satirlar):
    tam = os.path.join(KOK, yol)
    os.makedirs(os.path.dirname(tam), exist_ok=True)
    with io.open(tam, "w", encoding="utf-8") as f:
        for s in satirlar:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print("  " + yol + "  (" + str(len(satirlar)) + " olay)")


def aktivite_12h(olaylar):
    """Son 12 haftanın haftalık olay sayısı, eskiden yeniye."""
    kova = [0] * 12
    for o in olaylar:
        if o.get("onaylanmamis"):
            continue
        t = datetime.fromisoformat(o["t"])
        hafta = int((SIMDI - t).total_seconds() // (7 * 86400))
        if 0 <= hafta < 12:
            kova[11 - hafta] += 1
    return kova


# ---------------------------------------------------------------- ham veri

print("state/raw/")

yaz("state/raw/gmail.json", {
    "cekildi": iso(SIMDI),
    "hesap": "ornek@gmail.com",
    "toplam_okunmamis": 61,
    "mailler": [
        {
            "id": "18f2a",
            "gonderen": "Ayşe Yılmaz <ayse@tedarikfirma.com>",
            "alici": ["ben@ornek.com"],
            "cc": [],
            "konu": "Sözleşme revizyonu — imza bekliyor",
            "tarih": iso(gun(0) - timedelta(hours=2)),
            "thread_id": "t_9001",
            "govde": "Merhaba, revize sözleşmeyi ekte gönderiyorum. Fiyat maddesinde "
                     "değişiklik yaptık. Cuma 17:00'a kadar imzalı halini geri "
                     "gönderebilir misiniz? Teşekkürler.",
            "ekler": ["sozlesme_rev3.pdf"],
        },
        {
            "id": "18f2b",
            "gonderen": "Mert Kaya <mert@tasarimstudyo.com>",
            "alici": ["ben@ornek.com"],
            "cc": ["ekip@tasarimstudyo.com"],
            "konu": "Site tasarımı — geri bildirim bekliyoruz",
            "tarih": iso(gun(12)),
            "thread_id": "t_9002",
            "govde": "İkinci tur tasarımları paylaşmıştık, geri bildiriminizi "
                     "bekliyoruz. Süreç bizde durdu.",
            "ekler": [],
        },
        {
            "id": "18f2c",
            "gonderen": "Muhasebe <muhasebe@ornek.com>",
            "alici": ["ben@ornek.com"],
            "cc": [],
            "konu": "Ağustos faturaları",
            "tarih": iso(gun(1)),
            "thread_id": "t_9003",
            "govde": "Ağustos ayı faturaları hazır, ay sonuna kadar onaylamanız gerekiyor.",
            "ekler": ["agustos_faturalar.xlsx"],
        },
        {
            "id": "18f2d",
            "gonderen": "Teknoloji Bülteni <bulten@haberler.com>",
            "alici": ["ben@ornek.com"],
            "cc": [],
            "konu": "Bu haftanın öne çıkanları",
            "tarih": iso(gun(0) - timedelta(hours=5)),
            "thread_id": "t_9004",
            "govde": "Haftanın teknoloji haberleri...",
            "ekler": [],
        },
    ],
})

yaz("state/raw/instagram.json", {
    "cekildi": iso(SIMDI),
    "hesap": "@ornek_hesap",
    "konusmalar": [
        {
            "id": "9931",
            "kisi": "@marka_isbirligi",
            "mesajlar": [
                {"yon": "gelen", "t": iso(gun(0) - timedelta(hours=15)),
                 "metin": "Merhaba! Ürünümüz için işbirliği yapmak istiyoruz, "
                          "bütçe aralığınızı öğrenebilir miyiz?"}
            ],
        },
        {
            "id": "9932",
            "kisi": "@takipci_hesap",
            "mesajlar": [
                {"yon": "gelen", "t": iso(gun(2)),
                 "metin": "Paylaştığınız içerik çok faydalıydı, teşekkürler!"}
            ],
        },
        {
            "id": "9933",
            "kisi": "@kazan_hemen_2026",
            "mesajlar": [
                {"yon": "gelen", "t": iso(gun(1)),
                 "metin": "TEBRİKLER! Hesabınız seçildi, linke tıklayın..."}
            ],
        },
    ],
})

yaz("state/raw/calendar.json", {
    "cekildi": iso(SIMDI),
    "etkinlikler": [
        {
            "id": "evt_5501",
            "baslik": "Tedarikçi görüşmesi",
            "baslangic": iso(SIMDI + timedelta(days=1, hours=6)),
            "bitis": iso(SIMDI + timedelta(days=1, hours=7)),
            "yer": "Google Meet",
            "katilimcilar": ["ayse@tedarikfirma.com", "ben@ornek.com"],
            "aciklama": "Q4 fiyat listesi ve teslim süreleri",
        },
        {
            "id": "evt_5502",
            "baslik": "Diş hekimi",
            "baslangic": iso(SIMDI + timedelta(days=4, hours=2)),
            "bitis": iso(SIMDI + timedelta(days=4, hours=3)),
            "yer": "Kadıköy",
            "katilimcilar": [],
            "aciklama": "",
        },
    ],
})

# ------------------------------------------------------- proje: tedarikçi

print("projects/tedarikci-anlasmasi/")

tedarik = [
    {"t": iso(gun(42)), "tip": "not", "baslik": "Proje açıldı",
     "detay": "Yeni tedarikçi arayışı başladı", "kaynak": None,
     "etiket": [], "kilometre_tasi": False, "onaylanmamis": False},
    {"t": iso(gun(40)), "tip": "toplanti", "baslik": "İlk tanışma görüşmesi",
     "detay": "Üç firmayla ön görüşme yapıldı", "kaynak": "takvim:evt_4401",
     "etiket": [], "kilometre_tasi": False, "onaylanmamis": False},
    {"t": iso(gun(38)), "tip": "karar_alindi", "baslik": "İki firmayla devam kararı",
     "detay": "Üçüncü firma teslim süresi nedeniyle elendi", "kaynak": None,
     "etiket": ["lojistik"], "kilometre_tasi": True, "onaylanmamis": False},
    {"t": iso(gun(35)), "tip": "adim_tamamlandi", "baslik": "Teklif talebi gönderildi",
     "detay": "İki firmaya da aynı şartname iletildi", "kaynak": "mail:17a01",
     "etiket": ["fiyat"], "kilometre_tasi": False, "onaylanmamis": False},
    {"t": iso(gun(30)), "tip": "adim_tamamlandi", "baslik": "İlk teklif alındı",
     "detay": "Birim fiyat 340 TL, 8 hafta teslim", "kaynak": "mail:17a08",
     "etiket": ["fiyat"], "kilometre_tasi": False, "onaylanmamis": False},
    {"t": iso(gun(28)), "tip": "risk", "baslik": "Teslim süresi uzun",
     "detay": "8 hafta planlanandan 2 hafta fazla", "kaynak": None,
     "etiket": ["lojistik"], "kilometre_tasi": False, "onaylanmamis": False},
    {"t": iso(gun(24)), "tip": "toplanti", "baslik": "Ara değerlendirme",
     "detay": "Teslim süresi 6 haftaya çekildi", "kaynak": "takvim:evt_4712",
     "etiket": ["lojistik"], "kilometre_tasi": False, "onaylanmamis": False},
    {"t": iso(gun(21)), "tip": "kapsam_degisti", "baslik": "Sipariş adedi artırıldı",
     "detay": "Aylık 500 yerine 800 adet", "kaynak": None,
     "etiket": ["fiyat"], "kilometre_tasi": False, "onaylanmamis": False},
    {"t": iso(gun(18)), "tip": "not", "baslik": "Hukuki inceleme başladı",
     "detay": "Sözleşme taslağı avukata iletildi", "kaynak": "mail:17c22",
     "etiket": ["hukuk"], "kilometre_tasi": False, "onaylanmamis": False},
    {"t": iso(gun(14)), "tip": "adim_tamamlandi", "baslik": "Hukuki inceleme tamamlandı",
     "detay": "İki maddede değişiklik istendi", "kaynak": "mail:17d05",
     "etiket": ["hukuk"], "kilometre_tasi": False, "onaylanmamis": False},
    {"t": iso(gun(5)), "tip": "blokaj", "baslik": "Tedarikçi fiyat vermedi",
     "detay": "Üçüncü hatırlatmaya rağmen dönüş yok", "kaynak": "mail:18a91",
     "etiket": ["fiyat"], "kilometre_tasi": False, "onaylanmamis": False,
     "etki": "yuksek"},
    {"t": iso(gun(1) + timedelta(hours=1)), "tip": "blokaj_cozuldu",
     "baslik": "Alternatif tedarikçiye geçildi",
     "detay": "İkinci firmayla görüşüldü, revize teklif geldi", "kaynak": "ig:9931",
     "etiket": ["fiyat"], "kilometre_tasi": True, "onaylanmamis": False,
     "ref": iso(gun(5))},
    {"t": iso(gun(0) - timedelta(hours=2)), "tip": "tarih_kaydi",
     "baslik": "Sözleşme imzası için son tarih: cuma 17:00",
     "detay": "Ayşe'nin mailinden çıkarıldı", "kaynak": "mail:18f2a",
     "etiket": ["hukuk"], "kilometre_tasi": False, "onaylanmamis": True},
]

jsonl("projects/tedarikci-anlasmasi/olaylar.jsonl", tedarik)

yaz("projects/tedarikci-anlasmasi/proje.md", """# Tedarikçi anlaşması

**Amaç:** Mevcut tedarikçinin yerine daha kısa teslim süresi ve daha iyi birim fiyat
sunan bir firma ile anlaşmak.

**Başarı kriteri:** Birim fiyat 320 TL altında, teslim süresi 6 haftayı geçmeyecek,
sözleşme eylül başında imzalanmış olacak.

**Muhataplar:**
- Ayşe Yılmaz — tedarikfirma.com, ticari muhatap
- Av. Selim D. — sözleşme incelemesi

**Notlar:** Aylık adet 500'den 800'e çıktığı için fiyat yeniden pazarlığa açıldı.
""")

yaz("projects/tedarikci-anlasmasi/kararlar/001-ucuncu-firma-elendi.md", """# Üçüncü firma neden elendi

**Tarih:** 42 gün önce
**Karar:** Üç aday firmadan biri liste dışı bırakıldı.

**Gerekçe:** Teslim süresi 11 hafta olarak bildirildi. Diğer iki firma 8 hafta
veriyordu ve bizim hedefimiz 6 haftaydı. Fiyatı en düşük teklifti ama teslim
süresi telafi edilemez bulundu.

**Tekrar değerlendirilirse:** Yalnızca diğer iki firma da elenirse gündeme gelir.
""")

yaz("projects/tedarikci-anlasmasi/durum.json", {
    "ozet": "İlk tedarikçi üç hatırlatmaya rağmen fiyat vermedi, alternatif firmaya "
            "geçildi. Şu an revize teklifin karşılaştırılması ve sözleşme imzası bekleniyor.",
    "ozet_guncelleme": iso(SIMDI),
    "sonraki_adim": "İki firmanın revize fiyat listelerini karşılaştır",
    "acik_blokajlar": 0,
    "son_hareket": iso(gun(1) + timedelta(hours=1)),
    "acik_gun": 42,
    "olay_sayisi": len([o for o in tedarik if not o.get("onaylanmamis")]),
    "etiketler": ["fiyat", "hukuk", "lojistik"],
    "aktivite_12h": aktivite_12h(tedarik),
})

# ------------------------------------------------------------ proje: site

print("projects/web-sitesi-yenileme/")

site = [
    {"t": iso(gun(75)), "tip": "not", "baslik": "Proje açıldı",
     "detay": "Mevcut site 4 yaşında, mobilde kötü çalışıyor", "kaynak": None,
     "etiket": [], "kilometre_tasi": False, "onaylanmamis": False},
    {"t": iso(gun(70)), "tip": "karar_alindi", "baslik": "Ajans yerine stüdyo seçildi",
     "detay": "Bütçe farkı üç kat, iş kapsamı benzer", "kaynak": None,
     "etiket": ["butce"], "kilometre_tasi": True, "onaylanmamis": False},
    {"t": iso(gun(62)), "tip": "toplanti", "baslik": "Kickoff",
     "detay": "İçerik yapısı ve sayfa listesi belirlendi", "kaynak": "takvim:evt_3301",
     "etiket": [], "kilometre_tasi": False, "onaylanmamis": False},
    {"t": iso(gun(48)), "tip": "adim_tamamlandi", "baslik": "İlk tur tasarım geldi",
     "detay": "Ana sayfa ve iki iç sayfa", "kaynak": "mail:16b40",
     "etiket": ["tasarim"], "kilometre_tasi": False, "onaylanmamis": False},
    {"t": iso(gun(40)), "tip": "adim_tamamlandi", "baslik": "İkinci tur tasarım geldi",
     "detay": "Geri bildirimler uygulandı", "kaynak": "mail:16c11",
     "etiket": ["tasarim"], "kilometre_tasi": False, "onaylanmamis": False},
    {"t": iso(gun(12)), "tip": "blokaj", "baslik": "Geri bildirim verilmedi",
     "detay": "Stüdyo ikinci tur için dönüş bekliyor, süreç durdu",
     "kaynak": "mail:18f2b", "etiket": ["tasarim"], "kilometre_tasi": False,
     "onaylanmamis": False, "etki": "orta"},
]

jsonl("projects/web-sitesi-yenileme/olaylar.jsonl", site)

yaz("projects/web-sitesi-yenileme/proje.md", """# Web sitesi yenileme

**Amaç:** Mobil uyumlu, içerik yönetimi kolay yeni bir site.

**Başarı kriteri:** Mobil performans skoru 90 üzeri, içerik güncellemesi
geliştirici gerektirmeden yapılabiliyor.

**Muhataplar:**
- Mert Kaya — tasarimstudyo.com

**Notlar:** Ajans yerine stüdyo tercih edildi, bütçe farkı üç kattı.
""")

yaz("projects/web-sitesi-yenileme/durum.json", {
    "ozet": "İkinci tur tasarımlar 40 gün önce teslim edildi ama geri bildirim "
            "verilmediği için süreç 12 gündür durmuş durumda. Top bizde.",
    "ozet_guncelleme": iso(SIMDI),
    "sonraki_adim": "İkinci tur tasarımlara geri bildirim yaz",
    "acik_blokajlar": 1,
    "son_hareket": iso(gun(12)),
    "acik_gun": 75,
    "olay_sayisi": len(site),
    "etiketler": ["tasarim", "butce"],
    "aktivite_12h": aktivite_12h(site),
})

yaz("projects/_oneriler.json", {
    "guncelleme": iso(SIMDI),
    "oneriler": [{
        "onerilen_ad": "marka-isbirligi",
        "gerekce": "Instagram'dan gelen işbirliği teklifi mevcut projelerin hiçbirine "
                   "oturmuyor",
        "kaynak": "ig:9931",
    }],
})

print()
print("Tamam. Şimdi Claude Code içinde /brief çalıştırıp agent'ların bu ham veriden")
print("digest üretmesini izleyebilirsin.")

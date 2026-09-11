# -*- coding: utf-8 -*-
"""Asistan paneli — yerel sunucu.

Sunucunun kendisi yalnızca standart kütüphaneye dayanır. Sohbet ve tarama
Claude API üzerinden çalışır; onlar için:

    pip install anthropic
    API anahtarı: ANTHROPIC_API_KEY veya secrets/api_key.txt

Çalıştırmak için:

    python panel/sunucu.py

Sonra tarayıcıda:  http://127.0.0.1:8787

Yalnızca 127.0.0.1'e bind edilir; dışarıdan erişilemez.
"""

import io
import json
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = os.path.dirname(os.path.abspath(__file__))
for _yol in (PANEL, os.path.join(KOK, "scripts")):
    if _yol not in sys.path:
        sys.path.insert(0, _yol)
PORT = 8787
TZ = timezone(timedelta(hours=3))

# Gerçek gönderim kapalıyken onaylar yalnızca kaydedilir, hiçbir yere mail/DM gitmez.
# Faz 1 (Gmail) tamamlanana kadar False kalmalı.
CANLI_GONDERIM = False


# --------------------------------------------------------------- yardımcılar

def oku_json(yol, varsayilan=None):
    tam = os.path.join(KOK, yol)
    if not os.path.exists(tam):
        return varsayilan
    try:
        return json.load(io.open(tam, encoding="utf-8"))
    except ValueError:
        return varsayilan


def oku_jsonl(yol):
    tam = os.path.join(KOK, yol)
    if not os.path.exists(tam):
        return []
    satirlar = []
    for satir in io.open(tam, encoding="utf-8"):
        satir = satir.strip()
        if satir:
            satirlar.append(json.loads(satir))
    return satirlar


def yaz_json(yol, veri):
    tam = os.path.join(KOK, yol)
    os.makedirs(os.path.dirname(tam), exist_ok=True)
    io.open(tam, "w", encoding="utf-8").write(
        json.dumps(veri, ensure_ascii=False, indent=2)
    )


def ekle_jsonl(yol, kayit):
    """Append-only. Var olan satırlara asla dokunmaz."""
    tam = os.path.join(KOK, yol)
    with io.open(tam, "a", encoding="utf-8") as f:
        f.write(json.dumps(kayit, ensure_ascii=False) + "\n")


# ------------------------------------------------------------ durum türetme

def turet_durum(proje, mevcut):
    """olaylar.jsonl'dan durum.json'un mekanik alanlarını yeniden hesaplar.

    `ozet` alanı LLM tarafından yazılır, burada dokunulmaz — yalnızca
    `ozet_bayat` bayrağı kaldırılır/konur ki panel özetin güncellenmesi
    gerektiğini gösterebilsin.
    """
    olaylar = [o for o in oku_jsonl("projects/%s/olaylar.jsonl" % proje)
               if not o.get("onaylanmamis")]
    simdi = datetime.now(TZ)

    acik_blokajlar = 0
    cozulen_ref = set()
    for o in olaylar:
        if o.get("tip") == "blokaj_cozuldu" and o.get("ref"):
            cozulen_ref.add(o["ref"])
    for o in olaylar:
        if o.get("tip") == "blokaj" and o["t"] not in cozulen_ref:
            acik_blokajlar += 1

    etiketler = []
    for o in olaylar:
        for e in o.get("etiket") or []:
            if e not in etiketler:
                etiketler.append(e)

    kova = [0] * 12
    for o in olaylar:
        hafta = int((simdi - datetime.fromisoformat(o["t"])).total_seconds() // (7 * 86400))
        if 0 <= hafta < 12:
            kova[11 - hafta] += 1

    d = dict(mevcut or {})
    if olaylar:
        # Dosya append-only oldugu icin satir sirasi kronolojik olmayabilir.
        zamanlar = [datetime.fromisoformat(o["t"]) for o in olaylar]
        ilk, son = min(zamanlar), max(zamanlar)
        d["son_hareket"] = son.isoformat()
        d["acik_gun"] = (simdi - ilk).days
    d["acik_blokajlar"] = acik_blokajlar
    d["olay_sayisi"] = len(olaylar)
    d["etiketler"] = etiketler
    d["aktivite_12h"] = kova
    return d


# ------------------------------------------------------------------ toplama

def toplu_durum():
    projeler = []
    kok_p = os.path.join(KOK, "projects")
    if os.path.isdir(kok_p):
        for ad in sorted(os.listdir(kok_p)):
            if ad.startswith("_") or not os.path.isdir(os.path.join(kok_p, ad)):
                continue
            durum = oku_json("projects/%s/durum.json" % ad, {}) or {}
            olaylar = oku_jsonl("projects/%s/olaylar.jsonl" % ad)
            olaylar.sort(key=lambda o: o["t"], reverse=True)
            projeler.append({
                "ad": ad,
                "durum": durum,
                "olaylar": olaylar,
                "bekleyen_olay": len([o for o in olaylar if o.get("onaylanmamis")]),
            })

    log_dizin = os.path.join(KOK, "state", "log")
    arsiv = sorted(os.listdir(log_dizin), reverse=True) if os.path.isdir(log_dizin) else []

    # Brifing artık konuşmanın ilk mesajı; varsa bugünkü kaydı da gönder.
    bugun_ad = datetime.now(TZ).strftime("%Y-%m-%d") + ".md"
    bugun_yol = os.path.join(log_dizin, bugun_ad)
    bugunun_brifingi = brifing_zamani = None
    if os.path.exists(bugun_yol):
        bugunun_brifingi = io.open(bugun_yol, encoding="utf-8").read()
        # Dosyanin yazilma ani = brifingin uretildigi an. Damgasiz gosterilirse
        # sabahtan kalma bir brifing yeni taramanin ciktisi sanilir.
        brifing_zamani = datetime.fromtimestamp(
            os.path.getmtime(bugun_yol), TZ).isoformat()

    return {
        "simdi": datetime.now(TZ).isoformat(),
        "canli_gonderim": CANLI_GONDERIM,
        # Ham verinin ne zaman cekildigi: panel "bu brifing ne kadar taze"
        # sorusunu cevaplayabilsin.
        "ham_cekildi": (oku_json("state/raw/gmail.json", {}) or {}).get("cekildi"),
        "bugunun_brifingi": bugunun_brifingi,
        "brifing_zamani": brifing_zamani,
        "tarama": tarama_durumu(),
        "bildirimler": bildirimleri_oku(),
        "sohbet": sohbet_gecmisi(),
        "takvim": takvim_penceresi(),
        "konular": konular_durumu(),
        "mail": oku_json("state/inbox-digest.json", {}),
        "sosyal": oku_json("state/social-queue.json", {}),
        "projeler": projeler,
        "oneriler": oku_json("projects/_oneriler.json", {"oneriler": []}),
        "arsiv": arsiv[:30],
    }


def taslak_oku(taslak_id):
    for uzanti in ("md",):
        yol = os.path.join(KOK, "state", "taslaklar", "%s.%s" % (taslak_id, uzanti))
        if os.path.exists(yol):
            return io.open(yol, encoding="utf-8").read()
    return None


# ------------------------------------------------------------------ eylemler

def olay_karari(govde):
    """Onaylanmamış bir olayı onaylar veya reddeder.

    Onay:  olaya düzeltme satırı EKLENİR (onaylanmis_ref), özgün satır durur.
    Red:   yoksayma satırı eklenir. Hiçbir satır silinmez.
    """
    proje = govde["proje"]
    t = govde["t"]
    karar = govde["karar"]
    yol = "projects/%s/olaylar.jsonl" % proje

    olaylar = oku_jsonl(yol)
    hedef = next((o for o in olaylar if o["t"] == t and o.get("onaylanmamis")), None)
    if hedef is None:
        return {"hata": "Onay bekleyen böyle bir olay yok."}

    # Append-only kural: özgün satır korunur, kararı ayrı satır olarak yazılır.
    ekle_jsonl(yol, {
        "t": datetime.now(TZ).isoformat(),
        "tip": "not",
        "baslik": ("Olay onaylandı: " if karar == "onayla" else "Olay yoksayıldı: ")
                  + hedef.get("baslik", ""),
        "detay": "Panelden karar verildi",
        "kaynak": "panel",
        "etiket": [],
        "kilometre_tasi": False,
        "onaylanmamis": False,
        "ref": t,
        "karar": karar,
    })

    # Onaylandıysa olayın kendisi de geçerli sayılan bir satır olarak eklenir.
    if karar == "onayla":
        onayli = dict(hedef)
        onayli["onaylanmamis"] = False
        onayli["onay_zamani"] = datetime.now(TZ).isoformat()
        ekle_jsonl(yol, onayli)

    durum = turet_durum(proje, oku_json("projects/%s/durum.json" % proje, {}))
    durum["ozet_bayat"] = True
    yaz_json("projects/%s/durum.json" % proje, durum)
    return {"tamam": True, "durum": durum}


def taslak_onayi(govde):
    """Taslağı onaylar. CANLI_GONDERIM kapalıyken hiçbir yere gönderilmez."""
    taslak_id = govde["id"]
    metin = taslak_oku(taslak_id)
    if metin is None:
        return {"hata": "Taslak bulunamadı: " + taslak_id}

    if CANLI_GONDERIM:
        return {"hata": "Canlı gönderim henüz bağlanmadı (Faz 1 bekliyor)."}

    yol = os.path.join(KOK, "state", "taslaklar", "%s.md" % taslak_id)
    yeni = metin.replace("durum: onay_bekliyor", "durum: onaylandi_gonderilmedi", 1)
    yeni += ("\n<!-- %s tarihinde panelden onaylandı. Gerçek gönderim Faz 1'de "
             "Gmail bağlandığında yapılacak. -->\n" % datetime.now(TZ).isoformat())
    io.open(yol, "w", encoding="utf-8").write(yeni)

    return {
        "tamam": True,
        "gonderildi": False,
        "mesaj": "Onaylandı ve kaydedildi. Gerçek gönderim için Gmail bağlantısı gerekiyor.",
    }


def konular_durumu():
    """Konular sayfasının verisi: ortak sözlük + kullanıcının kendi konuları.

    Her gövdenin son taramada kaç maile dokunduğu da hesaplanır — kullanıcı
    eklediği kelimenin işe yarayıp yaramadığını görebilmeli.
    """
    try:
        import skorlama
    except Exception:
        return {"ortak": [], "kendi": [], "kapali": []}

    maddeler = (oku_json("state/inbox-digest.json", {}) or {}).get("maddeler", [])
    ham = {str(m.get("id")): m for m in
           (oku_json("state/raw/gmail.json", {}) or {}).get("mailler", [])}

    def dokunma(govde):
        kalip = skorlama.kalip_kur([govde])
        if not kalip:
            return 0
        sayi = 0
        for m in maddeler:
            h = ham.get(str(m.get("id")), {})
            metin = (m.get("konu") or "") + "\n" + (h.get("govde") or "")
            if kalip.search(metin):
                sayi += 1
        return sayi

    yerel = skorlama.kullanici_konulari()
    kapali = [str(a).lower() for a in (yerel.get("kapali") or [])]

    ortak = []
    for ad, k in sorted(skorlama.ortak_sozluk().items()):
        ortak.append({
            "kategori": ad, "agirlik": k["agirlik"],
            "govde_sayisi": len(k["govdeler"]),
            "ornekler": k["govdeler"][:6],
            "kapali": ad in kapali,
        })

    kendi = []
    for konu in yerel.get("konular") or []:
        if isinstance(konu, dict) and konu.get("kelime"):
            kendi.append({
                "kelime": konu["kelime"],
                "agirlik": konu.get("agirlik", 30),
                "kategori": konu.get("kategori") or "kendi-konularim",
                "dokundu": dokunma(konu["kelime"]),
            })
    vip, gurultu = skorlama.kisi_listeleri()
    yazistiklarim = skorlama.yazistiklarim()
    return {"ortak": ortak, "kendi": kendi, "kapali": kapali,
            "vip": vip, "gurultu": gurultu,
            "yazistiklarim": len(yazistiklarim)}


def konu_ekle(govde):
    import skorlama
    kelime = (govde.get("kelime") or "").strip()
    if not kelime:
        return {"hata": "Kelime boş olamaz."}
    if len(kelime) < 3:
        return {"hata": "Çok kısa kelimeler alakasız maillere yapışır; en az 3 harf."}
    try:
        agirlik = int(govde.get("agirlik", 30))
    except (TypeError, ValueError):
        return {"hata": "Ağırlık bir sayı olmalı."}
    agirlik = max(-50, min(50, agirlik))

    yerel = skorlama.kullanici_konulari()
    konular = list(yerel.get("konular") or [])
    if any(k.get("kelime", "").lower() == kelime.lower() for k in konular
           if isinstance(k, dict)):
        return {"hata": "Bu kelime zaten var."}
    konular.append({"kelime": kelime, "agirlik": agirlik,
                    "kategori": (govde.get("kategori") or "kendi-konularim")})
    yerel["konular"] = konular
    yaz_json("state/konular.json", yerel)
    return {"tamam": True}


def konu_sil(govde):
    import skorlama
    kelime = (govde.get("kelime") or "").strip().lower()
    yerel = skorlama.kullanici_konulari()
    kalan = [k for k in (yerel.get("konular") or [])
             if not (isinstance(k, dict) and k.get("kelime", "").lower() == kelime)]
    yerel["konular"] = kalan
    yaz_json("state/konular.json", yerel)
    return {"tamam": True}


def kisi_ekle(govde):
    """VIP ya da gürültü listesine adres ekler. Kişisel veri; yerelde durur."""
    import skorlama
    adres = (govde.get("adres") or "").strip().lower()
    liste = "gurultu" if govde.get("liste") == "gurultu" else "vip"
    if "@" not in adres or "." not in adres.split("@")[-1]:
        return {"hata": "Geçerli bir mail adresi girin."}
    yerel = skorlama.kullanici_konulari()
    mevcut = [str(a).lower() for a in (yerel.get(liste) or [])]
    if adres in mevcut:
        return {"hata": "Bu adres zaten listede."}
    # Aynı adres iki listede birden olmasın.
    diger = "gurultu" if liste == "vip" else "vip"
    yerel[diger] = [a for a in (yerel.get(diger) or [])
                    if str(a).lower() != adres]
    yerel[liste] = mevcut + [adres]
    yaz_json("state/konular.json", yerel)
    return {"tamam": True}


def kisi_sil(govde):
    import skorlama
    adres = (govde.get("adres") or "").strip().lower()
    yerel = skorlama.kullanici_konulari()
    for liste in ("vip", "gurultu"):
        yerel[liste] = [a for a in (yerel.get(liste) or [])
                        if str(a).lower() != adres]
    yaz_json("state/konular.json", yerel)
    return {"tamam": True}


def kategori_degistir(govde):
    """Ortak sözlükteki bir kategoriyi açar/kapatır. Ortak dosya değişmez."""
    import skorlama
    ad = (govde.get("kategori") or "").strip().lower()
    if not ad:
        return {"hata": "Kategori adı yok."}
    yerel = skorlama.kullanici_konulari()
    kapali = [str(a).lower() for a in (yerel.get("kapali") or [])]
    if govde.get("kapat"):
        if ad not in kapali:
            kapali.append(ad)
    else:
        kapali = [a for a in kapali if a != ad]
    yerel["kapali"] = kapali
    yaz_json("state/konular.json", yerel)
    return {"tamam": True}


def takvim_penceresi():
    """Panelin ay degistirebilmesi icin yeterli araliktaki etkinlikler."""
    try:
        import takvim
        return takvim.pencere()
    except Exception:
        return []


def etkinlik_ekle(govde):
    """Panelden elle etkinlik ekler."""
    import takvim
    try:
        kayit = takvim.ekle(
            baslik=govde.get("baslik"),
            baslangic=govde.get("baslangic"),
            saatli=govde.get("saatli", True),
            yer=govde.get("yer"),
            tur=govde.get("tur") or "diger",
            kaynak="elle",
        )
    except ValueError as hata:
        return {"hata": str(hata)}
    return {"tamam": True, "etkinlik": kayit}


def etkinlik_iptal(govde):
    """Etkinliği takvimden kaldırır. Özgün satır durur, iptal satırı eklenir."""
    import takvim
    kimlik = (govde.get("id") or "").strip()
    if not kimlik:
        return {"hata": "Etkinlik kimliği yok."}
    if not takvim.iptal_et(kimlik):
        return {"hata": "Böyle bir etkinlik yok."}
    return {"tamam": True}


def mail_oku(mail_id):
    """Bir mailin tam gövdesini döner.

    Once son cekilen pencereye, orada yoksa kalici arsive bakar — pencereden
    dusmus eski bir mail de okunabilsin.
    """
    mail_id = str(mail_id)
    ham = oku_json("state/raw/gmail.json", {}) or {}
    for m in ham.get("mailler", []):
        if str(m.get("id")) == mail_id:
            return {"mail": m}
    for m in oku_jsonl("state/raw/arsiv.jsonl"):
        if str(m.get("id")) == mail_id:
            return {"mail": m}
    return {"hata": "Bu mail elde yok. Ham veri tazelendiğinde düşmüş olabilir."}


def bildirimleri_oku(yalniz_gorulmemis=True):
    """Canlı izleyicinin düştüğü bildirimleri okur."""
    yol = os.path.join(KOK, "state", "bildirimler.jsonl")
    if not os.path.exists(yol):
        return []
    kayitlar = []
    for satir in io.open(yol, encoding="utf-8", errors="replace"):
        satir = satir.strip()
        if not satir:
            continue
        try:
            k = json.loads(satir)
        except ValueError:
            continue
        if yalniz_gorulmemis and k.get("goruldu"):
            continue
        kayitlar.append(k)
    kayitlar.sort(key=lambda k: -(k.get("ham_skor") or 0))
    return kayitlar[:20]


def izleyici_baslat():
    """Canlı izleyiciyi arka planda çalıştırır. Panel kapanınca izleme de durur."""
    def dongu():
        try:
            sys.path.insert(0, os.path.join(KOK, "scripts"))
            import izleyici
        except Exception as hata:
            print("Izleyici baslatilamadi:", hata)
            return
        print("Izleyici acik: her %d sn, esik %d" % (izleyici.ARALIK, izleyici.ESIK))
        while True:
            try:
                # IMAP'e aynı anda iki yerden gitmeyelim: tarama sürerken bekle.
                if _TARAMA_KILIDI.acquire(blocking=False):
                    try:
                        sayi, bildirilen = izleyici.tur()
                    finally:
                        _TARAMA_KILIDI.release()
                    if bildirilen:
                        print("Izleyici: %d onemli mail" % len(bildirilen))
            except Exception as hata:
                print("Izleyici turu hatasi (devam ediyor):", hata)
            time.sleep(izleyici.ARALIK)

    t = threading.Thread(target=dongu, daemon=True)
    t.start()
    return t


def anlasilir_hata(hata):
    """API hatalarını düz Türkçeye çevirir.

    Ham `BadRequestError` metni kullanıcıya bir şey anlatmıyor; kredi bitmesini
    bulmak bu yüzden yarım saat aldı.
    """
    metin = str(hata)
    d = metin.lower()
    if "credit balance is too low" in d:
        return ("API krediniz bitmiş, tarama yapılamıyor. "
                "console.anthropic.com → Plans & Billing'den kredi yükleyin.")
    if "authentication" in d or "invalid x-api-key" in d or "401" in d:
        return "API anahtarı geçersiz. .env dosyasındaki ANTHROPIC_API_KEY'i kontrol edin."
    if "rate limit" in d or "429" in d:
        return "API hız sınırına takıldık. Birkaç dakika sonra tekrar deneyin."
    if any(x in d for x in ("connection", "timeout", "getaddrinfo", "ssl")):
        return "Ağ bağlantısı kurulamadı. İnternet bağlantınızı kontrol edin."
    if "cikti siniri" in d:
        return metin   # zaten Türkçe ve açıklayıcı
    return "%s: %s" % (type(hata).__name__, metin)


def tarama_kaydet(kayit):
    """Her taramanın sonucunu — hata dahil — kalıcı olarak kaydeder."""
    yol = os.path.join(KOK, "state", "log", "taramalar.jsonl")
    try:
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        with io.open(yol, "a", encoding="utf-8") as f:
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
    except Exception:
        pass   # kayıt tutulamadı diye tarama bozulmasın


def _beyin():
    """beyin modulunu gec yukler; anthropic kurulu degilse anlasilir hata verir."""
    try:
        import beyin
        return beyin
    except ImportError as hata:
        raise RuntimeError(
            "Anthropic SDK kurulu degil. Kurmak icin: pip install anthropic (%s)" % hata
        )


SOHBET_DOSYASI = "state/sohbet.jsonl"
SOHBET_GOSTERILEN = 40   # panele taşınan son tur sayısı


def sohbet_gecmisi():
    """Kayıtlı sohbetin son turlarını döner. Dosya append-only büyür."""
    turlar = []
    for k in oku_jsonl(SOHBET_DOSYASI):
        if k.get("rol") and k.get("metin"):
            turlar.append({"rol": k["rol"], "metin": k["metin"]})
    return turlar[-SOHBET_GOSTERILEN:]


def sohbet_kaydet(rol, metin):
    try:
        ekle_jsonl(SOHBET_DOSYASI, {
            "t": datetime.now(TZ).isoformat(), "rol": rol, "metin": metin,
        })
    except Exception:
        pass   # kayıt tutulamadı diye sohbet bozulmasın


def sohbet(govde):
    """Soruyu Cekirdek'e iletir (Claude API), cevabi doner.

    Soru ve cevap diske yazilir: sayfa yenilenince konusma kaybolmamali.
    """
    soru = (govde.get("soru") or "").strip()
    if not soru:
        return {"hata": "Bos soru."}
    gecmis = govde.get("gecmis") or []
    sesli = bool(govde.get("ses"))
    try:
        cevap = _beyin().sohbet(soru, gecmis, ses=sesli)
        sohbet_kaydet("kullanici", soru)
        sohbet_kaydet("asistan", cevap)
        return {"cevap": cevap}
    except RuntimeError as hata:
        return {"hata": str(hata)}
    except Exception as hata:
        return {"hata": anlasilir_hata(hata)}


def seslendir(govde):
    """Metni mp3'e cevirir, panelin calabilecegi adresi doner.

    Ses uretilemezse hata degil, `yol: null` doner: panel sessiz devam eder.
    """
    metin = (govde.get("metin") or "").strip()
    if not metin:
        return {"yol": None}
    try:
        import seslendir as motor
    except ImportError:
        return {"yol": None, "not": "edge-tts kurulu degil: pip install edge-tts"}
    dosya = motor.seslendir(metin)
    if not dosya:
        return {"yol": None, "not": "Ses uretilemedi (ag ya da servis)."}
    return {"yol": "/ses/" + os.path.basename(dosya)}


def ham_veri_cek(adimlar):
    """Agent'lar okumadan once ham veriyi tazeler.

    Cekme basarisiz olursa tarama durmaz: agent'lar eldeki son veriyle devam
    eder. Ag koptu diye brifing tamamen kaybolmamali — ama kullanici verinin
    bayat oldugunu gormeli, o yuzden hata `adimlar` icinde geri doner.
    """
    adimlar.append("Gmail cekiliyor…")
    try:
        import gmail_fetch
        veri = gmail_fetch.cek()
        gmail_fetch.yaz(veri)
        yeni, toplam = gmail_fetch.arsivle(veri)
        adimlar.append("Gmail: %d mail cekildi (arsiv: +%d, toplam %d)."
                       % (len(veri["mailler"]), yeni, toplam))
    except SystemExit as hata:       # kimlik bilgisi eksik
        # Adim listesi tek satirlik; cok satirli kurulum metnini sikistir.
        adimlar.append("Gmail cekilemedi: %s" % " ".join(str(hata).split()))
    except Exception as hata:
        adimlar.append("Gmail cekilemedi (%s: %s) — eldeki son veriyle devam."
                       % (type(hata).__name__, hata))

    # Instagram bagli degilse sessizce atlanir: kurulmamis bir kaynak hata degil.
    if os.path.exists(os.path.join(KOK, "secrets", "instagram_token.json")):
        adimlar.append("Instagram cekiliyor…")
        try:
            import instagram_fetch
            ig = instagram_fetch.cek()
            instagram_fetch.yaz(ig)
            adimlar.append("Instagram: %d konusma cekildi." % len(ig["konusmalar"]))
        except SystemExit as hata:
            adimlar.append("Instagram cekilemedi: %s" % " ".join(str(hata).split()))
        except Exception as hata:
            adimlar.append("Instagram cekilemedi (%s: %s) — eldeki son veriyle devam."
                           % (type(hata).__name__, hata))


# Sunucu cok is parcacikli; iki "simdi tara" ayni anda gelebilir. Ikisi de ayni
# digest dosyalarina yazar ve API kredisi iki kat harcanir. Kilit alinamiyorsa
# ikinci istek calismaz, suren taramaya yonlendirilir.
_TARAMA_KILIDI = threading.Lock()

# Taramanin durumu sunucuda tutulur, tarayicinin belleginde degil. Boylece
# sayfa yenilense ya da baska bir sekmeden bakilsa da taramanin surdugu ve
# hangi adimda oldugu gorulur.
_TARAMA_DURUMU = {"suruyor": False, "baslangic": None, "adimlar": [], "bitti": None}


def tarama_durumu():
    d = dict(_TARAMA_DURUMU)
    d["adimlar"] = list(d["adimlar"])   # cizim sirasinda liste degisebilir
    return d


def tarama(govde):
    """Ham veriyi tazeler, dort agent'i calistirip brifingi uretir ve arsivler."""
    if not _TARAMA_KILIDI.acquire(blocking=False):
        return {"hata": "Bir tarama zaten suruyor. Bitmesini bekleyin — "
                        "ayni anda iki tarama ayni dosyalara yazar."}
    baslangic = datetime.now(TZ)
    _TARAMA_DURUMU.update(suruyor=True, bitti=None, adimlar=[],
                          baslangic=baslangic.isoformat())
    sonuc = {}
    try:
        sonuc = _tarama(govde)
        return sonuc
    finally:
        bitti = datetime.now(TZ)
        _TARAMA_DURUMU.update(suruyor=False, bitti=bitti.isoformat())
        _TARAMA_KILIDI.release()
        tarama_kaydet({
            "baslangic": baslangic.isoformat(),
            "bitti": bitti.isoformat(),
            "saniye": round((bitti - baslangic).total_seconds(), 1),
            "adimlar": list(_TARAMA_DURUMU["adimlar"]),
            "hata": sonuc.get("hata"),
            "agentlar": sonuc.get("agentlar"),
            "brifing_uzunlugu": len(sonuc.get("brifing") or ""),
        })


def _tarama(govde):
    try:
        b = _beyin()
    except RuntimeError as hata:
        return {"hata": str(hata)}

    # Adimlar dogrudan paylasilan duruma yazilir; panel surerken okuyabilsin.
    adimlar = _TARAMA_DURUMU["adimlar"]
    ham_veri_cek(adimlar)
    try:
        sonuc = b.brief(ilerleme=adimlar.append)
    except Exception as hata:
        return {"hata": anlasilir_hata(hata), "adimlar": adimlar}

    brifing = sonuc.get("brifing") or ""
    if brifing:
        bugun = datetime.now(TZ).strftime("%Y-%m-%d")
        yol = os.path.join(KOK, "state", "log", "%s.md" % bugun)
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        io.open(yol, "w", encoding="utf-8").write(brifing + "\n")
    return {"tamam": True, "brifing": brifing, "adimlar": adimlar,
            "agentlar": sonuc.get("agentlar", {})}


# -------------------------------------------------------------------- sunucu

ROTALAR = {
    "/api/olay": olay_karari,
    "/api/onay": taslak_onayi,
    "/api/sohbet": sohbet,
    "/api/seslendir": seslendir,
    "/api/tarama": tarama,
    "/api/etkinlik-ekle": etkinlik_ekle,
    "/api/etkinlik-iptal": etkinlik_iptal,
    "/api/konu-ekle": konu_ekle,
    "/api/konu-sil": konu_sil,
    "/api/kategori": kategori_degistir,
    "/api/kisi-ekle": kisi_ekle,
    "/api/kisi-sil": kisi_sil,
}


class Isleyici(BaseHTTPRequestHandler):
    def log_message(self, bicim, *args):
        pass  # konsolu kirletme

    def _gonder(self, kod, govde, tur="application/json; charset=utf-8"):
        if isinstance(govde, (dict, list)):
            govde = json.dumps(govde, ensure_ascii=False)
        if isinstance(govde, str):
            govde = govde.encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(len(govde)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(govde)

    def _dosya(self, ad, tur):
        yol = os.path.join(PANEL, ad)
        if not os.path.exists(yol):
            return self._gonder(404, "yok", "text/plain; charset=utf-8")
        self._gonder(200, io.open(yol, encoding="utf-8").read(), tur)

    TURLER = {
        ".css": "text/css; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml",
        ".mp3": "audio/mpeg",
        ".png": "image/png",
        ".woff2": "font/woff2",
    }
    # Metin olarak okunacak uzantilar. Gerisi ikili okunur — mp3'u utf-8
    # cozmeye kalkmak patlar.
    METIN_TURLERI = (".css", ".js", ".json", ".svg", ".html", ".txt", ".md")

    def _statik(self, yol):
        """panel/ altındaki statik dosyaları sunar (tasarım sistemi vb.)."""
        gorece = yol.lstrip("/").replace("/", os.sep)
        tam = os.path.normpath(os.path.join(PANEL, gorece))
        if os.path.commonpath([os.path.abspath(tam), PANEL]) != PANEL:
            return self._gonder(403, "yasak", "text/plain; charset=utf-8")
        self._gonder_dosya(tam)

    def _gonder_dosya(self, tam):
        """Diskteki bir dosyayı türüne göre metin ya da ikili olarak yollar."""
        if not os.path.isfile(tam):
            return self._gonder(404, "yok", "text/plain; charset=utf-8")
        uzanti = os.path.splitext(tam)[1].lower()
        tur = self.TURLER.get(uzanti, "application/octet-stream")
        if uzanti in self.METIN_TURLERI:
            return self._gonder(200, io.open(tam, encoding="utf-8").read(), tur)
        with open(tam, "rb") as d:
            self._gonder(200, d.read(), tur)

    def _ses(self, yol):
        """Uretilmis mp3'leri sunar. Ad disaridan geldigi icin dogrulanir."""
        try:
            import seslendir as motor
        except ImportError:
            return self._gonder(404, "yok", "text/plain; charset=utf-8")
        tam = motor.dosya_yolu(yol.rsplit("/", 1)[-1])
        if not tam:
            return self._gonder(404, "yok", "text/plain; charset=utf-8")
        self._gonder_dosya(tam)

    def do_GET(self):
        yol = urlparse(self.path).path
        if yol in ("/", "/index.html"):
            return self._dosya("panel.html", "text/html; charset=utf-8")
        if yol.endswith(".js") and yol.count("/") == 1:
            return self._statik(yol)     # panel.js, avatar.js, ses.js
        if yol.startswith("/_ds/"):
            return self._statik(yol)
        if yol.startswith("/ses/"):
            return self._ses(yol)
        if yol == "/api/durum":
            return self._gonder(200, toplu_durum())
        if yol.startswith("/api/taslak/"):
            metin = taslak_oku(yol.rsplit("/", 1)[-1])
            if metin is None:
                return self._gonder(404, {"hata": "Taslak yok."})
            return self._gonder(200, {"metin": metin})
        if yol.startswith("/api/mail/"):
            return self._gonder(200, mail_oku(yol.rsplit("/", 1)[-1]))
        if yol.startswith("/api/arsiv/"):
            ad = os.path.basename(yol.rsplit("/", 1)[-1])
            tam = os.path.join(KOK, "state", "log", ad)
            if not os.path.exists(tam):
                return self._gonder(404, {"hata": "Kayıt yok."})
            return self._gonder(200, {"metin": io.open(tam, encoding="utf-8").read()})
        self._gonder(404, {"hata": "Bilinmeyen adres."})

    def do_POST(self):
        yol = urlparse(self.path).path
        islev = ROTALAR.get(yol)
        if islev is None:
            return self._gonder(404, {"hata": "Bilinmeyen adres."})
        uzunluk = int(self.headers.get("Content-Length") or 0)
        try:
            govde = json.loads(self.rfile.read(uzunluk).decode("utf-8")) if uzunluk else {}
        except ValueError:
            return self._gonder(400, {"hata": "Geçersiz JSON."})
        try:
            self._gonder(200, islev(govde))
        except Exception as hata:  # panel çökmesin, hatayı göster
            self._gonder(500, {"hata": "%s: %s" % (type(hata).__name__, hata)})


def main():
    izleyici_baslat()
    sunucu = ThreadingHTTPServer(("127.0.0.1", PORT), Isleyici)
    print("Panel hazir:  http://127.0.0.1:%d" % PORT)
    print("Canli gonderim:", "ACIK" if CANLI_GONDERIM else "KAPALI (onaylar yalnizca kaydedilir)")
    try:
        import beyin
        print("Model:", beyin.MODEL,
              "| API anahtari:", "var" if beyin.anahtar() else "YOK")
    except ImportError:
        print("Anthropic SDK kurulu degil: pip install anthropic")
    print("Durdurmak icin Ctrl+C")
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        print("\nKapatildi.")
        sunucu.server_close()


if __name__ == "__main__":
    sys.exit(main())

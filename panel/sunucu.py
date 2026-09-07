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
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = os.path.dirname(os.path.abspath(__file__))
if PANEL not in sys.path:
    sys.path.insert(0, PANEL)
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
    bugunun_brifingi = (io.open(bugun_yol, encoding="utf-8").read()
                        if os.path.exists(bugun_yol) else None)

    return {
        "simdi": datetime.now(TZ).isoformat(),
        "canli_gonderim": CANLI_GONDERIM,
        "bugunun_brifingi": bugunun_brifingi,
        "mail": oku_json("state/inbox-digest.json", {}),
        "sosyal": oku_json("state/social-queue.json", {}),
        "ajanda": oku_json("state/agenda.json", {}),
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


def _beyin():
    """beyin modulunu gec yukler; anthropic kurulu degilse anlasilir hata verir."""
    try:
        import beyin
        return beyin
    except ImportError as hata:
        raise RuntimeError(
            "Anthropic SDK kurulu degil. Kurmak icin: pip install anthropic (%s)" % hata
        )


def sohbet(govde):
    """Soruyu Cekirdek'e iletir (Claude API), cevabi doner."""
    soru = (govde.get("soru") or "").strip()
    if not soru:
        return {"hata": "Bos soru."}
    gecmis = govde.get("gecmis") or []
    try:
        return {"cevap": _beyin().sohbet(soru, gecmis)}
    except RuntimeError as hata:
        return {"hata": str(hata)}
    except Exception as hata:
        return {"hata": "%s: %s" % (type(hata).__name__, hata)}


def tarama(govde):
    """Dort agent'i calistirip gunluk brifingi uretir ve arsive yazar."""
    try:
        b = _beyin()
    except RuntimeError as hata:
        return {"hata": str(hata)}

    adimlar = []
    try:
        sonuc = b.brief(ilerleme=adimlar.append)
    except Exception as hata:
        return {"hata": "%s: %s" % (type(hata).__name__, hata), "adimlar": adimlar}

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
    "/api/tarama": tarama,
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
    }

    def _statik(self, yol):
        """panel/ altındaki statik dosyaları sunar (tasarım sistemi vb.)."""
        gorece = yol.lstrip("/").replace("/", os.sep)
        tam = os.path.normpath(os.path.join(PANEL, gorece))
        if os.path.commonpath([os.path.abspath(tam), PANEL]) != PANEL:
            return self._gonder(403, "yasak", "text/plain; charset=utf-8")
        if not os.path.isfile(tam):
            return self._gonder(404, "yok", "text/plain; charset=utf-8")
        tur = self.TURLER.get(os.path.splitext(tam)[1].lower(),
                              "application/octet-stream")
        self._gonder(200, io.open(tam, encoding="utf-8").read(), tur)

    def do_GET(self):
        yol = urlparse(self.path).path
        if yol in ("/", "/index.html"):
            return self._dosya("panel.html", "text/html; charset=utf-8")
        if yol == "/panel.js":
            return self._dosya("panel.js", "text/javascript; charset=utf-8")
        if yol.startswith("/_ds/"):
            return self._statik(yol)
        if yol == "/api/durum":
            return self._gonder(200, toplu_durum())
        if yol.startswith("/api/taslak/"):
            metin = taslak_oku(yol.rsplit("/", 1)[-1])
            if metin is None:
                return self._gonder(404, {"hata": "Taslak yok."})
            return self._gonder(200, {"metin": metin})
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

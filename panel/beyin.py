# -*- coding: utf-8 -*-
"""Çekirdek ve alt agent'ların API üzerinden çalışan hali.

Claude Code CLI'sinin yerini alır: agent tanımları .claude/agents/*.md
dosyalarından okunur, sistem istemi olarak verilir, dosya araçları burada
tanımlanır. Böylece proje Claude Code'a bağımlı olmadan çalışır.

Gerekenler:
    pip install anthropic
    API anahtarı: ANTHROPIC_API_KEY ortam değişkeni veya secrets/api_key.txt
"""

import io
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

import anthropic
from anthropic import beta_tool

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODEL = "claude-opus-5"
# Alt agent'lar sınırlı bir işi yapıyor; Çekirdek harmanlama ve sohbette
# varsayılan (high) efor ile çalışır.
AGENT_EFOR = "medium"

# Yazma yalnızca bu klasörlerin altına serbest. secrets/ hiçbir koşulda okunmaz.
YAZILABILIR = ("state", "projects", "config")
OKUNAMAZ = ("secrets",)

_istemci = None


def _env_oku(yol):
    """Basit .env okuyucu: ANAHTAR=deger satırları. Tırnak ve # yorumları temizler."""
    degerler = {}
    if not os.path.exists(yol):
        return degerler
    for satir in io.open(yol, encoding="utf-8"):
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        ad, _, deger = satir.partition("=")
        deger = deger.strip()
        if len(deger) > 1 and deger[0] == deger[-1] and deger[0] in "\"'":
            deger = deger[1:-1]
        degerler[ad.strip()] = deger
    return degerler


def anahtar():
    """API anahtarını sırayla ortamdan, .env dosyasından, secrets/ altından okur."""
    k = os.environ.get("ANTHROPIC_API_KEY")
    if k and k.strip():
        return k.strip()

    for env_yolu in (os.path.join(KOK, ".env"),
                     os.path.join(KOK, "secrets", ".env")):
        k = _env_oku(env_yolu).get("ANTHROPIC_API_KEY")
        if k:
            return k

    yol = os.path.join(KOK, "secrets", "api_key.txt")
    if os.path.exists(yol):
        ilk = io.open(yol, encoding="utf-8").read().strip()
        if ilk:
            return ilk
    return None


def istemci():
    global _istemci
    if _istemci is None:
        k = anahtar()
        if not k:
            raise RuntimeError(
                "API anahtarı yok. ANTHROPIC_API_KEY ortam değişkenini ayarla "
                "veya secrets/api_key.txt dosyasına anahtarı yaz."
            )
        _istemci = anthropic.Anthropic(api_key=k, timeout=300.0)
    return _istemci


# ------------------------------------------------------------------ guvenlik

def _coz(gorece):
    """Göreli yolu proje köküne göre çözer ve sınır dışına çıkmayı engeller."""
    tam = os.path.normpath(os.path.join(KOK, gorece))
    if os.path.commonpath([os.path.abspath(tam), KOK]) != KOK:
        raise ValueError("Proje dışına çıkılamaz: " + gorece)
    ilk = os.path.relpath(tam, KOK).replace("\\", "/").split("/")[0]
    if ilk in OKUNAMAZ:
        raise ValueError("Bu klasör okunamaz: " + ilk)
    return tam, ilk


def _yazilabilir_mi(ilk):
    if ilk not in YAZILABILIR:
        raise ValueError(
            "Yazma yalnızca şu klasörlerde serbest: " + ", ".join(YAZILABILIR)
        )


# -------------------------------------------------------------------- araclar

@beta_tool
def dosya_oku(yol: str) -> str:
    """Proje içindeki bir dosyayı okur.

    Args:
        yol: Proje köküne göre dosya yolu, örn. "state/inbox-digest.json".
    """
    try:
        tam, _ = _coz(yol)
    except ValueError as e:
        return "HATA: %s" % e
    if not os.path.exists(tam):
        return "HATA: dosya yok: " + yol
    icerik = io.open(tam, encoding="utf-8", errors="replace").read()
    if len(icerik) > 200000:
        return icerik[:200000] + "\n\n[... dosya kırpıldı ...]"
    return icerik


@beta_tool
def dosya_listele(klasor: str = ".") -> str:
    """Bir klasörün içeriğini listeler.

    Args:
        klasor: Proje köküne göre klasör yolu, örn. "projects" veya ".".
    """
    try:
        tam, _ = _coz(klasor)
    except ValueError as e:
        return "HATA: %s" % e
    if not os.path.isdir(tam):
        return "HATA: klasör yok: " + klasor
    satirlar = []
    for ad in sorted(os.listdir(tam)):
        if ad in OKUNAMAZ:
            continue
        p = os.path.join(tam, ad)
        satirlar.append(("[k] " if os.path.isdir(p) else "    ") + ad)
    return "\n".join(satirlar) or "(bos)"


@beta_tool
def ek_oku(dosya_adi: str) -> str:
    """Bir mail ekini okur. Ekler state/raw/ekler/ klasöründedir.

    PDF ekler metne çevrilir. Metin, JSON, CSV ekler doğrudan okunur.
    Diğer biçimler (docx, xlsx, görsel) henüz desteklenmiyor.

    Args:
        dosya_adi: Ekin dosya adı, örn. "sozlesme_rev3.pdf". Klasör yolu verme.
    """
    ad = os.path.basename(dosya_adi.strip())
    tam = os.path.join(KOK, "state", "raw", "ekler", ad)
    if not os.path.exists(tam):
        mevcut = []
        klasor = os.path.dirname(tam)
        if os.path.isdir(klasor):
            mevcut = sorted(os.listdir(klasor))
        return ("HATA: ek bulunamadı: %s. Bu klasördeki ekler: %s"
                % (ad, ", ".join(mevcut) if mevcut else "(hiç yok)"))

    uzanti = os.path.splitext(ad)[1].lower()
    if uzanti == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            return "HATA: PDF okumak için pypdf gerekli (pip install pypdf)."
        try:
            okuyucu = PdfReader(tam)
        except Exception as hata:
            return "HATA: PDF açılamadı: %s" % hata
        sayfalar = []
        for i, sayfa in enumerate(okuyucu.pages, start=1):
            sayfalar.append("[sayfa %d]\n%s" % (i, sayfa.extract_text() or ""))
        metin = "\n\n".join(sayfalar).strip()
        if not metin:
            return ("HATA: PDF'ten metin çıkmadı — taranmış görüntü olabilir. "
                    "Bu durumda içeriğe dair bir şey uydurma, kullanıcıya söyle.")
        return metin[:200000]

    if uzanti in (".txt", ".md", ".json", ".csv", ".tsv", ".log", ".eml"):
        return io.open(tam, encoding="utf-8", errors="replace").read()[:200000]

    return ("HATA: %s biçimi henüz okunamıyor. İçeriği hakkında tahmin yürütme, "
            "kullanıcıya dosyayı kendisinin açması gerektiğini söyle." % uzanti)


@beta_tool
def dosya_yaz(yol: str, icerik: str) -> str:
    """Dosyayı baştan yazar. Yalnızca state/, projects/, config/ altında serbest.

    olaylar.jsonl dosyalarına bu araçla YAZILAMAZ; onlar için dosya_ekle kullan.

    Args:
        yol: Proje köküne göre dosya yolu.
        icerik: Dosyanın tam yeni içeriği.
    """
    try:
        tam, ilk = _coz(yol)
        _yazilabilir_mi(ilk)
    except ValueError as e:
        return "HATA: %s" % e
    if tam.replace("\\", "/").endswith("olaylar.jsonl"):
        return ("HATA: olay günlüğü append-only. Baştan yazılamaz, "
                "dosya_ekle kullan.")
    os.makedirs(os.path.dirname(tam), exist_ok=True)
    io.open(tam, "w", encoding="utf-8").write(icerik)
    return "yazildi: %s (%d karakter)" % (yol, len(icerik))


@beta_tool
def dosya_ekle(yol: str, satir: str) -> str:
    """Dosyanın SONUNA bir satır ekler. Var olan satırlara dokunmaz.

    Olay günlüklerine (olaylar.jsonl) yazmanın tek yolu budur.

    Args:
        yol: Proje köküne göre dosya yolu, örn. "projects/x/olaylar.jsonl".
        satir: Eklenecek tek satır. JSONL ise geçerli bir JSON nesnesi olmalı.
    """
    try:
        tam, ilk = _coz(yol)
        _yazilabilir_mi(ilk)
    except ValueError as e:
        return "HATA: %s" % e
    if tam.endswith(".jsonl"):
        try:
            json.loads(satir)
        except ValueError as e:
            return "HATA: gecersiz JSON, satir eklenmedi: %s" % e
    os.makedirs(os.path.dirname(tam), exist_ok=True)
    with io.open(tam, "a", encoding="utf-8") as f:
        f.write(satir.rstrip("\n") + "\n")
    return "eklendi: " + yol


OKUMA_ARACLARI = [dosya_oku, dosya_listele, ek_oku]
YAZMA_ARACLARI = [dosya_oku, dosya_listele, ek_oku, dosya_yaz, dosya_ekle]


# ------------------------------------------------------------------- calistir

def _metin(mesaj):
    return "\n".join(b.text for b in mesaj.content if b.type == "text").strip()


def calistir(sistem, istek, araclar, efor=None, max_tokens=16000):
    """Bir tool-use döngüsü çalıştırır, son mesajın metnini döner.

    `istek` tek bir metin ya da hazır bir mesaj listesi olabilir.
    """
    mesajlar = istek if isinstance(istek, list) else [
        {"role": "user", "content": istek}
    ]
    # output_config yalnizca efor verildiginde gonderilir; None gecmek
    # istegi gecersiz kilar.
    ek = {"output_config": {"effort": efor}} if efor else {}
    runner = istemci().beta.messages.tool_runner(
        model=MODEL,
        max_tokens=max_tokens,
        system=sistem,
        thinking={"type": "adaptive"},
        tools=araclar,
        messages=mesajlar,
        **ek,
    )
    son = None
    for mesaj in runner:
        son = mesaj
    if son is None:
        return ""
    if son.stop_reason == "refusal":
        ayrinti = getattr(son, "stop_details", None)
        return "[istek reddedildi: %s]" % getattr(ayrinti, "category", "bilinmiyor")
    return _metin(son)


# --------------------------------------------------------------------- agent

def _on_madde_sil(metin):
    """Agent tanimindaki YAML on maddesini ayiklar, govdeyi dondurur."""
    return re.sub(r"^---\n.*?\n---\n", "", metin, count=1, flags=re.S).strip()


def agent_tanimi(ad):
    yol = os.path.join(KOK, ".claude", "agents", "%s.md" % ad)
    if not os.path.exists(yol):
        raise RuntimeError("Agent tanimi yok: " + ad)
    return _on_madde_sil(io.open(yol, encoding="utf-8").read())


def cekirdek_sistemi():
    parcalar = []
    for yol in ("CLAUDE.md", "config/persona.md"):
        tam = os.path.join(KOK, yol)
        if os.path.exists(tam):
            parcalar.append(io.open(tam, encoding="utf-8").read())
    parcalar.append(
        "Dosyalara dosya_oku/dosya_listele araçlarıyla erişirsin. Yollar proje "
        "köküne göredir. Mail eklerini ek_oku aracıyla okursun — bir mailde ek "
        "varsa ve içeriği soruya konu oluyorsa, tahmin yürütmeden önce eki aç. "
        "Bilmediğin bir şeyi uydurma; önce ilgili dosyayı oku."
    )
    return "\n\n---\n\n".join(parcalar)


def agent_calistir(ad, istek):
    sistem = agent_tanimi(ad) + (
        "\n\n---\n\nDosya araçların: dosya_oku, dosya_listele, dosya_yaz, dosya_ekle. "
        "Yollar proje köküne göredir. Çıktı dosyalarını gerçekten yaz — "
        "sohbet metni üretme, işini bitirince tek cümlelik özet dön."
    )
    return calistir(sistem, istek, YAZMA_ARACLARI, efor=AGENT_EFOR)


# --------------------------------------------------------------------- disari

# Bir sohbette API'ye taşınacak en fazla tur sayısı. Geçmiş büyüdükçe her istek
# pahalılaşır; son turlar bağlam için yeter.
SOHBET_HAFIZASI = 20


def sohbet(soru, gecmis=None):
    """Panelden gelen soruyu Çekirdek'e iletir (salt okunur araçlarla).

    `gecmis`: [{"rol": "kullanici"|"asistan", "metin": "..."}] listesi.
    Rolleri sıraya sokar; API user/assistant dönüşümlü olmasını şart koşar.
    """
    mesajlar = []
    for tur in (gecmis or [])[-SOHBET_HAFIZASI:]:
        metin = (tur.get("metin") or "").strip()
        if not metin:
            continue
        rol = "user" if tur.get("rol") == "kullanici" else "assistant"
        if mesajlar and mesajlar[-1]["role"] == rol:
            # Aynı rol art arda gelemez; birleştir.
            mesajlar[-1]["content"] += "\n\n" + metin
        else:
            mesajlar.append({"role": rol, "content": metin})

    if mesajlar and mesajlar[0]["role"] == "assistant":
        mesajlar.pop(0)  # geçmiş asistanla başlayamaz

    if mesajlar and mesajlar[-1]["role"] == "user":
        mesajlar[-1]["content"] += "\n\n" + soru
    else:
        mesajlar.append({"role": "user", "content": soru})

    return calistir(cekirdek_sistemi(), mesajlar, OKUMA_ARACLARI)


def brief(ilerleme=None):
    """Günlük brifingi üretir: üç toplayıcı paralel, sonra proje-agent, sonra harman."""
    def bildir(m):
        if ilerleme:
            ilerleme(m)

    isler = {
        "mail-agent": "state/raw/gmail.json dosyasını işle ve çıktını yaz.",
        "social-agent": "state/raw/instagram.json dosyasını işle ve çıktını yaz.",
        "calendar-agent": "state/raw/calendar.json dosyasını işle ve çıktını yaz.",
    }

    bildir("Üç toplayıcı agent çalışıyor…")
    with ThreadPoolExecutor(max_workers=3) as havuz:
        gelecek = {ad: havuz.submit(agent_calistir, ad, istek)
                   for ad, istek in isler.items()}
        sonuclar = {}
        for ad, g in gelecek.items():
            try:
                sonuclar[ad] = g.result()
            except Exception as hata:
                sonuclar[ad] = "HATA: %s" % hata

    bildir("Proje belleği güncelleniyor…")
    try:
        sonuclar["proje-agent"] = agent_calistir(
            "proje-agent",
            "Üç digest dosyasını oku, projelere olay öner ve durum.json dosyalarını türet.",
        )
    except Exception as hata:
        sonuclar["proje-agent"] = "HATA: %s" % hata

    bildir("Brifing harmanlanıyor…")
    brifing = calistir(
        cekirdek_sistemi(),
        "Alt agent'lar çalıştı ve state/ ile projects/ altındaki dosyaları güncelledi. "
        "Şimdi state/inbox-digest.json, state/social-queue.json, state/agenda.json ve "
        "projects/*/durum.json dosyalarını oku ve günlük brifingi üret. "
        "persona.md içindeki brifing formatına uy. Yalnızca brifing metnini dön.",
        OKUMA_ARACLARI,
    )
    return {"brifing": brifing, "agentlar": sonuclar}

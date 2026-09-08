# -*- coding: utf-8 -*-
"""Gmail'den ham mailleri çeker ve state/raw/gmail.json dosyasına yazar.

Kimlik doğrulama IMAP + Google Uygulama Şifresi ile yapılır; OAuth yoktur.
IMAP kutusu `readonly=True` ile açılır — okundu bayrağı bile değişmez, gönderim
yolu hiç açılmaz.

Çıktı şeması `scripts/seed_ornek_veri.py` ile birebir aynıdır; agent'lar iki
kaynağı ayırt etmez.

Gereken (secrets/.env):
    GMAIL_ADRES=...@gmail.com
    GMAIL_UYGULAMA_SIFRESI=xxxxxxxxxxxxxxxx

Kullanım:
    python scripts/gmail_fetch.py          çeker ve yazar
    python scripts/gmail_fetch.py --kuru   çeker, yazmaz, özet basar
"""

import email
import email.utils
import html
import imaplib
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header

TZ = timezone(timedelta(hours=3))
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.join(KOK, "panel"))
from beyin import _env_oku  # .env okuyucusu tek yerde dursun  # noqa: E402

SUNUCU = "imap.gmail.com"
GUN = 1           # kaç günlük pencere taranır (agent'ın gördüğü pencere)
TAVAN = 50        # en fazla kaç mail alınır (en yeniden geriye)
GOVDE_SINIR = 2000   # modele giden gövde uzunluğu (PLAN.md §8)
EK_SINIR = 5 * 1024 * 1024   # bundan büyük ekler indirilmez

# Yalnızca beyin.ek_oku'nun okuyabildiği biçimler indirilir; diğerlerinin adı
# listede kalır, ek_oku "bu biçim okunamıyor" diyerek tahmini engeller.
INEN_UZANTILAR = (".pdf", ".txt", ".md", ".json", ".csv", ".tsv", ".log", ".eml")


# ------------------------------------------------------------------- ayarlar

def ayarlar():
    """Adres ve uygulama şifresini ortamdan ya da secrets/.env'den okur."""
    d = {}
    for yol in (os.path.join(KOK, "secrets", ".env"), os.path.join(KOK, ".env")):
        for ad, deger in _env_oku(yol).items():
            d.setdefault(ad, deger)
    adres = os.environ.get("GMAIL_ADRES") or d.get("GMAIL_ADRES")
    sifre = os.environ.get("GMAIL_UYGULAMA_SIFRESI") or d.get("GMAIL_UYGULAMA_SIFRESI")
    if not adres or not sifre:
        raise SystemExit(
            "Gmail kimlik bilgisi yok.\n"
            "secrets/.env dosyasina sunlari yaz:\n"
            "  GMAIL_ADRES=...@gmail.com\n"
            "  GMAIL_UYGULAMA_SIFRESI=xxxxxxxxxxxxxxxx\n"
            "Uygulama sifresi: https://myaccount.google.com/apppasswords "
            "(hesapta 2FA acik olmali)"
        )
    # Uygulama şifresi panelde boşluklu gösterilir; IMAP boşluk kabul etmez.
    return adres.strip(), sifre.replace(" ", "").strip()


# ---------------------------------------------------------------- cozumleme

def basligi_coz(ham):
    """MIME ile kodlanmış başlığı düz metne çevirir (=?UTF-8?B?... → Türkçe)."""
    if not ham:
        return ""
    try:
        return str(make_header(decode_header(ham))).strip()
    except Exception:
        return ham.strip()


def adres_listesi(ham):
    """'A <a@x>, B <b@y>' → ['A <a@x>', 'B <b@y>']. Boşsa boş liste."""
    if not ham:
        return []
    return [email.utils.formataddr((basligi_coz(ad), posta))
            for ad, posta in email.utils.getaddresses([basligi_coz(ham)]) if posta]


def _parca_metni(parca):
    ham = parca.get_payload(decode=True)
    if ham is None:
        return ""
    kod = parca.get_content_charset() or "utf-8"
    try:
        return ham.decode(kod, errors="replace")
    except LookupError:
        return ham.decode("utf-8", errors="replace")


def _html_soy(metin):
    """Kaba HTML temizliği: script/style at, etiketleri sil, boşlukları topla."""
    metin = re.sub(r"(?is)<(script|style).*?</\1>", " ", metin)
    metin = re.sub(r"(?i)<br\s*/?>|</p>", "\n", metin)
    metin = re.sub(r"(?s)<[^>]+>", " ", metin)
    metin = html.unescape(metin).replace("\xa0", " ")
    metin = re.sub(r"[ \t]+", " ", metin)
    return re.sub(r"\n{3,}", "\n\n", metin).strip()


def govde_cikar(mesaj):
    """text/plain tercih edilir; yoksa text/html'den metin soyulur."""
    duz, zengin = [], []
    if mesaj.is_multipart():
        for parca in mesaj.walk():
            if parca.get_content_maintype() == "multipart":
                continue
            if (parca.get("Content-Disposition") or "").lower().startswith("attachment"):
                continue
            tur = parca.get_content_type()
            if tur == "text/plain":
                duz.append(_parca_metni(parca))
            elif tur == "text/html":
                zengin.append(_parca_metni(parca))
    else:
        metin = _parca_metni(mesaj)
        (duz if mesaj.get_content_type() == "text/plain" else zengin).append(metin)

    metin = "\n".join(p for p in duz if p.strip()).strip()
    if not metin:
        metin = _html_soy("\n".join(zengin))
    metin = re.sub(r"\n{3,}", "\n\n", metin).strip()
    if len(metin) > GOVDE_SINIR:
        metin = metin[:GOVDE_SINIR] + "\n\n[... govde kirpildi ...]"
    return metin


def toplu_mu(mesaj):
    """Toplu gönderim (bülten/pazarlama) başlığı taşıyor mu.

    `List-Unsubscribe` kesin sinyaldir: abonelikten çıkma bağlantısı yalnızca liste
    gönderimlerinde bulunur. Bir mülakat daveti bu başlıkla gelmez — bu ayrım
    skorlamada bülteni işlem mailinden ayırmak için kullanılır.
    """
    for baslik in ("List-Unsubscribe", "List-Id", "Precedence", "Auto-Submitted"):
        deger = (mesaj.get(baslik) or "").strip().lower()
        if not deger:
            continue
        if baslik == "Precedence" and deger not in ("bulk", "list", "junk"):
            continue
        if baslik == "Auto-Submitted" and deger == "no":
            continue
        return True
    return False


def thread_kimligi(mesaj):
    """IMAP'te thread yok; References/In-Reply-To zincirinin kökü kullanılır."""
    for baslik in ("References", "In-Reply-To"):
        deger = mesaj.get(baslik)
        if deger:
            kimlikler = re.findall(r"<[^>]+>", deger)
            if kimlikler:
                return kimlikler[0].strip("<>")
    return (mesaj.get("Message-ID") or "").strip("<> ")


def tarih_cikar(mesaj):
    try:
        dt = email.utils.parsedate_to_datetime(mesaj.get("Date"))
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ).isoformat()


def ekleri_indir(mesaj, kuru):
    """Okunabilir ve küçük ekleri state/raw/ekler/ altına indirir.

    Dönen liste her ekin adını taşır — inmeyenler de dahil. Adı bilinen ama
    içeriği olmayan eke ek_oku "bulunamadi" der; agent tahmin yürütmez.
    """
    adlar = []
    klasor = os.path.join(KOK, "state", "raw", "ekler")
    for parca in mesaj.walk():
        ham_ad = parca.get_filename()
        if not ham_ad:
            continue
        # Ek adı yol içeremez: "../../secrets/.env" gibi bir ad kabul edilmez.
        ad = os.path.basename(basligi_coz(ham_ad)).strip()
        if not ad:
            continue
        adlar.append(ad)
        if kuru or os.path.splitext(ad)[1].lower() not in INEN_UZANTILAR:
            continue
        icerik = parca.get_payload(decode=True)
        if not icerik or len(icerik) > EK_SINIR:
            continue
        os.makedirs(klasor, exist_ok=True)
        with io.open(os.path.join(klasor, ad), "wb") as f:
            f.write(icerik)
    return adlar


# -------------------------------------------------------------------- cekme

def _arama(kutu, olcut):
    """UID ile arar. Sira numarasi degil UID: sira numaralari yeni mail geldikce
    kayar, UID kutuda sabit kalir — taramalar arasi eslestirme ancak boyle
    dogru olur (taslak dosya adlari da bu id'ye bagli)."""
    tamam, veri = kutu.uid("SEARCH", None, olcut)
    if tamam != "OK":
        raise RuntimeError("IMAP arama basarisiz: " + olcut)
    return veri[0].split()


def cek(kuru=False):
    """Gmail'e bağlanır, pencere içindeki mailleri şemaya çevirip döner."""
    adres, sifre = ayarlar()
    kutu = imaplib.IMAP4_SSL(SUNUCU, 993)
    try:
        try:
            kutu.login(adres, sifre)
        except imaplib.IMAP4.error as hata:
            raise RuntimeError(
                "Gmail girisi reddedildi (%s). Uygulama sifresi dogru mu, "
                "hesapta 2FA acik mi?" % hata
            )
        # readonly: sunucudaki okundu bayragina dokunulmaz.
        kutu.select("INBOX", readonly=True)

        sinir = (datetime.now(TZ) - timedelta(days=GUN)).strftime("%d-%b-%Y")
        kimlikler = _arama(kutu, '(SINCE "%s")' % sinir)[-TAVAN:]
        okunmamis = len(_arama(kutu, "(UNSEEN)"))

        mailler = []
        for kimlik in reversed(kimlikler):   # en yeniden geriye
            tamam, veri = kutu.uid("FETCH", kimlik, "(RFC822)")
            if tamam != "OK" or not veri or not isinstance(veri[0], tuple):
                continue
            mesaj = email.message_from_bytes(veri[0][1])
            mailler.append({
                "id": kimlik.decode(),
                "gonderen": basligi_coz(mesaj.get("From")),
                "alici": adres_listesi(mesaj.get("To")),
                "cc": adres_listesi(mesaj.get("Cc")),
                "konu": basligi_coz(mesaj.get("Subject")),
                "tarih": tarih_cikar(mesaj),
                "thread_id": thread_kimligi(mesaj),
                "toplu": toplu_mu(mesaj),
                "govde": govde_cikar(mesaj),
                "ekler": ekleri_indir(mesaj, kuru),
            })
    finally:
        try:
            kutu.logout()
        except Exception:
            pass

    return {
        "cekildi": datetime.now(TZ).isoformat(),
        "hesap": adres,
        # Kimliklerin UID oldugunu isaretler. Bu alani tasimayan eski dosyalar
        # sira numarasi tasir; onlarla eslestirme yapilamaz.
        "kimlik_turu": "uid",
        "toplam_okunmamis": okunmamis,
        "mailler": mailler,
    }


def arsivle(veri):
    """Cekilen her maili kalici arsive ekler. Ayni UID iki kez yazilmaz.

    Arsiv agent'in girdisi degildir — `gmail.json` yalnizca son pencereyi tasir,
    boylece tarama maliyeti sabit kalir. Gecmis burada durur.
    """
    yol = os.path.join(KOK, "state", "raw", "arsiv.jsonl")
    varolan = set()
    if os.path.exists(yol):
        for satir in io.open(yol, encoding="utf-8"):
            satir = satir.strip()
            if not satir:
                continue
            try:
                varolan.add(json.loads(satir).get("id"))
            except ValueError:
                continue   # bozuk satir arsivi kilitlemesin

    yeni = [m for m in veri["mailler"] if m["id"] not in varolan]
    if yeni:
        os.makedirs(os.path.dirname(yol), exist_ok=True)
        with io.open(yol, "a", encoding="utf-8") as f:
            for m in yeni:
                kayit = dict(m, hesap=veri["hesap"], arsivlendi=veri["cekildi"])
                f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
    return len(yeni), len(varolan) + len(yeni)


def cek_uid_ustu(son_uid, tavan=20):
    """Verilen UID'den büyük mailleri döner. Canlı izleyici bunu kullanır.

    Tüm pencereyi değil yalnızca yenileri çeker; hiç yeni mail yoksa tek bir
    IMAP aramasıyla boş döner. `son_uid` 0 ise kutunun son UID'si öğrenilir ve
    hiçbir şey işlenmez — izleyici ilk açılışta geçmişi bildirmemeli.
    """
    adres, sifre = ayarlar()
    kutu = imaplib.IMAP4_SSL(SUNUCU, 993)
    try:
        kutu.login(adres, sifre)
        kutu.select("INBOX", readonly=True)
        hepsi = _arama(kutu, "(ALL)")
        if not hepsi:
            return []
        kutunun_sonu = int(hepsi[-1])
        if not son_uid or son_uid > kutunun_sonu:
            # Kayitli UID kutununkinden buyukse gecersizdir: kutu yeniden
            # olusturulmus (UIDVALIDITY degismis) ya da deger bozulmustur.
            # Gecmisi bildirmemek icin kutunun sonuna hizalanir.
            return [{"id": str(kutunun_sonu)}]
        kimlikler = [u for u in _arama(kutu, "(UID %d:*)" % (son_uid + 1))
                     if int(u) > son_uid][-tavan:]
        mailler = []
        for kimlik in kimlikler:
            tamam, veri = kutu.uid("FETCH", kimlik, "(RFC822)")
            if tamam != "OK" or not veri or not isinstance(veri[0], tuple):
                continue
            mesaj = email.message_from_bytes(veri[0][1])
            mailler.append({
                "id": kimlik.decode(),
                "gonderen": basligi_coz(mesaj.get("From")),
                "alici": adres_listesi(mesaj.get("To")),
                "cc": adres_listesi(mesaj.get("Cc")),
                "konu": basligi_coz(mesaj.get("Subject")),
                "tarih": tarih_cikar(mesaj),
                "thread_id": thread_kimligi(mesaj),
                "toplu": toplu_mu(mesaj),
                "govde": govde_cikar(mesaj),
                "ekler": ekleri_indir(mesaj, kuru=True),
            })
        return mailler
    finally:
        try:
            kutu.logout()
        except Exception:
            pass


def yaz(veri):
    yol = os.path.join(KOK, "state", "raw", "gmail.json")
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with io.open(yol, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)
    return yol


def main():
    kuru = "--kuru" in sys.argv
    veri = cek(kuru=kuru)
    print("hesap: %s | %d mail | %d okunmamis"
          % (veri["hesap"], len(veri["mailler"]), veri["toplam_okunmamis"]))
    for m in veri["mailler"][:10]:
        print("  %-28.28s  %-46.46s  %s"
              % (m["gonderen"], m["konu"], (m["tarih"] or "")[:16]))
    if kuru:
        print("\n--kuru: dosyaya yazilmadi.")
    else:
        print("\nyazildi:", os.path.relpath(yaz(veri), KOK))
        yeni, toplam = arsivle(veri)
        print("arsiv  : +%d yeni, toplam %d mail (state/raw/arsiv.jsonl)"
              % (yeni, toplam))


if __name__ == "__main__":
    main()

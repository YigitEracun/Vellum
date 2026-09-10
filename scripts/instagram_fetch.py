# -*- coding: utf-8 -*-
"""Instagram DM'lerini çeker ve state/raw/instagram.json dosyasına yazar.

"Instagram API with Instagram Login" kullanılır — Facebook Sayfası gerekmez.
Hesabın **profesyonel** (İşletme veya Kreatör) olması şarttır; kişisel hesap bu
API'yi hiç kullanamaz.

App Review gerekmez: uygulama geliştirme modundayken, uygulamada rolü olan
hesapların (yani sizin) verisine erişilebilir. App Review ancak başkalarının
hesaplarını yöneten bir ürün yayımlarken gerekir.

Çıktı şeması `scripts/seed_ornek_veri.py` ile birebir aynıdır; agent'lar iki
kaynağı ayırt etmez.

Gereken (secrets/.env):
    IG_APP_ID=...
    IG_APP_SECRET=...
    IG_TOKEN=...            # ilk kez `--baglan` ile alınır

Kullanım:
    python scripts/instagram_fetch.py --baglan   hesabı bağlar (tek seferlik)
    python scripts/instagram_fetch.py            çeker ve yazar
    python scripts/instagram_fetch.py --kuru     çeker, yazmaz, özet basar
"""

import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

TZ = timezone(timedelta(hours=3))
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.join(KOK, "panel"))
from beyin import _env_oku  # .env okuyucusu tek yerde dursun  # noqa: E402

SURUM = "v25.0"
GRAPH = "https://graph.instagram.com/" + SURUM
GRAPH_KOK = "https://graph.instagram.com"
YETKI = "https://www.instagram.com/oauth/authorize"
TOKEN = "https://api.instagram.com/oauth/access_token"

# Instagram Login kapsamları. Mesaj okumak için ikisi de gerekli.
KAPSAM = "instagram_business_basic,instagram_business_manage_messages"

# Yerel geri dönüş adresi — Meta uygulamasında da aynısı tanımlanmalı.
GERI_DONUS_PORT = 8788
GERI_DONUS = "http://localhost:%d/" % GERI_DONUS_PORT

KONUSMA_TAVANI = 25      # kaç konuşma taranır
MESAJ_TAVANI = 20        # API zaten son 20 mesajı veriyor
METIN_SINIR = 2000       # modele giden metin uzunluğu (mail ile aynı ilke)
TOKEN_DOSYASI = os.path.join(KOK, "secrets", "instagram_token.json")


# ------------------------------------------------------------------- ayarlar

def ayarlar():
    d = {}
    for yol in (os.path.join(KOK, "secrets", ".env"), os.path.join(KOK, ".env")):
        for ad, deger in _env_oku(yol).items():
            d.setdefault(ad, deger)
    kimlik = os.environ.get("IG_APP_ID") or d.get("IG_APP_ID")
    sifre = os.environ.get("IG_APP_SECRET") or d.get("IG_APP_SECRET")
    if not kimlik or not sifre:
        raise SystemExit(
            "Instagram uygulama bilgisi yok.\n"
            "secrets/.env dosyasina sunlari yaz:\n"
            "  IG_APP_ID=...\n"
            "  IG_APP_SECRET=...\n"
            "Bunlar developers.facebook.com uzerinde olusturdugun uygulamanin\n"
            "Instagram > API setup with Instagram business login bolumunde."
        )
    return kimlik.strip(), sifre.strip()


def token_oku():
    """Uzun ömürlü token. secrets/ altında durur, git'e girmez."""
    if os.path.exists(TOKEN_DOSYASI):
        try:
            return json.load(io.open(TOKEN_DOSYASI, encoding="utf-8"))
        except ValueError:
            pass
    d = {}
    for yol in (os.path.join(KOK, "secrets", ".env"), os.path.join(KOK, ".env")):
        for ad, deger in _env_oku(yol).items():
            d.setdefault(ad, deger)
    ham = os.environ.get("IG_TOKEN") or d.get("IG_TOKEN")
    return {"access_token": ham} if ham else {}


def token_yaz(kayit):
    kayit["guncelleme"] = datetime.now(TZ).isoformat()
    os.makedirs(os.path.dirname(TOKEN_DOSYASI), exist_ok=True)
    with io.open(TOKEN_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(kayit, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------- http

def _cagir(url, parametreler=None):
    """Graph API çağrısı. Hata gövdesini yutmaz — Meta sebebi orada yazar."""
    if parametreler:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(parametreler)
    try:
        with urllib.request.urlopen(url, timeout=30) as yanit:
            return json.loads(yanit.read().decode("utf-8"))
    except urllib.error.HTTPError as hata:
        govde = hata.read().decode("utf-8", "replace")
        try:
            ayrinti = json.loads(govde).get("error", {}).get("message", govde)
        except ValueError:
            ayrinti = govde
        raise RuntimeError("Instagram API %s: %s" % (hata.code, ayrinti[:300]))


# ------------------------------------------------------------------ baglanma

class _Yakalayici(BaseHTTPRequestHandler):
    """Tek seferlik geri dönüş sunucusu: yetki kodunu yakalar."""
    kod = None

    def log_message(self, *a):
        pass

    def do_GET(self):
        sorgu = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _Yakalayici.kod = (sorgu.get("code") or [None])[0]
        hata = (sorgu.get("error_description") or sorgu.get("error") or [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        mesaj = ("Bağlandı. Bu sekmeyi kapatabilirsiniz."
                 if _Yakalayici.kod else "Bağlanamadı: %s" % hata)
        self.wfile.write(("<meta charset='utf-8'><body style=\"font-family:"
                          "'Segoe UI',sans-serif;padding:40px\"><h2>%s</h2>"
                          % mesaj).encode("utf-8"))


def baglan():
    """Tarayıcıda izin akışını açar, uzun ömürlü token'ı secrets/ altına yazar."""
    kimlik, sifre = ayarlar()
    url = YETKI + "?" + urllib.parse.urlencode({
        "client_id": kimlik,
        "redirect_uri": GERI_DONUS,
        "response_type": "code",
        "scope": KAPSAM,
    })
    print("Tarayici aciliyor. Instagram'da izin verin.")
    print("Acilmazsa su adresi elle acin:\n  %s\n" % url)
    webbrowser.open(url)

    sunucu = HTTPServer(("localhost", GERI_DONUS_PORT), _Yakalayici)
    sunucu.timeout = 300
    while _Yakalayici.kod is None:
        sunucu.handle_request()
        if _Yakalayici.kod is None:
            print("Kod gelmedi, bekleniyor…")
            break
    sunucu.server_close()
    if not _Yakalayici.kod:
        raise SystemExit("Yetki kodu alinamadi.")

    # Kod → kısa ömürlü token
    govde = urllib.parse.urlencode({
        "client_id": kimlik, "client_secret": sifre,
        "grant_type": "authorization_code",
        "redirect_uri": GERI_DONUS, "code": _Yakalayici.kod,
    }).encode()
    istek = urllib.request.Request(TOKEN, data=govde)
    try:
        with urllib.request.urlopen(istek, timeout=30) as yanit:
            kisa = json.loads(yanit.read().decode("utf-8"))
    except urllib.error.HTTPError as hata:
        raise SystemExit("Token alinamadi: %s" % hata.read().decode("utf-8", "replace")[:300])

    # Kısa ömürlü → uzun ömürlü (60 gün)
    uzun = _cagir(GRAPH_KOK + "/access_token", {
        "grant_type": "ig_exchange_token",
        "client_secret": sifre,
        "access_token": kisa["access_token"],
    })
    kayit = {"access_token": uzun["access_token"],
             "user_id": kisa.get("user_id"),
             "expires_in": uzun.get("expires_in")}
    token_yaz(kayit)
    print("Baglandi. Token secrets/instagram_token.json icinde (60 gun gecerli).")
    return kayit


def token_tazele(kayit):
    """60 günlük token'ı süresi dolmadan yeniler. Günde bir denemek yeter."""
    try:
        yeni = _cagir(GRAPH_KOK + "/refresh_access_token", {
            "grant_type": "ig_refresh_token",
            "access_token": kayit["access_token"],
        })
    except RuntimeError as hata:
        print("token tazelenemedi:", hata)
        return kayit
    kayit = dict(kayit, access_token=yeni["access_token"],
                 expires_in=yeni.get("expires_in"))
    token_yaz(kayit)
    return kayit


# -------------------------------------------------------------------- cekme

def _zaman(ham):
    """Graph zamanı ISO8601'e çevirir; biçim değişirse ham değeri korur."""
    if not ham:
        return None
    try:
        return datetime.strptime(ham, "%Y-%m-%dT%H:%M:%S%z").astimezone(TZ).isoformat()
    except ValueError:
        return ham


def cek():
    """Konuşmaları ve son mesajlarını çeker, ham şemaya çevirir."""
    kayit = token_oku()
    if not kayit.get("access_token"):
        raise SystemExit(
            "Instagram baglantisi yok. Once su komutu calistir:\n"
            "  python scripts/instagram_fetch.py --baglan"
        )
    tk = kayit["access_token"]

    ben = _cagir(GRAPH + "/me", {"fields": "user_id,username", "access_token": tk})
    hesap = "@" + (ben.get("username") or "?")

    liste = _cagir(GRAPH + "/me/conversations",
                   {"platform": "instagram", "access_token": tk})
    konusmalar = []
    for k in (liste.get("data") or [])[:KONUSMA_TAVANI]:
        ayrinti = _cagir("%s/%s" % (GRAPH, k["id"]),
                         {"fields": "messages", "access_token": tk})
        mesaj_kimlikleri = [m["id"] for m in
                            ((ayrinti.get("messages") or {}).get("data") or [])]

        mesajlar, kisi = [], None
        for mid in mesaj_kimlikleri[:MESAJ_TAVANI]:
            m = _cagir("%s/%s" % (GRAPH, mid),
                       {"fields": "id,created_time,from,to,message",
                        "access_token": tk})
            gonderen = (m.get("from") or {}).get("username")
            benim_mi = (m.get("from") or {}).get("id") == ben.get("user_id")
            if not benim_mi and gonderen and not kisi:
                kisi = "@" + gonderen
            metin = (m.get("message") or "").strip()
            if len(metin) > METIN_SINIR:
                metin = metin[:METIN_SINIR] + " […]"
            mesajlar.append({
                "yon": "giden" if benim_mi else "gelen",
                "t": _zaman(m.get("created_time")),
                "metin": metin,
            })
        mesajlar.sort(key=lambda x: x["t"] or "")
        konusmalar.append({
            "id": k["id"],
            "kisi": kisi or "@bilinmeyen",
            "mesajlar": mesajlar,
        })

    return {
        "cekildi": datetime.now(TZ).isoformat(),
        "hesap": hesap,
        "konusmalar": konusmalar,
    }


def yaz(veri):
    yol = os.path.join(KOK, "state", "raw", "instagram.json")
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with io.open(yol, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)
    return yol


def main():
    if "--baglan" in sys.argv:
        baglan()
        return 0

    kayit = token_oku()
    if kayit.get("access_token") and kayit.get("guncelleme"):
        # 60 günlük token; günde bir tazelemek yeter, süresi dolmadan yenilenir.
        try:
            yas = time.time() - os.path.getmtime(TOKEN_DOSYASI)
            if yas > 86400:
                token_tazele(kayit)
        except OSError:
            pass

    veri = cek()
    print("hesap: %s | %d konusma" % (veri["hesap"], len(veri["konusmalar"])))
    for k in veri["konusmalar"][:10]:
        son = k["mesajlar"][-1] if k["mesajlar"] else {}
        print("  %-22.22s %-5s %.50s" % (k["kisi"], son.get("yon", ""),
                                         (son.get("metin") or "").replace("\n", " ")))
    if "--kuru" in sys.argv:
        print("\n--kuru: dosyaya yazilmadi.")
    else:
        print("\nyazildi:", os.path.relpath(yaz(veri), KOK))
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Kişisel Asistan Sistemi — Plan

**Karar özeti:** Yerel çalışan, Windows Task Scheduler ile tetiklenen, dosya tabanlı (JSON + Markdown), Gmail + Google Takvim + Instagram DM okuyan, hiçbir şeyi onaysız göndermeyen çok-agent'lı tek varlık.

---

## 1. Temel ilke: "Tek varlık, üç uzuv"

Kullanıcı yalnızca **Çekirdek** ile konuşur. Alt agent'lar kullanıcıya hitap etmez, kendi üslubunu kullanmaz, kendi başına karar vermez. Her biri yalnızca **yapılandırılmış veri** üretir; o veriyi insan diline çeviren tek yer Çekirdek'tir.

```
                 ┌─────────────────────────┐
   sen  ◄──────► │   ÇEKİRDEK (persona)    │
                 │  tek ses, tek brifing   │
                 └───┬───────┬─────────┬───┘
                     │       │         │
              ┌──────▼──┐ ┌──▼──────┐ ┌▼──────────┐
              │  mail   │ │ social  │ │ calendar  │
              │  agent  │ │  agent  │ │  agent    │
              └────┬────┘ └────┬────┘ └─────┬─────┘
                   └───────────┴────────────┘
                               │
                    ┌──────────▼───────────┐
                    │   state/  +  proje    │
                    │   ortak hafıza        │
                    └───────────────────────┘
```

`proje-agent` dördüncü bir uzuv değil, diğer üçünün **ortak belleği**: her agent olayları
ilgili projeye düşürür, proje geçmişi böylece kendiliğinden oluşur (bkz. Bölüm 9).

Bütünlüğü sağlayan üç mekanizma:

1. **Ortak hafıza** — hepsi aynı `state/` klasörüne yazar. Mail'de geçen "salı 14:00 görüşme" `calendar-agent`'ın girdisi olur; Instagram'dan gelen bir iş teklifi `mail-agent`'ın VIP listesini besler. Agent'lar birbirini çağırmaz, ortak zemin üzerinden haberleşir.
2. **Ortak persona** — `config/persona.md` tek kişilik tanımı. Her alt agent prompt'unda "sen bağımsız bir asistan değilsin, bu varlığın bir bileşenisin" cümlesi yer alır.
3. **Tek çıkış kapısı** — çıktı yalnızca günlük brifing ve acil bildirim olarak gelir. Üç ayrı rapor değil, harmanlanmış tek metin.

---

## 2. Klasör yapısı

```
assistant/
├── CLAUDE.md                  # Çekirdek talimatları (her oturumda yüklenir)
├── PLAN.md                    # bu dosya
├── .claude/
│   ├── agents/
│   │   ├── mail-agent.md
│   │   ├── social-agent.md
│   │   ├── calendar-agent.md
│   │   └── proje-agent.md
│   ├── commands/
│   │   ├── brief.md           # /brief   → günlük brifing üret
│   │   ├── kuyruk.md          # /kuyruk  → bekleyen taslakları göster
│   │   └── onayla.md          # /onayla  → taslağı gönder
│   └── settings.json          # izinler, hook'lar
├── config/
│   ├── persona.md             # ses tonu, hitap, brifing formatı
│   ├── onem-kurallari.md      # önem skorlama rubriği
│   └── kisiler.md             # VIP / gürültü listesi
├── state/                     # ORTAK HAFIZA (agent çıktıları)
│   ├── inbox-digest.json
│   ├── social-queue.json
│   ├── agenda.json
│   ├── taslaklar/             # onay bekleyen cevaplar (.md)
│   └── log/YYYY-AA-GG.md      # brifing arşivi
├── projects/                  # PROJE HAFIZASI (bkz. Bölüm 9)
│   └── <proje-adi>/
│       ├── proje.md
│       ├── olaylar.jsonl      # append-only, asla silinmez
│       ├── durum.json         # olaylardan türetilir
│       ├── kararlar/
│       └── notlar/
├── panel/                     # TEK ARAYÜZ (bkz. Bölüm 10)
│   ├── sunucu.py              # http.server, 127.0.0.1:8787
│   ├── beyin.py               # Çekirdek + agent'lar (Claude API)
│   ├── panel.html             # "Tek Ağız" yerleşimi
│   ├── panel.js
│   └── _ds/broadsheet/        # tasarım sistemi (styles.css)
├── tasarım/                   # Claude Design kaynağı (.dc.html + _ds)
├── bot/
│   └── telegram_bot.py        # panelin uzaktan kolu
├── scripts/
│   ├── gmail_fetch.py
│   ├── ig_fetch.py
│   ├── calendar_sync.py
│   └── run-brief.ps1          # Task Scheduler girişi
└── secrets/                   # .gitignore — OAuth token'ları
```

---

## 3. Agent tanımları

### 3.1 mail-agent

**Girdi:** `scripts/gmail_fetch.py` çıktısı (son N saatteki okunmamış mailler, ham JSON)
**İş:** Her maile 0–100 önem skoru ver, kategorile, aksiyon gerekiyorsa çıkar.
**Çıktı:** `state/inbox-digest.json`

Önem skoru bileşenleri (`config/onem-kurallari.md`):

| Sinyal | Etki |
|---|---|
| Gönderen VIP listesinde | +40 |
| Doğrudan sana yazılmış | +20 |
| CC / toplu gönderim | −15 |
| İçinde tarih veya son tarih var | +25 |
| Para, fatura, sözleşme, hukuki | +30 |
| Thread'de sıra sende | +20 |
| Bülten / pazarlama / otomatik bildirim | −50 |

**Kural:** Skor ≥ 70 → brifingin başında, aksiyon maddesi olarak. 40–69 → "bilgin olsun" bölümü. < 40 → sadece sayı olarak ("47 düşük öncelikli mail").

### 3.2 social-agent

**Girdi:** `scripts/ig_fetch.py` (Instagram DM konuşmaları)
**İş:** Spam/bot ele, gerçek mesajları kişi bazında topla, cevap gerektirenlere taslak yaz.
**Çıktı:** `state/social-queue.json` + `state/taslaklar/ig-<konusma-id>.md`

**Kritik teknik not:** Instagram DM erişimi için gerekenler — Instagram **Business/Creator** hesabı → bir Facebook Sayfası'na bağlı → Meta Developer App → `instagram_manage_messages` + `pages_manage_metadata` izinleri → **App Review onayı**. Onay süreci birkaç gün sürebilir ve kullanım gerekçesini videolu anlatım ister.

Ayrıca Meta'nın **24 saat kuralı** var: kullanıcının son mesajından 24 saat sonra API ile serbest metin cevap gönderilemez. Bu yüzden `social-agent` "cevap penceresi kapanmak üzere" uyarısı üretir.

### 3.3 calendar-agent

**Girdi:** Google Calendar API + `inbox-digest.json` içinden çıkarılan tarih önerileri
**İş:** Üç şey üretir —

1. **Kayıt:** her randevu/toplantı için konu özeti, katılımcılar, yer/link
2. **Hazırlık listesi:** "bu toplantıdan önce yapılması gereken" maddeler (ilgili mail thread'lerinden ve önceki toplantı notlarından türetilir)
3. **Hatırlatma:** T−1 gün ve T−1 saat işaretleri

**Çıktı:** `state/agenda.json`

---

## 4. Veri şemaları

```jsonc
// state/inbox-digest.json
{
  "guncelleme": "2026-08-25T08:00:00+03:00",
  "toplam_okunmamis": 61,
  "maddeler": [{
    "id": "18f2a...",
    "gonderen": "Ayşe Y. <ayse@ornek.com>",
    "konu": "Sözleşme revizyonu",
    "skor": 88,
    "kategori": "aksiyon",
    "ozet": "Revize sözleşmeyi cuma 17:00'a kadar imzalı istiyor.",
    "aksiyon": "Sözleşmeyi oku ve imzala",
    "son_tarih": "2026-08-28T17:00:00+03:00",
    "tarih_ipucu": null,
    "taslak": "state/taslaklar/mail-18f2a.md"
  }]
}
```

```jsonc
// state/agenda.json
{
  "etkinlikler": [{
    "id": "evt_...",
    "baslik": "Tedarikçi görüşmesi",
    "baslangic": "2026-08-26T14:00:00+03:00",
    "yer": "Google Meet",
    "katilimcilar": ["mehmet@tedarikci.com"],
    "ana_konu": "Q4 fiyat listesi ve teslim süreleri",
    "hazirlik": [
      {"madde": "Mevcut fiyat listesini çıkar", "durum": "bekliyor", "kaynak": "mail:18f2a"},
      {"madde": "Geçen toplantı notlarını gözden geçir", "durum": "bekliyor", "kaynak": "log:2026-07-14"}
    ],
    "hatirlatma": ["T-1g", "T-1s"]
  }]
}
```

```jsonc
// state/social-queue.json
{
  "konusmalar": [{
    "platform": "instagram",
    "kisi": "@kullanici",
    "son_mesaj_zamani": "2026-08-24T23:10:00+03:00",
    "pencere_kapanis": "2026-08-25T23:10:00+03:00",
    "onem": "yuksek",
    "ozet": "İşbirliği teklifi, bütçe soruyor.",
    "taslak": "state/taslaklar/ig-9931.md",
    "durum": "onay_bekliyor"
  }]
}
```

---

## 5. Günlük akış

```
08:00  Task Scheduler → run-brief.ps1 → claude -p "/brief"
       ├─ 3 agent paralel çalışır, state/ güncellenir
       ├─ Çekirdek harmanlar → state/log/2026-08-25.md
       └─ Masaüstü bildirimi: "Sabah brifingin hazır — 3 acil madde"

13:00  hafif tarama (yalnızca skor ≥ 80 varsa bildirim)

19:00  gün kapanışı: yarının ajandası + hazırlık listesi + cevaplanmamış taslaklar
```

**Brifing formatı** — tek ses, kaynak ayrımı yok:

```
Günaydın. Bugün 3 şey seni bekliyor.

ŞİMDİ
1. Ayşe sözleşme revizyonunu cuma 17:00'a kadar istiyor. Taslak cevap hazır.
2. Yarın 14:00 tedarikçi görüşmesi var — öncesinde fiyat listesini çıkarman lazım.

BİLGİN OLSUN
- Instagram'da bir işbirliği teklifi var, cevap penceresi 9 saat sonra kapanıyor.
- 47 düşük öncelikli mail dokunulmadan bırakıldı.

ONAY BEKLEYEN 2 TASLAK  →  /kuyruk
```

---

## 6. Onay akışı (hiçbir şey onaysız gitmez)

1. Agent taslağı `state/taslaklar/` altına `.md` olarak yazar, durum `onay_bekliyor`.
2. `/kuyruk` → bekleyenleri listeler.
3. `/onayla <id>` → taslağı tam metin gösterir, **senden açık onay alır**, sonra gönderir.
4. `/duzelt <id> "..."` → taslağı revize eder, tekrar onaya sunar.

Gönderme yetkisi yalnızca Çekirdek'te. Alt agent'ların gönderim araçlarına erişimi yoktur — `.claude/agents/*.md` içinde `tools` alanı yalnızca okuma araçlarıyla sınırlanır.

---

## 7. Uygulama fazları

| Faz | İçerik | Bağımlılık | Süre |
|---|---|---|---|
| **0** | Klasör iskeleti, persona, agent tanımları, state şemaları, sahte veriyle uçtan uca test | yok | 1 oturum |
| **1** | Gmail: IMAP + uygulama şifresi, `gmail_fetch.py`, mail-agent canlı veriyle. **Tamam** — OAuth yerine IMAP seçildi: Cloud projesi/onay ekranı gerekmiyor, token 7 günde düşmüyor ve salt okuma protokol seviyesinde garanti. Gönderim bu fazda açılmadı. | Hesapta 2FA | tamam |
| **2** | Calendar entegrasyonu, hazırlık listesi üretimi, hatırlatmalar | Kendi OAuth'unu kurar (Faz 1 IMAP'e geçtiği için paylaşım yok) | 1 oturum |
| **3** | Task Scheduler + masaüstü bildirimi + brifing arşivi | Faz 1–2 | kısa |
| **4** | Onay/gönderim akışı (`/kuyruk`, `/onayla`, `/duzelt`) | Faz 1 | kısa |
| **5** | Proje hafızası: olay günlüğü, durum türetme, diğer agent'ların olay yazması | Faz 1–2 | 1 oturum |
| **6** | Telegram bot: bildirim, butonlu onay akışı (panelin uzaktan kolu) | Faz 4 | kısa |
| **7** | Birleşik panel: `sunucu.py` + tek ekran arayüz + gömülü sohbet | Faz 5 | 1–2 oturum |
| **8** | Instagram DM — Meta app, profesyonel hesap bağlama | Profesyonel Instagram hesabı | 1 oturum |

**Not (2026-09-09):** Bu varsayım artık geçerli değil. "Instagram API with Instagram Login" ile Facebook Sayfası gerekmiyor ve **kendi hesabınız için App Review de gerekmiyor** — uygulama geliştirme modundayken, uygulamada rolü olan hesabın verisine erişilebiliyor. App Review ancak başkalarının hesaplarını yöneten bir ürün yayımlarken şart. Tek gerçek koşul hesabın profesyonel (İşletme/Kreatör) olması; kişisel hesap bu API'yi kullanamıyor ve profesyonel hesaplar gizli olamıyor.

**Neden Instagram yine de sonda kaldı:** dış bir hesap türü değişikliği gerektiriyor. Diğer fazlar bittiğinde sistem zaten çalışır durumda olur; Meta onayı geldiğinde `social-agent` fişe takılır, mimaride değişiklik gerekmez.

---

## 8. Riskler ve peşinen kararlar

- **Gizlilik:** Mail ve DM içerikleri özetleme için modele gönderilir. Ham veri diskte kalır; `secrets/` ve `state/` versiyon kontrolüne girmez. Hangi hesapların taranacağı `config/`'te açıkça listelenir.
- **Instagram App Review reddi** gerçek bir ihtimal. Reddedilirse alternatif: yalnızca yorum/mention okuma (daha kolay izin) ya da bu ayağı manuel bırakmak.
- **Yanlış "önemli" sınıflaması:** İlk iki hafta agent hiçbir maili arşivlemez veya işaretlemez, sadece skorlar. Sen skorları düzelttikçe `config/onem-kurallari.md` ve `config/kisiler.md` güncellenir.
- **Token maliyeti:** Günde 3 tarama × 3 agent. Ham mail gövdeleri modele girmeden önce script tarafında kırpılır (ilk ~2000 karakter + ek listesi + thread başlıkları).
- **Bilgisayar kapalıysa** tarama olmaz. Task Scheduler "kaçırılan görevi açılışta çalıştır" seçeneğiyle kurulur.
- **Takvim yazma yetkisi:** İlk sürümde calendar-agent takvime **yazmaz**, sadece okur ve kendi kaydını tutar. Yazma yetkisi ancak skorlama güvenilir hale geldikten sonra açılır.


---

## 9. Proje hafızası

### 9.1 Temel karar: olay günlüğü, durum dosyası değil

Agent her taramada `durum.md`'yi üzerine yazarsa geçmiş kaybolur. Oysa asıl soru geçmişe
dair: "hangi adımlardan geçtim, ne yaşandı, o kararı neden verdik". Bu yüzden gerçeğin
kaynağı **append-only bir olay günlüğü**, anlık durum ise ondan **türetilen** bir görünüm.

```
projects/<proje-adi>/
├── proje.md          # kimlik kartı: amaç, paydaşlar, başarı kriteri (nadiren değişir)
├── olaylar.jsonl     # ASLA silinmez, sadece satır eklenir — gerçeğin kaynağı
├── durum.json        # olaylardan TÜRETİLİR, her taramada baştan hesaplanır
├── kararlar/         # neden böyle yaptık kayıtları (ADR mantığı)
└── notlar/           # toplantı notları, serbest metin
```

Üç kazancı: agent geçmişi **bozamaz**, sadece ekleyebilir; "üç ay önce neden böyle karar
verdik" cevaplanabilir hale gelir; `durum.json` bozulursa olaylardan yeniden inşa edilir.

### 9.2 Sabit faz yok — serbest zaman çizelgesi

**Karar:** Projelere önceden tanımlı faz yapısı dayatılmaz. Her proje farklı ilerler; sabit bir
faz listesi uydurma bir kalıp olur ve projeleri yanlış yere yerleştirir. Bunun yerine olaylar
zaman çizelgesine serbestçe kaydedilir, yapı geriye dönük kendiliğinden oluşur.

"Bu proje şu an nerede?" sorusunu faz numarası değil, üç türetilmiş sinyal cevaplar:

1. **Canlı özet** — agent her taramada son olaylara bakıp "nerede kaldık"ı iki cümleyle
   yeniden yazar (`durum.json > ozet`). Şemaya gömülü bir ilerleme çubuğundan çok daha
   doğru bilgi verir ve LLM'in zaten iyi yaptığı iştir.
2. **Aktivite şeridi** — son 12 haftanın olay yoğunluğu. Uydurulmuş bir yapı değil, olay
   günlüğünden doğrudan türeyen gerçek sinyal. "Bu proje sessizleşti"yi gösterir.
3. **Kilometre taşları** — bazı olaylar diğerlerinden ağırdır ("alternatif tedarikçiye geçildi").
   `kilometre_tasi: true` bayrağıyla işaretlenir, çizelgede kalın görünür. Önceden tanımlı
   değil, geriye dönük ortaya çıkar: projeyi altı ay sonra açtığında yalnızca kilometre
   taşlarını okuyarak hikâyeyi takip edebilirsin.

**Serbest etiketler:** Her olay `etiket` listesi taşıyabilir (`fiyat`, `hukuk`, `lojistik`).
Agent önerir, sen onaylarsın, her projede farklı olur. Uzun projelerde çizelge etikete göre
filtrelenir — "fiyat konusunda ne yaşandı" tek tıkla cevaplanır.

### 9.3 Olay tipleri

`adim_tamamlandi` · `karar_alindi` · `blokaj` · `blokaj_cozuldu` · `toplanti` · `teslim` ·
`kapsam_degisti` · `risk` · `tarih_kaydi` · `kisi_eklendi` · `not`

Tipler yalnızca ikon ve renk seçimi içindir; sıra veya ilerleme anlamı taşımaz. Listeye
uymayan bir şey için `not` kullanılır — serbest metin her zaman geçerli bir olaydır.

```jsonc
// projects/tedarikci-anlasmasi/olaylar.jsonl  (her satır bir olay)
{"t":"2026-08-20T14:30:00+03:00","tip":"blokaj","baslik":"Tedarikçi fiyat vermedi",
 "detay":"Üçüncü hatırlatmaya rağmen dönüş yok","kaynak":"mail:18f2a","etki":"yuksek",
 "etiket":["fiyat"]}
{"t":"2026-08-24T09:15:00+03:00","tip":"blokaj_cozuldu","ref":"2026-08-20T14:30:00+03:00",
 "baslik":"Alternatif tedarikçiye geçildi","kaynak":"ig:9931","etiket":["fiyat"],
 "kilometre_tasi":true}
```

```jsonc
// projects/tedarikci-anlasmasi/durum.json  (türetilmiş — elle düzenlenmez)
{
  "ozet": "İlk tedarikçi fiyat vermedi, alternatife geçildi. İki teklifin karşılaştırılması bekleniyor.",
  "ozet_guncelleme": "2026-08-25T08:00:00+03:00",
  "sonraki_adim": "Fiyat listesini karşılaştır",
  "acik_blokajlar": 1,
  "son_hareket": "2026-08-24T09:15:00+03:00",
  "acik_gun": 42,
  "olay_sayisi": 23,
  "etiketler": ["fiyat","hukuk","lojistik"],
  "aktivite_12h": [1,3,5,2,0,0,4,7,2,1,4,3]
}
```

### 9.4 Sistemi gerçekten tek varlık yapan bağ

`proje-agent` dördüncü bir uzuv değil, diğer üçünün **ortak belleği**. Bağlantı iki yönlü:

- `mail-agent` bir mailde "sözleşme imzalandı" gördüğünde ilgili projeye `teslim` olayı düşürür
- `calendar-agent` toplantı bittiğinde `toplanti` olayı + karar özeti yazar
- `social-agent`'a gelen işbirliği teklifi yeni bir proje taslağı doğurur
- Ters yönde: bir projenin `sonraki_adim`'ı, sabah brifingindeki aksiyon maddesi olur

Her olay `kaynak` alanı taşır (`mail:18f2a`, `takvim:evt_...`, `ig:9931`) — panoda tıklanınca
kaynağa gidilir, izlenebilirlik kopmaz.

### 9.5 Otomatik olay çıkarımının güvenliği

Yanlış olay yazmak geçmişi kirletir. Bu yüzden agent'ların ürettiği olaylar
`"onaylanmamis": true` bayrağıyla yazılır ve brifingde sorulur:
"Tedarikçi projesine 'sözleşme imzalandı' olayını ekleyeyim mi?"
Onaylanana kadar zaman çizgisinde soluk gösterilir, `durum.json` hesabına katılmaz.
Projeyi sen açarsın; agent kendi başına yeni proje yaratmaz, yalnızca önerir.

---

## 10. Arayüz — "Tek Ağız" (Broadsheet)

Arayüz bir gösterge tablosu değil, **bir konuşma**. Claude Design'da üç yön çizildi
(Sabah Baskısı · Tezgâh · Tek Ağız) ve **1c "Tek Ağız"** seçildi:

> Ajan yok, sadece kâtip var. Brifing konuşma olarak gelir, onaylar sohbetin içinde
> satır satır verilir. Solda ince bir künye ajanların hâlâ orada olduğunu söyler.

Tasarım kaynağı: `tasarım/Kâtip - Ekran Yönleri.dc.html` (satır 252–346).
Tasarım sistemi **Broadsheet** — gazete dizgisi: Source Serif 4, kağıt zemini,
camgöbeği ve magenta noktasal vurgu, **kutu ve çizgi yok**; hiyerarşi seriften ve
boşluktan gelir.

```
┌──────────────┬───────────────────────────────────────────┐
│ V Vellum     │  PAZARTESİ 07:40           şimdi tara     │
│              │                                           │
│ KÜNYE        │  Günaydın. Gün tek bir işin etrafında     │
│ ● Posta   4  │  dönüyor: Kayalar sözleşmesi 17:00'de…    │
│ ● Mesaj   7  │                                           │
│ ● Ajanda  3  │  ───────────────────────────────────────  │
│              │  ONAYINIZI BEKLEYEN 2 ŞEY                 │
│ BUGÜN        │  Ayşe — "Revize takvimi…"  [Onayla][Değiş]│
│ 11:00 Kayalar│  @marka — kibar ret        [Onayla][Değiş]│
│ 14:30 Diş    │  ───────────────────────────────────────  │
│ 18:00 Ekip   │                        siz yazdınız ▸     │
│              │  kâtibin cevabı…                          │
│ Vellum 139   │                                           │
│ kayıt okudu  │  [ Vellum'a yazın…            Söyle ]    │
│ Defteri aç → │                                           │
└──────────────┴───────────────────────────────────────────┘
```

**Brifing konuşmanın ilk mesajı.** Ayrı bir kutu değil: panel açıldığında bugünün
`state/log/<tarih>.md` kaydı varsa kâtibin açılış turu olarak görünür. İlk paragraf
"gün cümlesi" olarak büyük punto, gerisi normal.

**Onaylar akışın içinde.** Taslak metni satırda görünür, tek tıkla onaylanır. Metin
satıra sığmıyorsa kırpılır; `Değiştir` tam metni dialogda açar. Onay sonucu konuşmaya
kâtibin cevabı olarak düşer.

**Künye** sol kolonda: üç ajanın sayıları (Posta/Mesaj camgöbeği, Ajanda proses sarısı),
bugünün saatleri, ve "Vellum son taramada N kayıt okudu, M'ini size getirdi" cümlesi.
Ajanlar görünmez ama varlıkları burada duyulur.

**Defter** — gösterge tablosu buraya taşındı. Künyeden veya "Defteri aç" ile girilir,
"← Konuşmaya dön" ile çıkılır; konuşma durumu kaybolmaz. İçinde: Projeler (canlı özet +
12 haftalık aktivite şeridi → tıklayınca serbest zaman çizelgesi, kilometre taşları
belirgin, onaylanmamış olaylar soluk, etiket süzgeci), Posta, Mesaj, Ajanda, Arşiv.

**Karanlık tema yok.** Broadsheet readme'si "bu sistem koyu yüzey göstermez" diyor;
tasarıma sadık kalmak için tek kağıt teması kullanılıyor. Bilerek verilmiş bir karar.

**Mobil**: 760px altında künye yatay şeride iner, onaylar dikey yığılır, düğmeler 44px.

Dosyalar: `panel/panel.html` (yerleşim), `panel/panel.js` (çizim ve durum),
`panel/_ds/broadsheet/styles.css` (tasarım sistemi, olduğu gibi kopyalandı).

### 10.0 Karar: Claude Code yerine Claude API

Agent'lar başlangıçta Claude Code'un subagent sistemine dayanıyordu. Bu, projeyi CLI'ya ve
onun çalışma alanı güven modeline bağımlı kılıyordu. **Agent katmanı Claude API üzerine
taşındı** (`panel/beyin.py`):

- Agent tanımları yine `.claude/agents/*.md` dosyalarından okunur — YAML ön maddesi ayıklanıp
  sistem istemi olarak verilir. Yani tanımlar tek yerde kalır, iki kopya yok.
- Dosya araçları (`dosya_oku`, `dosya_listele`, `dosya_yaz`, `dosya_ekle`) Python'da tanımlanır
  ve SDK'nın tool runner'ı döngüyü sürer.
- Yetki sınırı artık kodda: proje kökü dışına çıkılamaz, `secrets/` okunamaz, yazma yalnızca
  `state/`, `projects/`, `config/` altında serbest, `olaylar.jsonl` yalnızca `dosya_ekle` ile
  büyür. Sohbet salt okunur araçlarla çalışır.
- Model `claude-sonnet-5`, adaptif düşünme açık. Alt agent'lar `effort: medium` ile çalışır;
  Çekirdek harmanlama ve sohbette varsayılan efor kullanılır.

Tek bağımlılık: `pip install anthropic`. API anahtarı `ANTHROPIC_API_KEY` ortam
değişkeninden veya `secrets/api_key.txt` dosyasından okunur (ikincisi `.gitignore`'da).

### 10.1 Mimari sonuç: statik HTML yetmiyor

Panelden sohbet edilip onay verildiği için arayüz artık salt okunur değil — Claude'u
çağırması ve mail gönderebilmesi gerekiyor. Bu yüzden altına küçük bir **yerel sunucu**
girer. Yalnızca `127.0.0.1`'e bağlanır, dışarı açılmaz.

| Uç nokta | İş |
|---|---|
| `GET /api/durum` | `state/` + `projects/` JSON'larını tek pakette döner |
| `POST /api/sohbet` | `claude -p` çağırır, cevabı SSE ile akıtır |
| `POST /api/onay/<id>` | Taslağı gönderir, `olaylar.jsonl`'a kayıt düşer |
| `POST /api/olay/<proje>` | Onaylanmamış olayı onaylar veya reddeder |
| `POST /api/tarama` | Elle tarama tetikler ("şimdi bak") |

Yaklaşık 150 satır Python (FastAPI). Build adımı, frontend framework, veritabanı yok.
Sunucu yalnızca dosya okur ve `claude` çağırır; iş mantığı agent'larda kalır.

---

## 11. Etkileşim kanalı

Panel tek arayüz, ama sistemin sana **ulaşması** da gerekiyor — hatırlatma, acil mail, onay
isteği. Bunlar sen bilgisayar başında değilken oluyor.

Bu yüzden Telegram bot ayrı bir pencere değil, **panelin uzaktan kolu**: aynı sunucuya
bağlanır, aynı `olaylar.jsonl`'a yazar. Evde panel, dışarıda Telegram — tek beyin, iki erişim.

| Kanal | Rolü |
|---|---|
| **Panel** | Ana arayüz. Görsel genel bakış, proje geçmişi, gömülü sohbet, onay. |
| **Telegram** | Uzaktan erişim. Anlık bildirim + butonlu hızlı onay. Ücretsiz API, hızlı kurulum. |
| Terminal | Yedek/bakım kanalı. Panel çalışmıyorsa veya derin dosya işi gerekiyorsa. |

Değerlendirilip elenenler: e-posta ile kendine yazma (zaten boğulduğun kanala yük bindirir),
WhatsApp (Business API zorunlu, ücretli, onay süreci — Telegram'ın verdiğini daha zor yoldan verir).

**Telegram akışı:**

```
08:00  bot → brifing mesajı + [Kuyruğu aç] [Ajanda] [Projeler]
       ↓ "Kuyruğu aç"
       taslak metni + [Onayla] [Düzelt] [Geç]
       ↓ "Onayla"
       POST /api/onay/<id> → mail gider · olay kaydı düşer · panel anında güncellenir
```

**Güvenlik:** Bot yalnızca senin chat id'ne cevap verir (whitelist). Token `secrets/` altında.
Sunucu yalnızca localhost'a bind edilir. Gönderim komutlarını bot değil Çekirdek yürütür —
bot ve panel yalnızca arayüzdür.

---

## 12. Kural motoru — modelin işi neresi (2026-09-08)

İlk canlı tarama ölçümü: `mail-agent` 32 mailin gövdesini tek turda okudu, **104.192 giriş +
16.000 çıkış token**, süre dakikalar. Oysa gelen kutusundaki 32 mailin 30'u iş ilanı
bülteniydi. Model, bültenleri okumak için çalıştırılıyordu.

**Karar:** `config/onem-kurallari.md` zaten bir kural tablosu — VIP +40, tarih +25,
bülten −50. Bunları modele hesaplatmanın hiçbir karşılığı yok. Skorlama `panel/skorlama.py`
içine, deterministik Python'a taşındı. Model yalnızca eşiği (ham skor 40) geçen maillere
özet, aksiyon ve taslak yazar.

### 12.1 Bülten tespiti: `List-Unsubscribe`

Toplu gönderim yapan her mail bu başlığı taşır; kesin sinyaldir ve sıfır token harcar.
Kutudaki 32 mailin 23'ü taşıyordu.

Ama iki tür otomatik mail vardır ve ayrımı önemlidir:

- **Bülten** — `List-Unsubscribe`/`List-Id` taşır. Gerçek bir mülakat daveti abonelikten
  çıkma bağlantısıyla gelmez, o yüzden bülten hiçbir koşulda "ilerleme" sayılmaz.
- **İşlem maili** — `noreply@` türü adres. Başvuru sistemleri (ATS) mülakat davetini de
  böyle gönderir; içeriğine bakılır.

Bu ayrım olmadan, gövdesinde "Interview" geçen bir Glassdoor bülteni 60 puan alıyordu.

### 12.2 İçerik sinyalleri yalnızca size yazılmış maillerde sayılır

Pazarlama metni her zaman tarih ("son 3 gün"), fiyat ("199 TL") ve soru ("kaçırmak ister
misiniz?") taşır. Bunlar sayılınca toplu gönderim cezasını geri kapatıyor ve bir indirim
maili "aksiyon" olarak brifingin başına çıkıyordu — ölçtük, çıkıyordu. Toplu gönderimde
tarih/para/soru hesaplanmaz; VIP'ten geliyorsa ya da başvuru ilerlemesiyse hesaplanır.

### 12.3 İş başvurusu ayrımı

Kullanıcının açık tercihi: başvuru **onayları** ("başvurunuz alındı") önemli değil,
şirketten gelen **ilerleme** (mülakat, teklif, değerlendirme sonucu) önemli. Ayrım
gönderene değil konuya bakar — aynı adresten ikisi de gelebilir.

### 12.4 Kullanıcı kimliği koda gömülmez

"Doğrudan sana yazılmış" ve "CC" sinyalleri kullanıcının adresini bilmeyi gerektirir. Adres
çalışma anında `secrets/.env`'den okunur; çözülemezse bu iki sinyal tahmin edilmez, atlanır.
Testler uydurma adreslerle yazılır — kimin makinesinde çalıştığından bağımsız geçmeli.

---

## 13. Modele ne gösterildiği (2026-09-08)

Skorlama ucuzladıktan sonra ikinci bir israf kalmıştı: ajana "gövdeleri
`state/raw/gmail.json` içinde bul" deniyordu. Ajan 100 KB'lık dosyanın tamamını okuyor,
**tool döngüsünün her turunda o içerik yeniden gönderiliyordu**. Üstüne 19,5 KB'lık digest'i
baştan yazıyordu — tek başına ~5.000 çıktı tokenı. İki mail özetlemek ~$0,24 tutuyordu.

**Üç karar:**

1. **Ajana yalnızca işleyeceği veri verilir.** `state/ozetlenecek.json` — eşiği geçen
   maillerin gövdeleriyle birlikte. İki mail için 1,2 KB.
2. **Ajan büyük dosyayı geri yazmaz.** Özetler küçük bir `state/ozetler.json`'a yazılır,
   digest'le birleştirmeyi sistem yapar. Model 19 KB'lık dosyayı yeniden yazarken bir alanı
   bozamaz; çıktı tokenı da 5.000'den ~300'e iner.
3. **Çekirdek ve `proje-agent` süzülmüş görünüm okur.** `state/brifing-girdisi.json`
   yalnızca eşiği geçenleri taşır, elenenler tek bir sayıdır. Digest'in tamamı panelin veri
   kaynağı olarak kalır — kullanıcı elenen maili de görebilmeli.

Ölçülen sonuç: mail özeti başına ~$0,236 → ~$0,005.

**Genel ilke:** bir ajanın okuduğu her dosya, döngünün her turunda yeniden faturalanır.
Ajanın girdisini dar tutmak, ajanı kısıtlamaktan daha etkilidir.

---

## 14. Canlı izleme (2026-09-08)

Tarama elle başlatılıyordu; gün içinde gelen önemli bir mailden ancak "şimdi tara"ya
basınca haberdar olunuyordu.

- `imaplib` Python 3.12'de IDLE desteklemiyor (3.13'te eklendi), bu yüzden **60 saniyelik
  yoklama**. IMAP sorgusu ücretsiz olduğu için maliyeti yok, gecikme en fazla bir dakika.
- İzleyici **model çağırmaz**: kural motoruyla puanlar, eşiği geçerse bildirir. Gün boyu
  izleme bedavadır.
- Yeni mail yalnızca bildirilmez, **sisteme de düşer**: `gmail.json`, `arsiv.jsonl` ve
  digest güncellenir. Bildirim tek başına yetmez — mail Posta listesinde de görünmeli.
- Bildirim kendi çizdiğimiz **Broadsheet kartıdır** (`scripts/kart.py`), Windows'un kutusu
  değil. Ayrı bir süreçte açılır: Tkinter çağrıları tek iş parçacığında kalmak zorunda,
  sunucunun içinden pencere açmak kırılgan olurdu. Kart çizilemezse Windows bildirimine
  düşülür; izleyici hiçbir durumda durmaz.
- UID koruması: kayıtlı UID kutununkinden büyükse geçersiz sayılıp kutunun sonuna hizalanır.
  Bu, kutu yeniden oluşturulduğunda (UIDVALIDITY değişimi) sistemi sağlam tutar.

---

## 15. Görünürlük (2026-09-08)

Kredi bitmesi gibi apaçık bir hatayı bulmak yarım saat aldı, çünkü hata hiçbir yere
yazılmıyordu — yalnızca tarayıcıya dönüyordu.

- Her taramanın sonucu (süre, adımlar, ajan çıktıları, hata) `state/log/taramalar.jsonl`.
- API hataları düz Türkçeye çevrilir: kredi bitti, anahtar geçersiz, hız sınırı, ağ yok.
- Tarama durumu sunucuda tutulur; panel yoklar. Sayfa yenilense ya da başka sekmeden
  bakılsa da taramanın sürdüğü ve hangi adımda olduğu görünür.
- Brifingin üstünde üretim damgası var. Damgasız gösterilen bir brifing, sabahtan kalma
  olduğu hâlde yeni taramanın çıktısı sanılıyordu — bunu bizzat yaşadık.
- Panel 20 saniyede bir kendini yoklar. Yazarken, okurken ya da bir işlem beklerken
  yenileme ertelenir; kullanıcının elinden iş alınmaz.
- Sohbet `state/sohbet.jsonl` içinde saklanır: sayfa yenilenince konuşma kaybolmaz.

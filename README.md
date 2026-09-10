# Vellum

Kişisel asistan sistemi. Gmail ve Instagram DM'lerini okur, önemli olanı ayıklar,
cevap taslakları hazırlar ve projelerin geçmişini tutar. **Hiçbir şey onaysız gönderilmez.**

Yerel çalışır, dosya tabanlıdır, Claude API üzerinden düşünür ve tek bir web paneli
üzerinden kullanılır.

> Durum: geliştirme aşaması. Gmail bağlantısı (IMAP, salt okuma), kural tabanlı skorlama,
> takvim, canlı izleme ve masaüstü bildirimi çalışıyor. Instagram çekicisi hazır, hesap
> bağlanmayı bekliyor; Google Takvim bağlantısı henüz kurulmadı. Gönderim kapalı —
> onaylar yalnızca kaydedilir.

---

## Ne yapıyor

- **Posta** — her maile önem skoru verir, aksiyon gerektirenleri çıkarır, cevap taslağı yazar
- **Mesaj** — Instagram DM'lerini eler ve özetler, cevap penceresi kapanmadan uyarır
- **Defter** — projelerin olay geçmişini tutar: hangi adımdan geçildi, ne yaşandı,
  hangi karar neden alındı

---

## Tasarım kararları

Bu projeyi diğer "AI asistan" denemelerinden ayıran şey, birkaç bilinçli kısıt:

**Tek varlık, çok uzuv.** Üç ajan var ama kullanıcı için tek bir varlık. Alt ajanlar
kullanıcıya hitap etmez, kendi üslubunu kullanmaz; yalnızca yapılandırılmış veri üretir.
Onu insan diline çeviren tek yer Çekirdek'tir. Üç ayrı rapor değil, harmanlanmış tek metin.

**Geçmiş silinmez.** Proje hafızası append-only bir olay günlüğüdür (`olaylar.jsonl`).
Anlık durum ondan **türetilir**. Ajan geçmişi bozamaz, yalnızca ekleyebilir; "üç ay önce
neden böyle karar verdik" sorusu cevaplanabilir kalır.

**Sabit faz yok.** Projelere önceden tanımlı aşama listesi dayatılmaz — her proje farklı
ilerler. "Bu proje nerede?" sorusunu üç türetilmiş sinyal cevaplar: canlı özet, son 12
haftanın aktivite şeridi, ve kilometre taşları. Faz çubuğu "sağlıklı ilerliyor" yanılsaması
üretir; aktivite şeridi projenin 12 gündür sessiz olduğunu saklamaz.

**Onaysız gönderim yok.** Gönderme yetkisi yalnızca Çekirdek'tedir; alt ajanların gönderim
aracı yoktur. Ajanların otomatik çıkardığı olaylar da `onaylanmamis: true` taşır —
kullanıcı onaylayana kadar özete ve sayıma katılmaz.

**Asistan sizin adınıza taahhüt vermez.** Tarih sözü, fiyat, kabul, red — hiçbiri taslakta
geçmez. Taslak karşı tarafı oyalamadan bekletir; taahhüdü siz verirsiniz.

**Yetki sınırı kodda, istemde değil.** "Şunu yapma" cümlelerine güvenilmez: araçların
kendisi engeller. Proje kökü dışına çıkılamaz, `secrets/` okunamaz, yazma yalnızca üç
klasörde serbesttir, olay günlüğünün üzerine yazılamaz.

**Kural işi kurala, yargı işi modele.** Önem skorlaması bir kural tablosudur — VIP +40,
tarih +25, bülten −50. Bunu modele hesaplatmak hem pahalı hem yavaştı: 32 maili skorlatmak
tek turda 104.000 giriş tokenıydı ve dakikalar sürüyordu. Skorlama artık Python'da
(`panel/skorlama.py`); model yalnızca eşiği geçen birkaç maile özet ve taslak yazar.

**Modele az göster.** Bir ajanın okuduğu her dosya, tool döngüsünün her turunda yeniden
gönderilir. Ajana "gövdeleri `gmail.json` içinde bul" demek, iki mail için 100 KB'lık
dosyanın birkaç kez faturalanması demekti. Ajan artık yalnızca işleyeceği maillerin
bulunduğu küçük bir dosya görür ve büyük digest'i geri yazmaz — birleştirmeyi sistem yapar.
Mail özeti başına maliyet ~$0,24'ten ~$0,005'e indi.

**Bülten ile işlem maili ayrıdır.** `List-Unsubscribe` başlığı taşıyan hiçbir şey mülakat
daveti sayılmaz; bir davet abonelikten çıkma bağlantısıyla gelmez. Ama `noreply@` adresinden
gelen bir başvuru sistemi bildirimi sayılabilir. Bu ayrım olmadan, gövdesinde "interview"
geçen bir iş ilanı bülteni öne çıkıyordu. Aynı sebeple toplu gönderimde tarih/fiyat/soru
sinyalleri hesaplanmaz: pazarlama metni hepsini taşır ve toplu gönderim cezasını kapatır.

**Kimlik koda gömülmez.** "Doğrudan sana yazılmış" sinyali kullanıcının adresini bilmeyi
gerektirir; o adres çalışma anında `secrets/.env`'den okunur. Çözülemezse sinyal tahmin
edilmez, atlanır. Program başka bir hesapla kurulduğunda kendiliğinden o kullanıcıya
göre çalışır.

---

## Mimari

```
                    ┌───────────────────────────┐
     kullanıcı ◄──► │   ÇEKİRDEK  (tek ses)     │
                    └────┬───────┬────────┬─────┘
                         │       │        │
                   ┌─────▼──┐ ┌──▼────┐
                   │ Posta  │ │ Mesaj │
                   └─────┬──┘ └──┬────┘
                         └───────┘
                                 │
                      ┌──────────▼──────────┐
                      │  state/ + projects/ │
                      │    ortak hafıza     │
                      └─────────────────────┘
```

Proje ajanı üçüncü bir uzuv değil, diğer ikisinin **ortak belleğidir**: her ajan olayları
ilgili projeye düşürür, proje geçmişi kendiliğinden oluşur.

Veri çekme işi ajanlara ait değildir — fetch scriptleri ham veriyi `state/raw/` altına
bırakır, ajanlar yalnızca onu okur. Bu sayede hiçbir ajanın ağa erişimi yoktur.

Mail tarafında araya bir kat daha girer:

```
gmail_fetch.py  →  state/raw/gmail.json  →  skorlama.py (kural, modelsiz)
                                                  ↓
                                    inbox-digest.json   (panelin gördüğü: hepsi)
                                    brifing-girdisi.json (modelin gördüğü: eşiği geçenler)
                                                  ↓
                                            mail-agent (özet + taslak)
```

Kural motoru elemeyi yapar, model yalnızca kalanla ilgilenir. Panel elenen maili de
gösterir — skor neyin öne çıkacağını belirler, neyin görüneceğini değil; elenen bir maili
görebilmek skorlamayı düzeltmenin tek yoludur.

---

## Arayüz

Arayüz bir gösterge tablosu değil, bir konuşmadır. Brifing ayrı bir kutu olarak değil,
kâtibin günün ilk mesajı olarak gelir; onaylar sohbetin içinde satır satır verilir.

```
┌──────────────┬────────────────────────────────────┐
│ V Vellum     │  PAZARTESİ 07:40      şimdi tara   │
│              │                                    │
│ KÜNYE        │  Günaydın. Gün tek bir işin        │
│ ● Posta   4  │  etrafında dönüyor: ...            │
│ ● Mesaj   7  │  ────────────────────────────────  │
│              │  ONAYINIZI BEKLEYEN 2 ŞEY          │
│              │  Ayşe — "..."  [Onayla] [Değiştir] │
│ BUGÜN        │  ────────────────────────────────  │
│ 11:00 Kayalar│                  siz yazdınız ▸    │
│ 14:30 Diş    │  kâtibin cevabı...                 │
│              │                                    │
│ Defteri aç → │  [ Vellum'a yazın…        Söyle ]  │
└──────────────┴────────────────────────────────────┘
```

Yerleşim [Claude Design](https://claude.ai/design)'da hazırlandı; öğelerin görünüşü
**Microsoft Fluent 2 Web** — Segoe UI, beyaz yüzey, 4 px yarıçap, `#0f6cbd` marka rengi,
girdilerde odakta marka alt şeridi, kartlarda yükseklik gölgesi.

Proje önce **Broadsheet** (gazete dizgisi, Source Serif 4, kutu yok) ile çizilmişti;
tasarım dili Fluent 2 ile değiştirildi. Broadsheet stylesheet'i `tasarım/` altındaki
`.dc.html` kaynakları için diskte duruyor, panel artık onu yüklemiyor.

Gösterge tablosu (projeler, zaman çizelgesi, arşiv) **Defter** görünümünde durur.

---

## Kurulum

Gereken: Python 3.12.

```bash
pip install anthropic pypdf
```

API anahtarını `.env` dosyasına yazın:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Anahtar sırayla şuralarda aranır, ilk bulunan kullanılır: ortam değişkeni → `.env` →
`secrets/.env` → `secrets/api_key.txt`.

### Gmail bağlantısı

Bağlantı IMAP + **Google Uygulama Şifresi** ile kurulur — OAuth, Cloud projesi ve
onay ekranı yoktur. Hesapta iki adımlı doğrulama açık olmalı; şifreyi
[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) üretir.

`secrets/.env` dosyasına yazın:

```
GMAIL_ADRES=...@gmail.com
GMAIL_UYGULAMA_SIFRESI=xxxxxxxxxxxxxxxx
```

Bağlantıyı diske hiçbir şey yazmadan sınamak için:

```bash
python scripts/gmail_fetch.py --kuru
```

Kutu IMAP'te `readonly` açılır: okundu bayrağı bile değişmez, gönderim yolu yoktur.
Her taramada gelen kutusunun son 3 günü, en fazla 50 mail çekilir; gövdeler 2000
karaktere kırpılır. Okunabilir ve 5 MB altındaki ekler `state/raw/ekler/` altına iner.

Panelden "şimdi tara" dendiğinde bu çekme adımı kendiliğinden çalışır. Çekme başarısız
olursa tarama durmaz — ajanlar eldeki son veriyle devam eder, hata adım listesinde görünür.

### Instagram DM bağlantısı

Hesabınızın **profesyonel** (İşletme veya Kreatör) olması şart — kişisel hesap bu API'yi
kullanamaz. Facebook Sayfası gerekmez, kendi hesabınız için App Review de gerekmez.

1. [developers.facebook.com](https://developers.facebook.com) → yeni uygulama → **Instagram**
   ürünü ekleyin, "API setup with Instagram business login" bölümüne girin.
2. Instagram hesabınızı uygulamaya bağlayın (uygulamada rolünüz olmalı).
3. **OAuth Redirect URI** olarak `http://localhost:8788/` ekleyin.
4. Uygulama kimliğini ve gizli anahtarı `secrets/.env` dosyasına yazın:

```
IG_APP_ID=...
IG_APP_SECRET=...
```

5. Hesabı bağlayın — tarayıcı açılır, izin verirsiniz, token `secrets/` altına yazılır:

```bash
python scripts/instagram_fetch.py --baglan
```

Token 60 gün geçerlidir ve her taramada günde bir kez kendiliğinden tazelenir. Bağlantı
kurulmadıysa tarama Instagram adımını sessizce atlar — kurulmamış bir kaynak hata değildir.

Meta'nın 24 saat kuralı **okumayı değil göndermeyi** kısıtlar: karşı tarafın son mesajından
24 saat sonra API ile serbest metin gönderilemez. Vellum zaten göndermiyor.

Paneli başlatın:

```bash
python panel/sunucu.py
```

Tarayıcıda `http://127.0.0.1:8787`. Sunucu yalnızca `127.0.0.1`'e bağlanır, dışarı açılmaz.

Demo verisini tazelemek için (mevcut proje günlüklerinin üzerine yazar):

```bash
python scripts/seed_ornek_veri.py
```

---

## Klasör yapısı

```
├── CLAUDE.md              Çekirdek talimatları
├── PLAN.md                sistem planı ve kararların gerekçeleri
├── .claude/agents/        üç ajan tanımı (hem belge hem yapılandırma)
├── config/                persona, skorlama rubriği, kişi listeleri
├── state/                 ortak hafıza: digest'ler, taslaklar, brifing arşivi
├── projects/              proje hafızası: olaylar.jsonl + durum.json
├── panel/
│   ├── sunucu.py          yerel sunucu + canlı izleyici (standart kütüphane)
│   ├── beyin.py           Çekirdek + ajanlar (Claude API, tool use)
│   ├── skorlama.py        kural motoru — önem skorlaması, modelsiz
│   ├── panel.html         arayüz yerleşimi
│   ├── panel.js
│   └── _ds/fluent2/      tasarım sistemi (Fluent 2 token'ları)
└── scripts/
    ├── gmail_fetch.py      Gmail → state/raw/gmail.json (IMAP, salt okuma)
    ├── instagram_fetch.py  Instagram DM → state/raw/instagram.json
    ├── izleyici.py         canlı izleyici: yeni maili yakalar, bildirir
    ├── kart.py             Fluent bildirim kartı (masaüstü pop-up)
    ├── test_skorlama.py    kural motorunun birim testleri
    └── seed_*.py           demo verisi
```

---

## Önem skorlaması

Mail önemi kural tabanlı bir rubrikle hesaplanır. Rubrik `config/onem-kurallari.md`
içinde belgelenir, `panel/skorlama.py` içinde uygulanır — **model çağrılmaz**. Taban 30 puan:

| Sinyal | Etki |
|---|---|
| Gönderen VIP listesinde | +40 |
| Gönderen gürültü listesinde | −40 |
| Doğrudan size yazılmış | +20 |
| Yalnızca CC'desiniz | −15 |
| İçinde tarih veya son tarih var | +25 |
| Para, fatura, sözleşme, hukuki | +30 |
| Doğrudan soru var | +15 |
| Bülten / pazarlama / otomatik | −50 |
| İş başvurusu **onayı** ("başvurunuz alındı") | −40 |
| Şirketten **ilerleme** (mülakat, teklif, sonuç) | +45 |

Eşikler: ham skor ≥70 aksiyon, 40–69 bilgi, <40 gürültü. **Eşiğin altındaki mail modele
hiç gösterilmez** — panelde durur, ama özet için kredi harcanmaz.

Son iki satır kullanıcının açık tercihidir: başvuru onayları önemli değil, şirketten gelen
ilerleme önemli. Ayrım gönderene değil konuya bakar — aynı adresten ikisi de gelebilir.

Sinyal toplamı 100'ü aşabilir. **Ham toplam saklanır**, gösterilen skor 0–100'e kırpılır,
sıralama daima ham skora göre yapılır — aksi halde 140 puanlık bir sözleşme maili ile
105 puanlık bir fatura maili ekranda aynı görünürdü.

---

## Yol haritası

| Faz | İçerik | Durum |
|---|---|---|
| 0 | İskelet, ajan tanımları, uçtan uca akış | tamam |
| 1 | Gmail entegrasyonu (IMAP fetch, salt okuma) | tamam |
| 2 | Google Takvim entegrasyonu | kapsam dışı — Takvim sayfası yerel veriyle çalışıyor |
| 3 | Canlı izleme + masaüstü bildirimi | tamam |
| 4 | Onay ve gönderimin canlıya alınması | bekliyor |
| 5 | Proje hafızası | tamam |
| 6 | Telegram botu — panelin uzaktan kolu | bekliyor |
| 7 | Panel arayüzü | tamam |
| 8 | Instagram DM (profesyonel hesap) | kısmen — çekici hazır, hesap bağlanmadı |

---

## Bilinen sınırlar

- Instagram DM için hesabın **profesyonel** (İşletme/Kreatör) olması şart; kişisel hesap bu
  API'yi kullanamaz ve profesyonel hesaplar gizli olamaz. Kendi hesabınız için App Review
  gerekmez. Meta'nın 24 saat kuralı okumayı değil göndermeyi kısıtlar — karşı tarafın son
  mesajından 24 saat sonra serbest metin gönderilemez.
- Yalnızca **eşiği geçen** maillerin içeriği modele gönderilir; gerisi diski hiç terk
  etmez. Ham veri, digest'ler, taslaklar, bildirimler ve sohbet kaydı versiyon kontrolüne
  girmez — `.gitignore` bunları kapsar.
- Tarama, bağlı kaynak ve eşiği geçen mail sayısına göre 2–4 API çağrısıdır. Kaynağı
  bağlı olmayan ajan hiç çağrılmaz; özetlenecek mail yoksa mail ajanı da çağrılmaz.
- Canlı izleme **model çağırmaz**: kural motoru puanlar, bildirim düşer. Özet ve taslak
  yalnızca siz istediğinizde üretilir.
- Token kullanımı henüz kaydedilmiyor; maliyet ölçümleri dosya boyutlarından hesaplanan
  tahminlerdir.
- Taranmış (görüntü) PDF eklerinden metin çıkmaz; sistem bu durumda tahmin yürütmez,
  kullanıcıya bildirir.
- Karanlık tema yoktur: Fluent 2'nin nötr rampası buna elverir ama uygulanmadı; tek
  açık tema var.
- Bildirim kartı Windows Bildirim Merkezi'ne iz bırakmaz — ekran başında değilken kaçırılan
  kart orada bulunamaz, ama panelde bildirim listesinde durmaya devam eder.
- Masaüstü kartının köşesi diktir: Tkinter'da `overrideredirect` pencere yuvarlatılamıyor,
  paneldeki kartlar 8 px yarıçaplı olduğu hâlde bu kart öyle değil.
- Canlı izleme panel sunucusuyla birlikte çalışır; panel kapanınca izleme de durur.

---

## Not

Proje önceki çalışma adlarıyla (*Edirnekapı*, *Kâtip*) geliştirildi; tasarım kaynak
dosyaları (`tasarım/`) hâlâ o adı taşıyor — Claude Design'dan geldikleri hâlleriyle
duruyorlar.

Ayrıntılı mimari dokümanı: `Vellum - Yapi Dokumani.docx`

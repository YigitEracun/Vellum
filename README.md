# Vellum

Kişisel asistan sistemi. Gmail, Instagram DM ve Google Takvim'i okur, önemli olanı ayıklar,
cevap taslakları hazırlar ve projelerin geçmişini tutar. **Hiçbir şey onaysız gönderilmez.**

Yerel çalışır, dosya tabanlıdır, Claude API üzerinden düşünür ve tek bir web paneli
üzerinden kullanılır.

> Durum: geliştirme aşaması. Ajan katmanı, proje hafızası ve panel çalışıyor;
> Gmail / Takvim / Instagram bağlantıları henüz kurulmadı — sistem şu an sahte veriyle
> uçtan uca çalışabilir durumda.

---

## Ne yapıyor

- **Posta** — her maile önem skoru verir, aksiyon gerektirenleri çıkarır, cevap taslağı yazar
- **Mesaj** — Instagram DM'lerini eler ve özetler, cevap penceresi kapanmadan uyarır
- **Ajanda** — randevuların ana konusunu özetler, **öncesinde yapılması gerekenleri** listeler
- **Defter** — projelerin olay geçmişini tutar: hangi adımdan geçildi, ne yaşandı,
  hangi karar neden alındı

---

## Tasarım kararları

Bu projeyi diğer "AI asistan" denemelerinden ayıran şey, birkaç bilinçli kısıt:

**Tek varlık, çok uzuv.** Dört ajan var ama kullanıcı için tek bir varlık. Alt ajanlar
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

---

## Mimari

```
                    ┌───────────────────────────┐
     kullanıcı ◄──► │   ÇEKİRDEK  (tek ses)     │
                    └────┬───────┬────────┬─────┘
                         │       │        │
                   ┌─────▼──┐ ┌──▼────┐ ┌─▼───────┐
                   │ Posta  │ │ Mesaj │ │ Ajanda  │
                   └─────┬──┘ └──┬────┘ └─┬───────┘
                         └───────┴────────┘
                                 │
                      ┌──────────▼──────────┐
                      │  state/ + projects/ │
                      │    ortak hafıza     │
                      └─────────────────────┘
```

Proje ajanı dördüncü bir uzuv değil, diğer üçünün **ortak belleğidir**: her ajan olayları
ilgili projeye düşürür, proje geçmişi kendiliğinden oluşur.

Veri çekme işi ajanlara ait değildir — fetch scriptleri ham veriyi `state/raw/` altına
bırakır, ajanlar yalnızca onu okur. Bu sayede hiçbir ajanın ağa erişimi yoktur.

---

## Arayüz

Arayüz bir gösterge tablosu değil, bir konuşmadır. Brifing ayrı bir kutu olarak değil,
kâtibin günün ilk mesajı olarak gelir; onaylar sohbetin içinde satır satır verilir.

```
┌──────────────┬────────────────────────────────────┐
│ E Edirnekapı │  PAZARTESİ 07:40      şimdi tara   │
│              │                                    │
│ KÜNYE        │  Günaydın. Gün tek bir işin        │
│ ● Posta   4  │  etrafında dönüyor: ...            │
│ ● Mesaj   7  │  ────────────────────────────────  │
│ ● Ajanda  3  │  ONAYINIZI BEKLEYEN 2 ŞEY          │
│              │  Ayşe — "..."  [Onayla] [Değiştir] │
│ BUGÜN        │  ────────────────────────────────  │
│ 11:00 Kayalar│                  siz yazdınız ▸    │
│ 14:30 Diş    │  kâtibin cevabı...                 │
│              │                                    │
│ Defteri aç → │  [ Vellum'a yazın…        Söyle ]  │
└──────────────┴────────────────────────────────────┘
```

Tasarım [Claude Design](https://claude.ai/design)'da hazırlandı; tasarım sistemi
**Broadsheet** — gazete dizgisi: Source Serif 4, kağıt zemini, camgöbeği ve magenta
noktasal vurgu, kutu ve çerçeve yok.

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
├── .claude/agents/        dört ajan tanımı (hem belge hem yapılandırma)
├── config/                persona, skorlama rubriği, kişi listeleri
├── state/                 ortak hafıza: digest'ler, taslaklar, brifing arşivi
├── projects/              proje hafızası: olaylar.jsonl + durum.json
├── panel/
│   ├── sunucu.py          yerel sunucu (yalnızca standart kütüphane)
│   ├── beyin.py           Çekirdek + ajanlar (Claude API, tool use)
│   ├── panel.html         arayüz yerleşimi
│   ├── panel.js
│   └── _ds/broadsheet/    tasarım sistemi
└── scripts/               veri çekme ve demo üretimi
```

---

## Önem skorlaması

Mail önemi kural tabanlı bir rubrikle hesaplanır (`config/onem-kurallari.md`). Taban 30 puan:

| Sinyal | Etki |
|---|---|
| Gönderen VIP listesinde | +40 |
| Doğrudan size yazılmış | +20 |
| CC / toplu gönderim | −15 |
| İçinde tarih veya son tarih var | +25 |
| Para, fatura, sözleşme, hukuki | +30 |
| Thread'de sıra sizde | +20 |
| Bülten / pazarlama / otomatik | −50 |

Sinyal toplamı 100'ü aşabilir. **Ham toplam saklanır**, gösterilen skor 0–100'e kırpılır,
sıralama daima ham skora göre yapılır — aksi halde 140 puanlık bir sözleşme maili ile
105 puanlık bir fatura maili ekranda aynı görünürdü.

---

## Yol haritası

| Faz | İçerik | Durum |
|---|---|---|
| 0 | İskelet, ajan tanımları, uçtan uca akış | tamam |
| 1 | Gmail entegrasyonu (OAuth, fetch, canlı gönderim) | bekliyor |
| 2 | Google Takvim entegrasyonu | bekliyor |
| 3 | Zamanlanmış tarama + bildirim | bekliyor |
| 4 | Onay ve gönderimin canlıya alınması | bekliyor |
| 5 | Proje hafızası | tamam |
| 6 | Telegram botu — panelin uzaktan kolu | bekliyor |
| 7 | Panel arayüzü | tamam |
| 8 | Instagram DM (Meta App Review) | bekliyor |

---

## Bilinen sınırlar

- Instagram DM erişimi Meta App Review onayı gerektirir; ayrıca Meta'nın 24 saat kuralı
  vardır — karşı tarafın son mesajından 24 saat sonra API ile serbest metin gönderilemez.
- Mail ve mesaj içerikleri özetleme için modele gönderilir. Ham veri diskte kalır;
  `secrets/`, `state/raw/` ve `.env` versiyon kontrolüne girmez.
- Her tarama beş API çağrısıdır (dört ajan + harmanlama). Zamanlanmış taramaya geçmeden
  önce gerçek token kullanımı ölçülmelidir.
- Taranmış (görüntü) PDF eklerinden metin çıkmaz; sistem bu durumda tahmin yürütmez,
  kullanıcıya bildirir.
- Karanlık tema yoktur: Broadsheet koyu yüzey tanımlamıyor, tek kağıt teması kullanılıyor.

---

## Not

Proje **Vellum** adını yeni aldı; arayüzde ve bazı dosyalarda hâlâ önceki çalışma adı
(*Edirnekapı* / *Kâtip*) geçiyor. İsim değişikliği koda henüz yansıtılmadı.

Ayrıntılı mimari dokümanı: `Edirnekapi - Yapi Dokumani.docx`

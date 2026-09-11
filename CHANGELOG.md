# Değişiklik günlüğü

Bu dosya projenin git geçmişinden üretildi ve her değişiklikte sürdürülüyor. Her kayıt
ne yapıldığını değil, **neden** yapıldığını da söyler; bir karardan dönmek gerektiğinde
asıl aranan bilgi odur. Yol boyunca çıkan hatalar da yazılı — sessizce düzeltilen hata
ikinci kez aynı yerden çıkar.

Aynı içeriğin Word hâli: `Vellum - Degisiklik Gunlugu.docx`.

Sürümler en yeniden eskiye sıralıdır.

## Bir bakışta

| Tarih | Değişiklik | Kayıt |
|---|---|---|
| 11 Eyl 2026 | Değişiklik günlüğü eklendi; dokümanlar hafızaya göre güncellendi | `4726189` |
| 11 Eyl 2026 | Kalıcı kullanıcı hafızası | `8fe9e8d` |
| 11 Eyl 2026 | Sohbete takvim ve proje yazma yetkisi; yazılı sayfa kaldırıldı | `f96eba6` |
| 11 Eyl 2026 | Yazı kutusu hatası düzeltildi; Spline iptal | `20fab79` |
| 11 Eyl 2026 | Sesli mod: panel konuşuyor ve dinliyor | `2cf3f0f` |
| 10 Eyl 2026 | Dokümanlar Fluent 2'ye ve bugünkü mimariye göre güncellendi | `e22f62e` |
| 10 Eyl 2026 | Instagram DM; Ajanda kaldırıldı; öncelikler adlandırıldı | `263a8b1` |
| 10 Eyl 2026 | Panel bileşenleri Fluent 2'ye geçirildi | `e5e6b59` |
| 9 Eyl 2026 | Anahtar kelime sözlüğü, Konular sayfası, yazışma sinyali | `1de3b2d` |
| 9 Eyl 2026 | Takvim sayfası, otomatik etkinlik ve hatırlatma | `e480baa` |
| 8 Eyl 2026 | Yapı dokümanı güncellendi | `93fd1d3` |
| 8 Eyl 2026 | Kural tabanlı skorlama, canlı izleme, maliyet düşürme | `23d288d` |
| 7 Eyl 2026 | Ürün adı Vellum'a çevrildi | `95252f9` |
| 7 Eyl 2026 | İlk sürüm | `2fe0d46` |

---

## 11 Eylül 2026

### Değişiklik günlüğü ve doküman güncellemeleri · `4726189`, `5a178e6`

- Git geçmişinden bir değişiklik günlüğü üretildi (Word ve Markdown olarak) ve bundan
  sonraki her değişiklikte sürdürülecek.
- Yapı dokümanına hafıza bölümü, yol haritası satırları ve yeni sınırlar eklendi.
- Yol boyunca dosya iki kez bozuldu, ikisi de aynı hatadan: paragraf metnini bulan
  `<w:t[^>]*>` deseni `<w:tcPr>` gibi etiketleri de yakalayıp hücre XML'inin ortasından
  "metin" başlatıyordu. Desene sınır kondu: `<w:t(?=[ >])[^>]*>`.

### Kalıcı kullanıcı hafızası · `8fe9e8d`

Vellum artık kullanıldıkça kullanıcıyı tanıyor: mesleği, ilgi alanları, gittiği yerler,
sık görüştüğü kişiler. Öğrendiği her şey kalıcı olarak saklanıyor ve maillerin önem
sırasına giriyor.

- İki kaynaktan öğreniyor, ikisi de ek ücret doğurmuyor: konuşurken söyledikleriniz
  (zaten yapılan çağrının içinde) ve taramadan sonra çalışan modelsiz sayım — kiminle
  kaç kez yazışıldığı, hangi adın tekrar ettiği.
- Mail gövdelerinden model çıkarımı bilerek yapılmıyor: her taramaya bir çağrı bindirir
  ve içerik modele daha çok giderdi.
- Öğrenilenler sinyal satırında görünüyor (`hafiza:mimarlık +25`); hiçbir ağırlık sessiz
  uygulanmıyor.
- Depo append-only: bilgi silinmiyor, unutma da bir satır. "Ne zamandan beri böyle
  biliyor" sorusu cevaplanabilir kalıyor.
- Üç sınır bilerek kondu: bir maile toplam katkı ±40; bir bilgi 90 günde yarıya, 180
  günde çeyreğe iniyor (kayıt duruyor, etkisi sönüyor); VIP ve "bu adrese yazdınız"
  sinyallerinin altında sıralanıyor.
- Defter'e Hafıza sekmesi eklendi: ne öğrendiği, nereden öğrendiği, kaç kez doğrulandığı
  yazılı. Yanlış olan kaldırılıyor, önemi değiştirilebiliyor.
- Hafıza dosyası projenin en kişisel dosyası; sürüm kontrolüne girmiyor.

Testler: hafıza 53/53 (yeni), skorlama 51/51 — hafıza boşken skorların birebir aynı
kaldığı da doğrulandı.

### Sohbet takvime ve proje günlüğüne yazabiliyor · `f96eba6`

Sesli asistan "takvime yazma yetkim yok, sadece dosyaları okuyabiliyorum" diyordu.
Artık yazıyor.

- Dört dar araç eklendi: `takvim_ekle`, `takvim_iptal`, `proje_olay_ekle`, `proje_ac`.
- Serbest dosya yazma bilerek verilmedi. Projenin ilkesi, yetki sınırının "şunu yapma"
  cümlelerine değil araçların kendisine gömülmesi. Dar araç ayrıca kaydın biçimini
  garanti ediyor: model ISO tarihi ya da olay şemasını uydurmuyor.
- Gönderim yetkisi verilmedi: mail ve DM hâlâ yalnızca panelden onaylanan taslaklarla
  gidiyor.
- Her sohbet çağrısına o anki tarih ve gün ekleniyor. "Önümüzdeki salı" ancak bugünün ne
  olduğu biliniyorsa tarihe çevrilebilir.
- Yazılı sohbet sayfası kaldırıldı; tek ana ekran sesli mod. Günün brifingi sağ şeride,
  konuşma geçmişi Defter'in yeni Sohbet sekmesine taşındı.
- Düzeltilen hata: durum tazeleme hesabı sunucuya yaptırılıyordu ama sunucunun kendi kök
  dizini var; testler gerçek `projects/` klasörüne yazıyor, hatta olmayan klasörleri
  açıyordu.
- Düzeltilen hata: proje adı üretimi Türkçe harfleri atıyordu ("Görüşmesi" → "grmesi").

### Yazı kutusu hatası düzeltildi; Spline iptal · `20fab79`

Sesli ekranda yazı kutusuna yazılamıyordu. Sebep tuvaldi: boyunu kabından bir kez
ölçüyor, balon uzayıp sahne kısalınca eski boyunda kalıp aşağı taşıyor ve kutunun
tıklamalarını yutuyordu.

- Üç yerden kapatıldı: sahne kabına overflow gizleme, tuvale pointer-events kapatma,
  kabı izleyen bir `ResizeObserver`.
- İkinci kırpma: sesli ekranın kendi overflow ayarı alçak pencerede taşan öğeyi
  kesiyordu. Kırpma yerine kaydırma; sahne ilk küçülen öğe oldu.
- Spline sahnesi iptal edildi — kendi çizdiğimiz küre beğenildi. Kullanılmayan yükleme
  yolu silindi; o yol ücretsiz planda köşeye rozet koyuyordu.

### Sesli mod: panel konuşuyor ve dinliyor · `2cf3f0f`

Panel yazışmaktan çıkıp konuşmaya geçti. Açılış ekranında ortada bir küre, altında
söylenenin yazıldığı balon, mikrofon düğmesi ve yazı kutusu var.

- Maliyet sıfır: konuşma `edge-tts` ile Microsoft'un Türkçe neural sesinden üretiliyor
  (anahtar yok, ücret yok), dinleme tarayıcının kendi konuşma tanımasıyla.
- Claude tarafı ucuzladı: sesli cevaplar üç cümleyle sınırlı, çıktı token'ı düşüyor.
- Üretilen mp3 diske cacheleniyor; aynı cümle ikinci kez söylenirse ağa hiç gidilmiyor.
- Küre gerçek sesle oynuyor: çalan ses çözümleyiciden geçiyor, ölçülen güç doğrudan
  çizime gidiyor.
- Ses üretilemezse panel sessiz devam ediyor, balon yazmayı sürdürüyor. Sesin kaybolması
  konuşmayı kaybetmekten iyidir.
- Düzeltilen hata: kürenin sese tepkisi sessizce kapalıydı — üst seviye bir sabit,
  tarayıcının genel nesnesine özellik yazmıyor.

---

## 10 Eylül 2026

### Dokümanlar bugünkü mimariye göre güncellendi · `e22f62e`

- README, PLAN ve yapı dokümanı hâlâ eski tasarım dilini anlatıyordu.
- Biriken sapmalar düzeltildi: ajan sayısı, model adı, takvim entegrasyonu,
  Instagram'ın App Review gerektirdiği yanlış ifadesi.
- Yol haritası tablosunda bir satırın durumu yanlışlıkla değişmişti; aynı içerikli
  hücreler metin aramasıyla karışıyordu. Konum bazlı yazımla düzeltildi.

### Instagram DM; Ajanda kaldırıldı; öncelikler adlandırıldı · `263a8b1`

- Instagram DM bağlantısı kuruldu (Instagram Login). Profesyonel hesap yetiyor; Facebook
  Sayfası bağlamak gerekmiyor ve kendi hesabınız için App Review gerekmiyor.
- Ajanda bölümü kaldırıldı: ayrı bir veri kaynağı değildi, takvim geldikten sonra aynı
  işi iki yerde gösteriyordu.
- Konular sayfasında ağırlıklar sayı olmaktan çıktı: Çok önemli, Önemli, Biraz önemli,
  Önemsiz, Gürültü. Depoda saklanan hâlâ sayı; yalnızca arayüz adlandırıyor.

### Panel bileşenleri Fluent 2'ye geçirildi · `e5e6b59`

- Yerleşim aynı kaldı; değişen öğelerin görünüşü. Segoe UI, beyaz yüzey, 4 piksel köşe
  yarıçapı, odakta marka alt şeridi, kartlarda yükseklik gölgesi.
- Token değerleri paylaşılan Figma dosyasından değil, Fluent'in yayımlanmış kaynağından
  alındı.
- Kontrast ölçüldü: gövde 15,5:1, marka düğme 5,4:1, rozet 7,0:1 — hepsi erişilebilirlik
  eşiğinin üstünde. Mobil dokunma hedefi 44 piksele çıkarıldı.
- Düzeltilen hata: kısayol biçiminde yazılan kenarlık kuralı, odak kuralının rengini
  eziyordu.

---

## 9 Eylül 2026

### Anahtar kelime sözlüğü, Konular sayfası, yazışma sinyali · `1de3b2d`

Araştırma sırasında eşleştiricinin Türkçede bozuk olduğu ortaya çıktı: kalıplar yalnızca
yalın hâlde çalışıyordu, "faturanız" ve "sözleşmeyi" yakalanmıyordu.

- Çekim ekleri açık liste olarak tanımlandı. Genel bir joker kullanılsaydı "kaza" gövdesi
  "kazandınız"a yapışırdı — pazarlama dilinin klasiği.
- 10 kategori, 141 gövdelik ortak sözlük eklendi: para ve sözleşme, aksiyon isteği,
  güvenlik, resmî, sağlık, eğitim, seyahat, kargo, iş başvurusu.
- Aciliyet kelimeleri bilerek dışarıda bırakıldı: araştırma bunların pazarlama ve
  oltalama dili olduğunu gösteriyor.
- Konular sayfası açıldı: kendi kelimenizi ağırlığıyla ekliyorsunuz, yanında son taramada
  kaç maile dokunduğu yazıyor.
- Yazışma sinyali eklendi: daha önce yazdığınız adreslerden gelen mail öne çıkıyor.
  Davranışsal sinyal, kelimeden güçlü bir ölçüt.
- Gizlilik: kişi listeleri ve konular git dışına alındı.

### Takvim sayfası, otomatik etkinlik, hatırlatma · `e480baa`

- Defter'e gerçek bir aylık takvim eklendi. Mailden çıkan toplantı ve görüşmeler
  kendiliğinden yazılıyor.
- Etkinlik günü ve bir gün öncesinde masaüstü hatırlatması çıkıyor. Hatırlatma mevcut
  izleme turuna eklendi; model çağrılmıyor, maliyeti yok.
- Depo append-only: etkinlik silinmiyor, düzeltme yeni satır, kaldırma iptal satırı.
  Kaldırılan bir mail etkinliği sonraki taramada geri gelmiyor.
- Bölümler alttaki etiket şeridinden sol menüye taşındı.

---

## 8 Eylül 2026

### Yapı dokümanı güncellendi · `93fd1d3`

- Kural motoru, yeni bileşenler, Gmail kurulumu ve görünürlük bölümleri eklendi; klasör
  yapısı ve yol haritası tazelendi.

### Kural tabanlı skorlama, canlı izleme, maliyet düşürme · `23d288d`

Önem skorlaması modelden alınıp Python'a taşındı. Rubrik zaten deterministik bir kural
tablosuydu; onu modele hesaplatmak 32 mail için 104.000 giriş tokenı ve dakikalar
demekti.

- Mail özeti başına maliyet yaklaşık 0,24 dolardan 0,005 dolara indi.
- Model artık yalnızca eşiği geçen maillere özet ve taslak yazıyor; ajanın okuduğu dosya
  küçültüldü ve sistem istemi önbelleğe alındı.
- Canlı izleme eklendi: 60 saniyede bir posta kutusu yoklanıyor, model çağrılmadığı için
  gün boyu izleme bedava.
- Yeni mail yalnızca bildirilmiyor, sisteme de düşüyor; masaüstünde kendi çizdiğimiz
  bildirim kartı açılıyor.
- Görünürlük: tarama kaydı tutuluyor, API hataları düz Türkçeye çevriliyor, brifingin
  üretim damgası gösteriliyor.
- Demo veri kaldırıldı; gerçek kullanıcı verisi taşıyan dosyalar versiyon kontrolünden
  çıkarıldı.

---

## 7 Eylül 2026

### Ürün adı Vellum'a çevrildi · `95252f9`

- Arayüzdeki ad, marka monogramı ve künye cümlesi güncellendi.

### İlk sürüm · `2fe0d46`

Dört ajanlı yerel asistan. Claude API üzerinden çalışır, tek bir web paneli üzerinden
kullanılır. Başlangıçta konan ve bugün hâlâ geçerli olan kararlar:

- Tek varlık, çok uzuv: alt ajanlar yapılandırılmış veri üretir, Çekirdek harmanlar.
  Kullanıcı tek bir sesle konuşur.
- Proje hafızası append-only olay günlüğü; durum ondan türetilir.
- Onaysız gönderim yok; otomatik çıkarılan olaylar onay bekler.
- Yetki sınırı araç seviyesinde: proje kökü dışına çıkılamaz, sırlar okunamaz.

---

## Bundan sonrası

Yeni bir değişiklik yapıldığında "Bir bakışta" tablosuna satır eklenir ve altına kaydı
yazılır. Kayıt şu üç şeyi söylemeli:

- **Ne değişti.**
- **Neden değişti** — bir karardan dönmek gerektiğinde asıl aranan bilgi budur.
- **Yol boyunca bulunan hatalar ve ne yapıldığı.** Sessizce düzeltilen hata, ikinci kez
  aynı yerden çıkar.

Word dosyası da aynı anda güncellenir; ikisi aynı içeriği taşır.

Bilinen ve bilerek yapılmamış işler: karanlık tema yok, canlı gönderim kapalı, Telegram
botu bekliyor.

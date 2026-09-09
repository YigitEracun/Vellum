# Anahtar kelime sözlüğü

Önem skorlamasının içerik sinyalleri. `panel/skorlama.py` bu dosyayı okur ve uygular.

**Bu dosya ortak varsayılandır** — herkes için geçerli genel kelimeler. Kendi konularınızı
buraya değil, panelin **Konular** sayfasına girin; onlar `state/konular.json` içinde,
versiyon kontrolünün dışında durur. Sebep: bu dosya projeyle birlikte güncellenir, sizin
konularınız ise kişiseldir ve başka bir kullanıcıya kurulduğunda gelmemelidir.

## Biçim

Her başlık bir kategori, yanındaki sayı ağırlığıdır. Altındaki her satır bir **gövde** —
Türkçe ekler kendiliğinden eşleşir (`fatura` yazarsanız "faturanız", "faturayı", "faturası"
da yakalanır), o yüzden ekli hâlleri yazmayın.

Gövdeyi olabildiğince uzun tutun. Kısa gövdeler alakasız kelimelere yapışır: `kaza`
yazarsanız "kazandınız" da eşleşme riski taşır (ek kümesi bunu eler ama sınırda kalır),
`ders` yazarsanız "derslik" tehlikeye girer.

## Aciliyet kelimeleri neden yok

"Acil", "hemen", "son gün", "kaçırmayın", "süresi doluyor" — bunlar bilerek listede değil.
Araştırmalar bu kelimelerin en yoğun pazarlama ve oltalama dilinde geçtiğini gösteriyor;
olumlu sinyal yapılırsa her indirim maili brifingin başına çıkar. Toplu gönderimde içerik
sinyalleri zaten sayılmıyor ama listeye de girmemeliler.

---

## para-sozlesme +30

fatura
ödeme
ücret
tutar
bedel
sözleşme
kontrat
teklif
fiyat teklifi
bütçe
ihale
masraf
tahsilat
havale
dekont
invoice
payment
contract
billing
receipt
refund
quotation

## aksiyon-istegi +20

onayınız
onayınıza
imzanız
imzalamanız
teyit
geri dönüş
dönüş yapabilir
cevap bekliyoruz
görüş bildir
değerlendirmenizi
tamamlamanız
please review
please confirm
awaiting your
your approval
action required
sign the

## guvenlik +35

şifre sıfırlama
şifrenizi
parola sıfırlama
doğrulama kodu
tek kullanımlık kod
yeni cihazdan giriş
şüpheli giriş
hesabınız askıya
hesabınızın kapatılması
yetkisiz erişim
güvenlik uyarısı
password reset
verification code
suspicious sign
unauthorized access
account suspended
two-factor

## resmi +35

tebligat
mahkeme
duruşma
dava
icra
haciz
ihtarname
vergi borcu
vergi beyan
sgk
e-devlet
noter
savcılık
idari para cezası
ruhsat
denetim

## saglik +30

muayene
poliklinik
tahlil
tetkik
biyopsi
reçete
ameliyat
kontrol randevu
hastane randevu
laboratuvar sonuc
patoloji
radyoloji
aşı

## egitim +25

sınav
vize sınav
final sınav
bütünleme
ders kaydı
ders seçim
transkript
diploma
burs
staj başvuru
tez
danışman onay
akademik takvim

## seyahat +20

uçuş
rezervasyon
check-in
biniş kartı
otel kaydı
vize randevu
pasaport
seyahat planı
flight
booking reference

## kargo +10

teslim edilemedi
teslimat başarısız
gümrük
iade talebi
kargo hasar
delivery failed
customs

## is-basvurusu-ilerleme +45

mülakat
görüşme
işe alım görüşme
iş teklifi
teklif mektubu
işe alım süreç
değerlendirme sonuc
sonraki aşama
interview
job offer
offer letter
next step
move forward
shortlist

## is-basvurusu-onayi -40

başvurunuz ... alın
başvurunuz ... iletil
başvurunuz ... ulaş
başvurun ... alın
başvurusu ... alın
thank you for applying
thank you for your application
received your application
application received
application submitted
indeed başvuru
indeed application

---
description: Günlük brifingi üret
---

Sırayla:

1. `state/raw/` altındaki dosyaların zaman damgasına bak. 2 saatten eskiyse kullanıcıyı uyar
   ("veri eski, tarama çalışmamış olabilir") ama yine de devam et.
2. `mail-agent`, `social-agent`, `calendar-agent` agent'larını **paralel** çalıştır.
3. Üçü bitince `proje-agent` çalıştır.
4. Çıktıları `config/persona.md` içindeki brifing formatına göre harmanla. Üç ayrı rapor değil,
   tek metin. Hangi agent'ın ne ürettiğinden bahsetme.
5. Onaylanmamış olay önerisi varsa brifingin sonunda sor:
   "<Proje> geçmişine şu olayı ekleyeyim mi: <başlık>"
6. Brifingi `state/log/<bugün>.md` dosyasına yaz.

Argüman verilmişse (`/brief hizli`) yalnızca skoru 80 üzeri olanları göster, taslak üretme.

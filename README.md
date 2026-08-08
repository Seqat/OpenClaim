# OpenClaim - Open Source Free Games Tracker

Steam, Epic Games Store ve Amazon Luna / Prime Gaming platformlarındaki ücretsiz oyun fırsatlarını otomatize pipeline ile takip eden açık kaynaklı web uygulaması.

---

## ✨ Öne Çıkan Özellikler (Key Features)

- 🤖 **GitHub Actions Otomasyonu:** Otomatik veri çekme ve yayınlama (Cron otomasyonu).
- ⚡ **Sıfır İstemci Taraflı API Bağımlılığı:** CORS ve rate-limit engeline takılmadan yerel `games.json` kullanımı.
- 🌐 **Çoklu Dil Desteği:** Türkçe ve İngilizce (TR / EN) dil seçenekleri.
- 🗂️ **Gelişmiş Filtreleme ve Görünüm:** Akıllı Sıralama, Grid / List görünüm modları ve yapışkan (sticky) filtre çubuğu.
- 👁️ **Modern Arayüz Tasarımı:** Göz dostu Slate Dark tema mimarisi ve mikro-animasyonlar.

---

## 🛠️ Teknoloji Yığını (Tech Stack)

- **Backend / Pipeline:** Python (`Playwright`, `Requests`)
- **Otomasyon & CI/CD:** GitHub Actions
- **Frontend:** Vanilla HTML5, CSS3 (Custom Design System), ES6 JavaScript Modules

---

## 💻 Lokal Geliştirme (Local Development)

### 1. Backend Pipeline'ı Çalıştırma

```bash
git clone https://github.com/Seqat/OpenClaim.git
cd OpenClaim
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
python backend/main.py
```

### 2. Frontend Önizleme (Local Web Server)

```bash
# Kök dizindeyken yerel sunucuyu başlatın:
python -m http.server 8000

# Tarayıcıda açın:
# http://localhost:8000
```

---

## 📄 Lisans (License)

Bu proje [MIT License](LICENSE) altında lisanslanmıştır.

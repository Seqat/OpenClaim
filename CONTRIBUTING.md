# Contributing to OpenClaim

[English](#english) | [Türkçe](#türkçe)

---

<a name="english"></a>
## 🌐 English

Thank you for your interest in contributing to OpenClaim! All bug reports, feature suggestions, and code contributions are welcome.

### 🛠️ Contribution Workflow

1. **Fork the Repository:** Fork the project on GitHub to your own account.
2. **Create a Branch:** Create a descriptive branch for your feature or bug fix:
   ```bash
   git checkout -b feature/new-scraper
   # or
   git checkout -b fix/date-parsing-bug
   ```
3. **Make & Test Changes:**
   Install development dependencies and run the pytest suite:
   ```bash
   pip install -r requirements-dev.txt
   python -m pytest
   ```
4. **Commit Your Changes:** Follow the **Conventional Commits** standard for your commit messages (e.g. `chore:`, `feat:`, `fix:`, `docs:`, `test:`).
5. **Open a Pull Request (PR):** Submit a PR to the `main` branch with a clear title and description of your changes.

---

### 📝 Commit Message Conventions

Our repository enforces Conventional Commits standards:

- `feat:` When adding a new feature (e.g. `feat: add GOG scraper`)
- `fix:` When fixing a bug (e.g. `fix: correct iso date parser`)
- `chore:` For maintenance and CI/CD updates (e.g. `chore: update games.json [skip ci]`)
- `docs:` For documentation updates (e.g. `docs: update README with contribution guide`)
- `test:` When adding or updating tests (e.g. `test: add unit tests for dedupe`)

---

### 🐛 Issue Reporting Guide

When reporting an issue or suggesting a feature, please select the appropriate template under GitHub Issues:

- **Bug Report:** Specify the affected platform, expected vs. observed behavior, `games.json` `generated_at` timestamp, and your environment/browser information.
- **Feature Request:** Clearly outline the purpose of the feature and how it benefits the users.

---

<a name="türkçe"></a>
## 🇹🇷 Türkçe

OpenClaim projesine katkıda bulunmak istediğiniz için teşekkür ederiz! Her türlü hata bildirimi, özellik önerisi ve kod katkısı memnuniyetle karşılanır.

### 🛠️ Katkı Sağlama Akışı (Contribution Workflow)

1. **Repoyu Fork Edin:** GitHub üzerinde projeyi kendi hesabınıza fork edin.
2. **Branch Oluşturun:** Özelliğinizi veya düzeltmenizi açıklayan anlamlı bir branch açın:
   ```bash
   git checkout -b feature/new-scraper
   # veya
   git checkout -b fix/date-parsing-bug
   ```
3. **Değişiklikleri Yapın ve Test Edin:**
   Geliştirme bağımlılıklarını yükleyin ve pytest testlerini çalıştırın:
   ```bash
   pip install -r requirements-dev.txt
   python -m pytest
   ```
4. **Commit Atın:** Commit mesajlarınızda **Conventional Commits** standartlarına uyun (ör. `chore:`, `feat:`, `fix:`, `docs:`, `test:`).
5. **Pull Request (PR) Açın:** Değişikliklerinizi `main` branch'ine yönelik açık bir başlık ve açıklama ile PR olarak gönderin.

---

### 📝 Commit Mesajı Formatı (Commit Message Conventions)

Repomuzda Conventional Commits standartları takip edilmektedir:

- `feat:` Yeni bir özellik eklendiğinde (ör. `feat: add GOG scraper`)
- `fix:` Bir hata düzeltildiğinde (ör. `fix: correct iso date parser`)
- `chore:` Genel bakım ve CI/CD güncellemelerinde (ör. `chore: update games.json [skip ci]`)
- `docs:` Dokümantasyon güncellemelerinde (ör. `docs: update README with contribution guide`)
- `test:` Test eklendiğinde veya güncellendiğinde (ör. `test: add unit tests for dedupe`)

---

### 🐛 Issue Açma Rehberi (Issue Reporting Guide)

Bir sorunla karşılaştığınızda veya yeni bir fikir önerdiğinizde lütfen GitHub Issues bölümünden uygun şablonu seçin:

- **Hata Bildirimi (Bug Report):** Etkilenen platform, beklenen ve gözlenen davranış, `games.json` dosyasındaki `generated_at` zaman damgası ve tarayıcı bilgilerinizi ekleyin.
- **Özellik İsteği (Feature Request):** Önerilen özelliğin amacını ve kullanıcıya sağlayacağı faydaları net bir şekilde açıklayın.

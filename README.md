# DataForge — End-to-End Data Pipeline

Veriyi kaynaktan alıp dönüştüren ve hedef sisteme yükleyen uçtan uca veri pipeline projesi.

## Proje Yapısı

```
.
├── config/                 # Pipeline yapılandırma dosyaları
├── data/
│   ├── raw/                # Ham veri (git'e eklenmez)
│   └── processed/          # İşlenmiş veri (git'e eklenmez)
├── notebooks/              # Keşif amaçlı analizler
├── src/dataforge/
│   ├── ingestion/          # Veri toplama (extract)
│   ├── transformation/     # Temizleme ve dönüştürme (transform)
│   └── loading/            # Hedefe yükleme (load)
└── tests/                  # Testler
```

## Kurulum

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Testler

```bash
pytest
```

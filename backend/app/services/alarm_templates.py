"""Human-readable, deterministic alarm guidance (not ML diagnostics)."""

from typing import Final

CauseList = list[dict[str, str]]
Template = tuple[str, str, CauseList]
DEFAULT: Final[Template] = (
    "Bir operasyon değeri, tanımlı kural sınırını aştı.",
    "Etkilenen ekipmanı ve son sensör ölçümlerini kontrol edin.",
    [{"description": "Operasyon değeri tanımlı kural sınırının dışında"}],
)


def _causes(*items: str) -> CauseList:
    return [{"description": item} for item in items]


_TEMPLATES: Final[dict[str, Template]] = {
    "LOW_FLOW": ("Pompa çalışırken debi, tanımlı alt sınırın altında kaldı.", "Pompa filtresini, hat basıncını ve pompa performansını kontrol edin.", _causes("Filtre tıkanıklığı", "Pompa performans kaybı", "Hat basıncı sorunu")),
    "HIGH_MOTOR_CURRENT": ("Pompa motor akımı, tanımlı çalışma sınırını aştı.", "Motor yükünü, mekanik sürtünmeyi ve pompanın çalışma koşullarını kontrol edin.", _causes("Aşırı motor yükü", "Mekanik sürtünme", "Pompa aşınması")),
    "HIGH_PRESSURE": ("Pompa hat basıncı, tanımlı üst sınırı aştı.", "Hat basıncını, vana durumunu ve olası tıkanıklıkları kontrol edin.", _causes("Kapalı vana", "Hat tıkanıklığı", "Basınç sensörü sapması")),
    "HIGH_WATER_LEVEL": ("Tank su seviyesi kritik çalışma sınırının üzerine çıktı.", "Tank su seviyesini doğrulayın ve yakıt-su ayrışmasını kontrol edin.", _causes("Su karışması", "Tank sızdırmazlık sorunu", "Seviye sensörü doğrulaması gerekli")),
    "SENSOR_STUCK": ("Satış sürerken ölçülen tank seviyesi olağandışı süre boyunca değişmedi.", "Tank seviye sensörünü ve sensör iletişimini kontrol edin.", _causes("Sensörün sabit kalması", "İletişim sorunu", "Kalibrasyon gereksinimi")),
    "SENSOR_SPIKE": ("Ölçümdeki ani değişim fiziksel akışla açıklanamıyor.", "Ölçüm değişimini doğrulayın; sensör bağlantısını ve kalibrasyonunu kontrol edin.", _causes("Bağlantı kesintisi", "Elektriksel gürültü", "Sensör kalibrasyonu")),
    "TANK_SALES_MISMATCH": ("Tank seviyesindeki düşüş, satışlarla açıklanan miktardan daha fazla.", "Satış kayıtlarını tank seviyesiyle karşılaştırın; olası sızıntı veya ölçüm hatasını araştırın.", _causes("Kayıt uyuşmazlığı", "Olası sızıntı", "Seviye ölçüm hatası")),
    "LOW_DATA_QUALITY": ("Etkilenen ekipmanın ölçümlerinde veri kalitesi sorunu algılandı.", "Sensör verisini, iletişimi ve son veri kalitesi işaretlerini kontrol edin.", _causes("İletişim kesintisi", "Eksik veri", "Fiziksel aralık ihlali")),
    "AI_ANOMALY": ("Öğrenilen normal çalışma davranışından anlamlı bir sapma algılandı.", "Yapay zekâ bulgularını ve önerilen kontrolleri inceleyin.", _causes("Olağandışı çalışma davranışı", "Ekipman performans değişimi", "Sensör verisi sapması")),
}

_TITLES: Final[dict[str, str]] = {
    "LOW_FLOW": "Pompa Debi Düşüşü",
    "HIGH_MOTOR_CURRENT": "Yüksek Motor Akımı",
    "HIGH_PRESSURE": "Yüksek Hat Basıncı",
    "HIGH_WATER_LEVEL": "Yüksek Tank Su Seviyesi",
    "SENSOR_STUCK": "Sensör Verisi Sabit",
    "SENSOR_SPIKE": "Ani Sensör Değişimi",
    "TANK_SALES_MISMATCH": "Tank ve Satış Uyuşmazlığı",
    "LOW_DATA_QUALITY": "Düşük Veri Kalitesi",
    "AI_ANOMALY": "Yapay Zekâ Erken Uyarısı",
}


def guidance_for(alarm_type: str) -> Template:
    return _TEMPLATES.get(alarm_type, DEFAULT)


def title_for(alarm_type: str) -> str:
    return _TITLES.get(alarm_type, "Operasyon Uyarısı")

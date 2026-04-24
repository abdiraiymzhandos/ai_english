import re
import secrets
import string
import unicodedata
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from difflib import SequenceMatcher

import pytesseract
from django.utils import timezone
from django.utils.text import slugify
from PIL import Image, ImageOps

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - dependency is added in requirements, but keep runtime safe.
    PdfReader = None


BUYING_INTENT_PATTERNS = (
    "сатып аламын",
    "аламын",
    "қалай төлеймін",
    "қалай сатып аламын",
    "төлем",
    "оплатить",
    "хочу купить",
    "готов оплатить",
    "где оплатить",
    "беру",
    "бастаймын",
)

PAYMENT_DONE_PATTERNS = (
    "төледім",
    "чек жібердім",
    "чек",
    "оплатил",
    "оплатила",
    "чек отправил",
    "чек отправила",
)

HANDOFF_PATTERNS = (
    "менеджер",
    "адам керек",
    "человек",
    "позовите человека",
    "жалоба",
    "тоқтат",
    "не пиши",
    "сен ботсың ба",
    "не понял",
    "не правильно",
    "проблема",
)

KAZAKH_LETTERS = set("әіңғүұқөһӘІҢҒҮҰҚӨҺ")
CYRILLIC_PATTERN = re.compile(r"[А-Яа-яЁёӘәІіҢңҒғҮүҰұҚқӨөҺһ]")


def normalize_phone_number(phone):
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    return f"+{digits}"


def raw_whatsapp_recipient(phone):
    return re.sub(r"\D", "", phone or "")


def whatsapp_recipient(phone):
    return raw_whatsapp_recipient(normalize_phone_number(phone))


def resolve_outbound_whatsapp_recipient(phone, prefer_exact_input=False):
    raw_digits = raw_whatsapp_recipient(phone)
    if not raw_digits:
        return ""
    if prefer_exact_input:
        if raw_digits.startswith("00"):
            return whatsapp_recipient(phone)
        if raw_digits.startswith("8") and len(raw_digits) == 11:
            return whatsapp_recipient(phone)
        return raw_digits
    return whatsapp_recipient(phone)


def detect_language(text):
    if not text:
        return "unknown"
    if not CYRILLIC_PATTERN.search(text):
        return "unknown"
    if any(char in KAZAKH_LETTERS for char in text):
        return "kk"
    return "ru"


def detect_intent(text):
    lowered = (text or "").lower()
    if any(pattern in lowered for pattern in HANDOFF_PATTERNS):
        return "handoff"
    if any(pattern in lowered for pattern in PAYMENT_DONE_PATTERNS):
        return "payment_submitted"
    if any(pattern in lowered for pattern in BUYING_INTENT_PATTERNS):
        return "buying_intent"
    return "general"


def normalize_matching_text(value):
    normalized = unicodedata.normalize("NFKC", value or "").lower()
    return re.sub(r"[^0-9a-zа-яёәіңғүұқөһ]+", "", normalized)


def expected_name_score(extracted_text, expected_name):
    text_norm = normalize_matching_text(extracted_text)
    name_norm = normalize_matching_text(expected_name)
    if not text_norm or not name_norm:
        return 0
    if name_norm in text_norm:
        return 1
    tokens = [
        normalize_matching_text(token)
        for token in (expected_name or "").split()
        if len(normalize_matching_text(token)) >= 3
    ]
    token_hits = sum(1 for token in tokens if token and token in text_norm)
    token_score = (token_hits / len(tokens)) if tokens else 0
    similarity = SequenceMatcher(None, name_norm, text_norm).ratio()
    return max(token_score, similarity)


def parse_amount_candidates(text):
    candidates = []
    for raw in re.findall(r"\d[\d\s.,]{2,14}", text or ""):
        digits_only = re.sub(r"\D", "", raw)
        if not digits_only:
            continue
        try:
            candidates.append(Decimal(digits_only))
        except Exception:
            continue
    return candidates


def extract_matching_phone(text, expected_phone):
    expected_normalized = normalize_phone_number(expected_phone)
    expected_digits = re.sub(r"\D", "", expected_normalized)
    if not expected_digits:
        return ""
    for raw in re.findall(r"\+?\d[\d\s()-]{8,}\d", text or ""):
        candidate = normalize_phone_number(raw)
        candidate_digits = re.sub(r"\D", "", candidate)
        if candidate_digits == expected_digits:
            return candidate
        if candidate_digits.endswith(expected_digits[-10:]):
            return candidate
    return ""


def parse_timestamp(text):
    patterns = (
        ("%d.%m.%Y %H:%M", r"\b\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}\b"),
        ("%d.%m.%y %H:%M", r"\b\d{2}\.\d{2}\.\d{2}\s+\d{2}:\d{2}\b"),
        ("%d/%m/%Y %H:%M", r"\b\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}\b"),
        ("%Y-%m-%d %H:%M", r"\b\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\b"),
    )
    for fmt, pattern in patterns:
        match = re.search(pattern, text or "")
        if not match:
            continue
        try:
            naive = datetime.strptime(match.group(0), fmt)
            return timezone.make_aware(naive, timezone.get_current_timezone())
        except Exception:
            continue
    return None


def extract_pdf_text(file_path):
    if not PdfReader:
        return ""
    try:
        reader = PdfReader(file_path)
    except Exception:
        return ""
    chunks = []
    for page in reader.pages[:3]:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def extract_image_text(file_path):
    try:
        image = Image.open(file_path)
    except Exception:
        return ""

    processed = ImageOps.autocontrast(image.convert("L"))
    width, height = processed.size
    processed = processed.resize((max(width * 2, width), max(height * 2, height)))
    configs = ("--oem 3 --psm 6", "--oem 3 --psm 11")
    for config in configs:
        try:
            text = pytesseract.image_to_string(processed, lang="rus+kaz+eng", config=config).strip()
        except Exception:
            text = ""
        if text:
            return text
    return ""


def extract_receipt_text(file_path, file_type):
    if file_type == "pdf":
        return extract_pdf_text(file_path)
    if file_type == "image":
        return extract_image_text(file_path)
    return ""


def analyze_receipt_text(extracted_text, expected_amount, expected_phone, expected_name):
    expected_amount_decimal = Decimal(str(expected_amount))
    amount_candidates = parse_amount_candidates(extracted_text)
    amount_detected = next((candidate for candidate in amount_candidates if candidate == expected_amount_decimal), None)
    phone_detected = extract_matching_phone(extracted_text, expected_phone)
    name_score = expected_name_score(extracted_text, expected_name)
    timestamp_detected = parse_timestamp(extracted_text)

    confidence = Decimal("0")
    notes = []
    if amount_detected:
        confidence += Decimal("0.40")
        notes.append("amount matched")
    else:
        notes.append("amount missing or different")

    if phone_detected:
        confidence += Decimal("0.35")
        notes.append("receiver phone matched")
    else:
        notes.append("receiver phone missing")

    if name_score >= 0.66:
        confidence += Decimal("0.20")
        notes.append("receiver name matched approximately")
    elif name_score >= 0.33:
        confidence += Decimal("0.10")
        notes.append("receiver name partially matched")
    else:
        notes.append("receiver name weak")

    if timestamp_detected:
        confidence += Decimal("0.05")
        notes.append("timestamp detected")

    is_validated = bool(
        amount_detected
        and confidence >= Decimal("0.75")
        and (phone_detected or name_score >= 0.66)
    )

    return {
        "amount_detected": amount_detected,
        "receiver_phone_detected": phone_detected,
        "receiver_name_detected": expected_name if name_score >= 0.33 else "",
        "timestamp_detected": timestamp_detected,
        "validation_confidence": float(confidence),
        "is_validated": is_validated,
        "validation_notes": "; ".join(notes),
        "name_score": float(name_score),
    }


def build_base_username(name, phone_number):
    base = slugify(name or "", allow_unicode=True).replace("-", "")
    if not base:
        base = "oqyai"
    suffix = re.sub(r"\D", "", phone_number or "")[-4:] or "user"
    return f"{base[:20]}{suffix}"[:30]


def generate_password(length=10):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def parse_meta_timestamp(timestamp_value):
    if not timestamp_value:
        return timezone.now()
    try:
        return datetime.fromtimestamp(int(timestamp_value), tz=dt_timezone.utc)
    except Exception:
        return timezone.now()


def clip_text(value, limit=300):
    value = (value or "").strip()
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}…"

import fcntl
import hashlib
import json
import logging
import os
import re
import time
from difflib import SequenceMatcher
from pathlib import Path

import django
import requests
from dotenv import load_dotenv
from openai import OpenAI
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ============================================================
# BASE
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "english_course.settings",
)

django.setup()

from django.db import connection, IntegrityError
from django.utils import timezone


# ============================================================
# ENV
# ============================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
THREADS_USER_ID = os.getenv("THREADS_USER_ID")

# GPT-6 Luna is a low-cost model for high-volume text generation.
# OPENAI_MODEL in .env takes precedence over this default.
OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-6-luna",
)

# 1 = generate only (safe default)
# 0 = generate + publish
THREADS_DRY_RUN = (
    os.getenv("THREADS_DRY_RUN", "1") == "1"
)


# ============================================================
# CONTENT / POST LIMIT
# ============================================================

# Keep a margin below Threads' 500-character text-post limit.
# App-store URLs are intentionally NOT appended to every post.
# Put the app links in the Threads profile bio and track bio-link clicks.
MAX_POST_CHARACTERS = 460
CONTENT_BUDGET = MAX_POST_CHARACTERS
TARGET_CONTENT_CHARACTERS = 380

# A brand mention is allowed only when no recent post promoted OqyAI.
PROMO_COOLDOWN_POSTS = 5
PROMPT_HISTORY_LIMIT = 12

# Topic tags are supported by the Threads publishing API. Disable with
# THREADS_ADD_TOPIC_TAG=0 if your API version/account rejects them.
THREADS_ADD_TOPIC_TAG = (
    os.getenv("THREADS_ADD_TOPIC_TAG", "1") == "1"
)

TOPIC_TAGS_BY_PILLAR = {
    "KZ_HUMOR": "Comedy",
    "ANECDOTE": "Stories",
    "LOCAL_SUPPORT": "Kazakhstan",
    "KZ_LIFE": "Lifestyle",
    "DISCUSSION": "Culture",
    "ENGLISH_BRIDGE": "Language Learning",
}

# Weighted rotation: approximately 30/25/15/15/10/5 percent.
PILLAR_WEIGHTS = {
    "KZ_HUMOR": 0.30,
    "ANECDOTE": 0.25,
    "LOCAL_SUPPORT": 0.15,
    "KZ_LIFE": 0.15,
    "DISCUSSION": 0.10,
    "ENGLISH_BRIDGE": 0.05,
}


# ============================================================
# HISTORY / DUPLICATE
# ============================================================

# Agent reads ONLY its own latest N published posts.
RECENT_POST_LIMIT = 30

# Structured Outputs and local validation remove most retry causes,
# so we no longer need a large retry budget.
# One normal generation and at most one retry for a duplicate/invalid result.
MAX_GENERATION_ATTEMPTS = 2

# Hard cap on generated tokens: keeps accidental long answers inexpensive.
OPENAI_MAX_OUTPUT_TOKENS = int(
    os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "450")
)

TOPIC_SIMILARITY_THRESHOLD = 0.82
HOOK_SIMILARITY_THRESHOLD = 0.82
CTA_SIMILARITY_THRESHOLD = 0.84
CONTENT_SIMILARITY_THRESHOLD = 0.78


# ============================================================
# DATABASE
# ============================================================

DB_TABLE = "threads_agent_posts"

DB_INDEX_NAME = "idx_threads_agent_source_status_pub"


# ============================================================
# LOCK
# ============================================================

LOCK_FILE = "/tmp/oqyai_threads_agent.lock"


# ============================================================
# LOGGING
# ============================================================

LOG_FILE = "/tmp/oqyai_threads_agent.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(
            LOG_FILE,
            encoding="utf-8",
        ),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(
    "oqyai_threads_agent"
)


# ============================================================
# VALIDATION
# ============================================================

if not OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY .env ішінде табылмады"
    )

if not THREADS_ACCESS_TOKEN:
    raise ValueError(
        "THREADS_ACCESS_TOKEN .env ішінде табылмады"
    )

if not THREADS_USER_ID:
    raise ValueError(
        "THREADS_USER_ID .env ішінде табылмады"
    )

logger.info("✅ OpenAI API кілті сәтті жүктелді!")


# ============================================================
# OPENAI
# ============================================================

openai_client = OpenAI(
    api_key=OPENAI_API_KEY
)

# Structured Outputs schema: guarantees valid JSON with exactly these
# fields, so we no longer pay for a retry just because the model wrapped
# the JSON in markdown or forgot a field.
POST_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "pillar": {
            "type": "string",
            "enum": [
                "KZ_HUMOR",
                "ANECDOTE",
                "LOCAL_SUPPORT",
                "KZ_LIFE",
                "DISCUSSION",
                "ENGLISH_BRIDGE",
            ],
        },
        "topic": {"type": "string"},
        "format": {"type": "string"},
        "hook": {"type": "string"},
        "body": {"type": "string"},
        "promotion": {
            "type": "string",
            "enum": ["none", "soft"],
        },
        "cta": {"type": "string"},
    },
    "required": [
        "pillar",
        "topic",
        "format",
        "hook",
        "body",
        "promotion",
        "cta",
    ],
    "additionalProperties": False,
}


# ============================================================
# HTTP CLIENT
# ============================================================

retry_strategy = Retry(
    total=4,
    connect=4,
    read=4,
    status=4,
    backoff_factor=1,
    status_forcelist=(
        429,
        500,
        502,
        503,
        504,
    ),
    # Threads publishing uses POST. Automatic retries can create duplicate
    # containers/posts when the server succeeds but the response is lost.
    # Retry only idempotent GET requests automatically.
    allowed_methods=frozenset({"GET"}),
    respect_retry_after_header=True,
)

http = requests.Session()

http.mount(
    "https://",
    HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,
        pool_maxsize=10,
    ),
)

http.mount(
    "http://",
    HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=10,
        pool_maxsize=10,
    ),
)


# ============================================================
# TEXT HELPERS
# ============================================================

def normalize_text(text: str) -> str:
    """
    Used for duplicate/similarity checks.
    URLs, punctuation and repeated spaces are removed.

    Local computation only — never calls OpenAI.
    """

    text = text.lower()

    text = re.sub(
        r"https?://\S+",
        "",
        text,
    )

    text = re.sub(
        r"[^\w\s]",
        " ",
        text,
        flags=re.UNICODE,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def text_hash(text: str) -> str:
    return hashlib.sha256(
        normalize_text(text).encode("utf-8")
    ).hexdigest()


def similarity(
    first: str,
    second: str,
) -> float:
    """
    Local difflib comparison only — never calls OpenAI.
    """
    return SequenceMatcher(
        None,
        normalize_text(first),
        normalize_text(second),
    ).ratio()


def parse_json_response(text: str) -> dict:
    """
    Structured Outputs (see POST_JSON_SCHEMA) should already guarantee
    clean JSON, so this rarely has to do real work. Kept as a defensive
    fallback in case a response ever comes back malformed.
    """

    cleaned = text.strip()

    cleaned = re.sub(
        r"^```json\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"^```\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    try:
        return json.loads(cleaned)

    except json.JSONDecodeError:

        match = re.search(
            r"\{.*\}",
            cleaned,
            flags=re.DOTALL,
        )

        if not match:
            raise ValueError(
                "OpenAI JSON response parse failed"
            )

        return json.loads(
            match.group(0)
        )


# ============================================================
# DATABASE SETUP + SAFE MIGRATION
# ============================================================

def get_table_columns():
    """
    Returns current DB columns.
    Works with SQLite and MySQL.
    """

    vendor = connection.vendor

    with connection.cursor() as cursor:

        if vendor == "sqlite":

            cursor.execute(
                f"PRAGMA table_info({DB_TABLE})"
            )

            return {
                row[1]
                for row in cursor.fetchall()
            }

        if vendor == "mysql":

            cursor.execute(
                f"SHOW COLUMNS FROM {DB_TABLE}"
            )

            return {
                row[0]
                for row in cursor.fetchall()
            }

        raise RuntimeError(
            f"Unsupported database: {vendor}"
        )


def get_existing_index_names():
    """
    Returns current index names on DB_TABLE.
    Works with SQLite and MySQL.
    """

    vendor = connection.vendor

    with connection.cursor() as cursor:

        if vendor == "sqlite":

            cursor.execute(
                f"PRAGMA index_list({DB_TABLE})"
            )

            # PRAGMA index_list columns: seq, name, unique, origin, partial
            return {
                row[1]
                for row in cursor.fetchall()
            }

        if vendor == "mysql":

            cursor.execute(
                f"SHOW INDEX FROM {DB_TABLE}"
            )

            # SHOW INDEX columns: ... Key_name is index 2
            return {
                row[2]
                for row in cursor.fetchall()
            }

        raise RuntimeError(
            f"Unsupported database: {vendor}"
        )


def ensure_database_indexes():
    """
    Adds a composite index for the exact query pattern used by
    get_recent_published_posts() (source + status + ordering by
    published_at). Safe to call every run — it's a no-op once the
    index exists.
    """

    existing = get_existing_index_names()

    if DB_INDEX_NAME in existing:
        return

    with connection.cursor() as cursor:

        cursor.execute(
            f"""
            CREATE INDEX {DB_INDEX_NAME}
            ON {DB_TABLE} (source, status, published_at)
            """
        )

    logger.info(
        "Created DB index: %s",
        DB_INDEX_NAME,
    )


def ensure_database_table():
    """
    Creates the table if necessary.

    Also safely adds missing columns to an older version
    of the table, and ensures the query index exists.

    Does NOT touch Django models/migrations.
    """

    vendor = connection.vendor

    with connection.cursor() as cursor:

        if vendor == "mysql":

            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {DB_TABLE} (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,

                    topic VARCHAR(255) NOT NULL,

                    content_format VARCHAR(100) NOT NULL,

                    hook VARCHAR(500) NULL,

                    cta VARCHAR(500) NULL,

                    post_text TEXT NOT NULL,

                    thread_id VARCHAR(100) NULL,

                    container_id VARCHAR(100) NULL,

                    status VARCHAR(30) NOT NULL,

                    source VARCHAR(30) NOT NULL,

                    content_hash CHAR(64) NOT NULL,

                    published_at DATETIME(6) NULL,

                    created_at DATETIME(6) NOT NULL,

                    error_message TEXT NULL,

                    UNIQUE KEY uq_threads_agent_hash (
                        content_hash
                    ),

                    INDEX idx_threads_agent_status (
                        status
                    ),

                    INDEX idx_threads_agent_created (
                        created_at
                    )

                ) ENGINE=InnoDB
                DEFAULT CHARSET=utf8mb4
                COLLATE=utf8mb4_unicode_ci
                """
            )

        elif vendor == "sqlite":

            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {DB_TABLE} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    topic VARCHAR(255) NOT NULL,

                    content_format VARCHAR(100) NOT NULL,

                    hook VARCHAR(500),

                    cta VARCHAR(500),

                    post_text TEXT NOT NULL,

                    thread_id VARCHAR(100),

                    container_id VARCHAR(100),

                    status VARCHAR(30) NOT NULL,

                    source VARCHAR(30) NOT NULL,

                    content_hash VARCHAR(64) NOT NULL UNIQUE,

                    published_at DATETIME,

                    created_at DATETIME NOT NULL,

                    error_message TEXT
                )
                """
            )

        else:

            raise RuntimeError(
                f"Unsupported database: {vendor}"
            )

    # --------------------------------------------------------
    # Migration for older versions
    # --------------------------------------------------------

    columns = get_table_columns()

    vendor = connection.vendor

    missing_columns = {
        "hook": "VARCHAR(500)",
        "cta": "VARCHAR(500)",
        "source": "VARCHAR(30)",
        "error_message": "TEXT",
        "container_id": "VARCHAR(100)",
        "published_at": (
            "DATETIME(6)"
            if vendor == "mysql"
            else "DATETIME"
        ),
    }

    with connection.cursor() as cursor:

        for column, column_type in missing_columns.items():

            if column not in columns:

                logger.info(
                    "Adding missing DB column: %s",
                    column,
                )

                cursor.execute(
                    f"""
                    ALTER TABLE {DB_TABLE}
                    ADD COLUMN {column}
                    {column_type}
                    """
                )

    ensure_database_indexes()

    logger.info(
        "Database table ready: %s (%s)",
        DB_TABLE,
        vendor,
    )


# ============================================================
# AGENT HISTORY
# ============================================================

def get_recent_published_posts(
    limit=RECENT_POST_LIMIT,
):
    """
    IMPORTANT:
    Only posts created by THIS AGENT are returned.
    Manual Threads posts are intentionally ignored.

    This is a plain DB query — it costs nothing on the OpenAI side.
    """

    with connection.cursor() as cursor:

        query = f"""
        SELECT
            topic,
            content_format,
            hook,
            cta,
            post_text,
            created_at
        FROM {DB_TABLE}
        WHERE
            status = 'published'
            AND source = 'agent'
        ORDER BY
            COALESCE(
                published_at,
                created_at
            ) DESC,
            id DESC
        LIMIT %s
        """

        cursor.execute(
            query,
            [limit],
        )

        rows = cursor.fetchall()

    posts = []

    for row in rows:

        (
            topic,
            content_format,
            hook,
            cta,
            post_text,
            created_at,
        ) = row

        posts.append(
            {
                "topic": topic or "",
                "format": content_format or "",
                "hook": hook or "",
                "cta": cta or "",
                "text": post_text or "",
                "created_at": str(
                    created_at
                ),
            }
        )

    return posts


def hash_exists(
    content_hash: str,
):
    """
    Exact duplicate check against the agent history.
    Plain DB query — no OpenAI cost.
    """

    with connection.cursor() as cursor:

        query = f"""
        SELECT id
        FROM {DB_TABLE}
        WHERE content_hash = %s
        LIMIT 1
        """

        cursor.execute(
            query,
            [content_hash],
        )

        return cursor.fetchone() is not None


# ============================================================
# SAVE / UPDATE
# ============================================================

def save_generated_post(
    topic,
    content_format,
    hook,
    cta,
    post_text,
    content_hash,
):
    now = timezone.now()

    query = f"""
    INSERT INTO {DB_TABLE} (
        topic,
        content_format,
        hook,
        cta,
        post_text,
        status,
        source,
        content_hash,
        created_at
    )
    VALUES (
        %s,
        %s,
        %s,
        %s,
        %s,
        'generated',
        'agent',
        %s,
        %s
    )
    """

    try:

        with connection.cursor() as cursor:

            cursor.execute(
                query,
                [
                    topic,
                    content_format,
                    hook,
                    cta,
                    post_text,
                    content_hash,
                    now,
                ],
            )

            return cursor.lastrowid

    except IntegrityError as exc:

        # Another process (or a rare race) inserted the exact same
        # content_hash between our duplicate check and this insert.
        raise RuntimeError(
            f"Duplicate content_hash on insert: {exc}"
        ) from exc


def mark_post_published(
    row_id,
    thread_id,
    container_id,
):
    now = timezone.now()

    with connection.cursor() as cursor:

        query = f"""
        UPDATE {DB_TABLE}
        SET
            status = 'published',
            thread_id = %s,
            container_id = %s,
            published_at = %s
        WHERE id = %s
        """

        cursor.execute(
            query,
            [
                thread_id,
                container_id,
                now,
                row_id,
            ],
        )


def mark_post_failed(
    row_id,
    error_message,
):
    with connection.cursor() as cursor:

        query = f"""
        UPDATE {DB_TABLE}
        SET
            status = 'failed',
            error_message = %s
        WHERE id = %s
        """

        cursor.execute(
            query,
            [
                str(error_message)[:10000],
                row_id,
            ],
        )


# ============================================================
# OPENAI PROMPT
# ============================================================
#
# COST NOTE:
# Everything below STATIC_PROMPT_HEADER is fixed text — it never
# changes between calls (it only depends on module-level constants).
# By putting it FIRST and appending the per-run history/rejection
# data AFTER it, repeated calls (retries within one run, and separate
# hourly runs) can hit OpenAI's automatic prompt caching on this
# shared prefix, since GPT-5-family models cache long, identical
# prefixes for a while (no code change needed beyond keeping this
# text byte-for-byte identical across calls).
# ============================================================

STATIC_PROMPT_HEADER = f"""
Сен Қазақстандағы Threads аудиториясына арналған OqyAI контент-агентсің.

OqyAI — қазақша сөйлейтін адамдарға ағылшын тілін үйрететін мобильді қосымша.
Бірақ бұл аккаунттың басты мақсаты әр постта курс сату емес. Алдымен адамдар
оқитын, күлетін, пікір жазатын және бөлісетін қазақша медиа-аккаунт қалыптастыр.
OqyAI-ды тек шынайы әрі сирек контексте таныстыр.

НЕГІЗГІ ЕРЕЖЕЛЕР
- Контенттің басым бөлігі қазақ тілінде, ауызекі әрі табиғи болсын.
- Пост Threads-ке арнайы жазылсын; Instagram/TikTok жарнамасының мәтініндей болма.
- Бір пост = бір идея. Күштеп ағылшын сабағын қоспа.
- Жалған статистика, ойдан шығарылған нақты адам пікірі, жалған клиент оқиғасы,
  жалған жетістік, тексерілмеген жаңалық немесе дәйексөз ойлап таппа.
- Ойдан шығарылған анекдотты шынайы болған оқиға ретінде ұсынба.
- Патриоттық контент мәдениет, тіл, отандық өнім, жергілікті кәсіпкер мен
  қоғамдастықты шынайы қолдауға негізделсін; кінәлау/ұялту/мәжбүрлеу болмауы керек.
- Этносқа, дінге, өңірге, жынысқа, мүгедектікке қатысты кемсітетін әзіл жасама.
- Саяси үгіт, дау тудыратын жалған айыптау және трагедияны әзілге айналдыру жоқ.
- Hashtag жазба. Артық emoji қолданба. URL ешқашан жазба.
- Бірдей hook, сюжет, punchline немесе соңғы сұрақты қайталама.

КОНТЕНТ ПИЛЛАРЛАРЫ
1. KZ_HUMOR — Қазақстандағы ортақ күнделікті жағдайлар, мем, relatable юмор.
2. ANECDOTE — қысқа анекдот, диалог, күтпеген финалы бар шағын оқиға.
3. LOCAL_SUPPORT — қазақ тілі, Қазақстанда жасалған өнімдер, отандық стартаптар,
   жергілікті адамдар мен бастамаларды шынайы қолдау.
4. KZ_LIFE — студенттік өмір, жұмыс, отбасы, ақша, достар, қала/ауыл тұрмысы.
5. DISCUSSION — адамдардың нақты тәжірибесін сұрайтын мәдениетті пікірталас.
6. ENGLISH_BRIDGE — ағылшынға қатысты әзіл/оқиға/пайдалы ой. Тек сирек қолдан.

ПОСТТЫҢ ҚҰРЫЛЫМЫ
- hook: бірінші жолдағы қызықты, бірақ табиғи бастама.
- body: негізгі оқиға, әзіл, ой немесе сұрақ. Hook-ты қайталама.
- Соңында пікір сұрау қажет болса ғана бір қысқа сұрақ қой.
- Әр постқа міндетті CTA қоспа.
- Постты әдейі ұзартпа. Мақсатты ұзындық шамамен {TARGET_CONTENT_CHARACTERS} таңба,
  абсолют максимум {CONTENT_BUDGET} таңба.

OQYAI ЖАРНАМАСЫ
- Тікелей сату, баға, жеңілдік, App Store/Google Play URL, "сатып ал" деген CTA жоқ.
- promotion="none" болса, cta бос жол болсын.
- promotion="soft" тек осы іске қосуда рұқсат берілсе ғана қолданылсын.
- Soft mention OqyAI-ды шынайы контексте бір рет атап, қысқа әрі сабырлы болсын.
  Мысалы, өнім жасаушының шынайы тәжірибесі немесе ағылшын үйрену жайлы пост.
- OqyAI-ды атап өтпес бұрын оның осы постқа табиғи қатысы бар екеніне көз жеткіз.
- Әр алты посттың шамамен біреуінен жиі брендті атама.

OUTPUT
Тек JSON schema-дағы өрістерді қайтар. Markdown, түсініктеме және қосымша мәтін қоспа.
""".strip()


def extract_pillar(post):
    """The pillar is stored in the existing content_format DB column."""
    value = str(post.get("format", ""))
    return value.split("|", 1)[0].strip().upper()


def choose_target_pillar(recent_posts):
    """Choose a weighted pillar while avoiding the two latest pillars."""
    from collections import Counter

    window = recent_posts[:20]
    if not window:
        return "KZ_HUMOR"

    counts = Counter(extract_pillar(post) for post in window)
    recent_two = {extract_pillar(post) for post in recent_posts[:2]}
    total = max(len(window), 1)

    candidates = [name for name in PILLAR_WEIGHTS if name not in recent_two]
    if not candidates:
        candidates = list(PILLAR_WEIGHTS)

    def score(name):
        observed_share = counts.get(name, 0) / total
        target_share = PILLAR_WEIGHTS[name]
        return target_share - observed_share

    return max(candidates, key=score)


def is_promotion_allowed(recent_posts):
    """Allow a soft brand mention only after a five-post promotion cooldown."""
    return not any(
        str(post.get("cta", "")).strip()
        for post in recent_posts[:PROMO_COOLDOWN_POSTS]
    )


def build_prompt_history(recent_posts):
    """Send a short digest; full text is checked locally for duplicates."""
    if not recent_posts:
        return "Бұл агент әлі пост жариялаған жоқ."

    lines = []
    selected = list(reversed(recent_posts[:PROMPT_HISTORY_LIMIT]))
    for index, post in enumerate(selected, start=1):
        lines.append(
            f"{index}. [{post['format']}] {post['topic']} | "
            f"hook: {post['hook']} | cta: {post['cta']}"
        )
    return "\n".join(lines)


def build_generation_prompt(recent_posts, rejected_reasons):
    """Keep the fixed prompt first for prompt-cache reuse."""
    target_pillar = choose_target_pillar(recent_posts)
    promotion_allowed = is_promotion_allowed(recent_posts)
    history_block = build_prompt_history(recent_posts)
    rejected_block = (
        "\n".join(f"- {reason}" for reason in rejected_reasons)
        if rejected_reasons else "Жоқ."
    )

    dynamic_section = f"""

ОСЫ ПОСТҚА АРНАЛҒАН МІНДЕТТІ ПАРАМЕТРЛЕР
- Таңдалған pillar: {target_pillar}. Дәл осы мәнді JSON-да қайтар.
- Soft promotion рұқсат етілген бе: {"ИӘ" if promotion_allowed else "ЖОҚ"}.
  Егер ЖОҚ болса, promotion="none" және cta="" міндетті.
- Қысқа әрі түпнұсқа идея таңда. Бұрынғы посттарға ұқсатпа.

СОҢҒЫ ПОСТТАР (ең көбі {PROMPT_HISTORY_LIMIT})
{history_block}

ОСЫ ІСКЕ ҚОСУДА ҚАБЫЛДАНБАҒАН НҰСҚАЛАР
{rejected_block}
"""
    return STATIC_PROMPT_HEADER + dynamic_section


# ============================================================
# AI GENERATION
# ============================================================

def generate_candidate(recent_posts, rejected_reasons):
    prompt = build_generation_prompt(recent_posts, rejected_reasons)
    response = openai_client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
        max_output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
        **(
            {"reasoning": {"effort": os.getenv("OPENAI_REASONING_EFFORT", "none")}}
            if OPENAI_MODEL.startswith("gpt-6")
            else {}
        ),
        text={
            "format": {
                "type": "json_schema",
                "name": "oqyai_threads_post",
                "schema": POST_JSON_SCHEMA,
                "strict": True,
            }
        },
        store=False,
    )

    usage = getattr(response, "usage", None)
    if usage:
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        details = getattr(usage, "input_tokens_details", None)
        cached_tokens = getattr(details, "cached_tokens", 0) if details else 0
        logger.info(
            "OpenAI usage: input=%s output=%s cached_input=%s",
            input_tokens,
            output_tokens,
            cached_tokens,
        )

    return parse_json_response(response.output_text)



# ============================================================
# BUILD FINAL POST
# ============================================================

def build_final_post(candidate, recent_posts=None):
    pillar = str(candidate.get("pillar", "")).strip().upper()
    topic = str(candidate.get("topic", "")).strip()
    content_format = str(candidate.get("format", "")).strip()
    hook = str(candidate.get("hook", "")).strip()
    body = str(candidate.get("body", "")).strip()
    promotion = str(candidate.get("promotion", "none")).strip().lower()
    cta = str(candidate.get("cta", "")).strip()

    if pillar not in PILLAR_WEIGHTS:
        raise ValueError(f"Белгісіз контент pillar: {pillar}")
    if recent_posts is not None:
        expected_pillar = choose_target_pillar(recent_posts)
        if pillar != expected_pillar:
            raise ValueError(
                f"Pillar сәйкес емес: expected={expected_pillar}, got={pillar}"
            )
        if promotion == "soft" and not is_promotion_allowed(recent_posts):
            raise ValueError("OqyAI жарнамасына cooldown әлі аяқталған жоқ")
    if not topic or not content_format or not hook or not body:
        raise ValueError("topic, format, hook және body бос болмауы керек")
    if promotion not in {"none", "soft"}:
        raise ValueError("promotion тек none немесе soft болуы керек")

    # Do not allow URLs in generated text. The profile bio carries the app links.
    for field_name, field_value in (("hook", hook), ("body", body), ("cta", cta)):
        if re.search(r"(?:https?://|www\.)", field_value, flags=re.IGNORECASE):
            raise ValueError(f"{field_name} ішінде URL бар")

    brand_mentioned = bool(
        re.search(r"oqy\s*ai", f"{hook} {body} {cta}", flags=re.IGNORECASE)
    )
    if brand_mentioned and promotion != "soft":
        raise ValueError("OqyAI атауы тек promotion=soft кезінде қолданылуы керек")

    if promotion == "none":
        cta = ""
    elif not cta:
        raise ValueError("promotion=soft болғанда cta бос болмауы керек")

    if len(cta) > 110:
        raise ValueError("cta тым ұзын")

    if body.lower().startswith(hook.lower()):
        body = body[len(hook):].lstrip(" \n.!?—-")
    if not body:
        raise ValueError("body hook-ты алып тастағаннан кейін бос қалды")

    final_post = f"{hook}\n{body}".strip()
    if cta:
        final_post += f"\n\n{cta}"

    final_characters = len(final_post)
    if final_characters > MAX_POST_CHARACTERS:
        raise ValueError(
            f"Final post too long: {final_characters} chars "
            f"(max {MAX_POST_CHARACTERS})"
        )

    # Store the pillar in the existing content_format column, avoiding a DB migration.
    stored_format = f"{pillar}|{content_format}|promo:{promotion}"[:100]

    return {
        "topic": topic,
        "format": stored_format,
        "pillar": pillar,
        "topic_tag": TOPIC_TAGS_BY_PILLAR.get(pillar),
        "hook": hook,
        "cta": cta,
        "text": final_post,
        "characters": final_characters,
    }



# ============================================================
# DUPLICATE CHECK
# ============================================================

def check_duplicate(
    candidate,
    recent_posts,
):
    """
    Entirely local (hashing + difflib.SequenceMatcher). No OpenAI
    calls happen here — checking duplicates costs zero API tokens,
    no matter how large recent_posts or the agent's history gets.
    """

    candidate_text = candidate["text"]

    candidate_topic = normalize_text(
        candidate["topic"]
    )

    candidate_hash = text_hash(
        candidate_text
    )

    # --------------------------------------------------------
    # Exact duplicate against entire agent history (DB query)
    # --------------------------------------------------------

    if hash_exists(candidate_hash):
        return (
            True,
            "Exact duplicate already exists",
        )

    # --------------------------------------------------------
    # Similarity against latest N agent posts (local difflib)
    # --------------------------------------------------------

    for old in recent_posts:

        old_topic = normalize_text(
            old["topic"]
        )

        if candidate_topic and old_topic:

            topic_ratio = SequenceMatcher(
                None,
                candidate_topic,
                old_topic,
            ).ratio()

            if topic_ratio >= TOPIC_SIMILARITY_THRESHOLD:

                return (
                    True,
                    (
                        "Topic too similar: "
                        f"{old['topic']} "
                        f"({topic_ratio:.2f})"
                    ),
                )

        if candidate["hook"] and old["hook"]:

            hook_ratio = similarity(
                candidate["hook"],
                old["hook"],
            )

            if hook_ratio >= HOOK_SIMILARITY_THRESHOLD:

                return (
                    True,
                    (
                        "Hook too similar "
                        f"({hook_ratio:.2f})"
                    ),
                )

        if candidate["cta"] and old["cta"]:

            cta_ratio = similarity(
                candidate["cta"],
                old["cta"],
            )

            if cta_ratio >= CTA_SIMILARITY_THRESHOLD:

                return (
                    True,
                    (
                        "CTA too similar "
                        f"({cta_ratio:.2f})"
                    ),
                )

        content_ratio = similarity(
            candidate_text,
            old["text"],
        )

        if content_ratio >= CONTENT_SIMILARITY_THRESHOLD:

            return (
                True,
                (
                    "Content too similar "
                    f"({content_ratio:.2f})"
                ),
            )

    return False, None


# ============================================================
# UNIQUE POST
# ============================================================

def generate_unique_post():

    recent_posts = get_recent_published_posts(
        RECENT_POST_LIMIT
    )

    logger.info(
        "Loaded %s recent agent posts",
        len(recent_posts),
    )

    rejected_reasons = []

    for attempt in range(
        1,
        MAX_GENERATION_ATTEMPTS + 1,
    ):

        logger.info(
            "Generating candidate %s/%s",
            attempt,
            MAX_GENERATION_ATTEMPTS,
        )

        try:

            candidate = generate_candidate(
                recent_posts,
                rejected_reasons,
            )

            final_post = build_final_post(
                candidate,
                recent_posts=recent_posts,
            )

            duplicate, reason = check_duplicate(
                final_post,
                recent_posts,
            )

            if duplicate:

                logger.warning(
                    "Candidate rejected: %s",
                    reason,
                )

                rejected_reasons.append(reason)

                continue

            logger.info(
                (
                    "Candidate accepted: "
                    "topic=%s | format=%s | "
                    "characters=%s"
                ),
                final_post["topic"],
                final_post["format"],
                final_post["characters"],
            )

            return final_post

        except Exception as exc:

            reason = f"Candidate error: {exc}"

            logger.warning(reason)

            rejected_reasons.append(reason)

    raise RuntimeError(
        (
            "Could not generate a unique "
            "valid post after "
            f"{MAX_GENERATION_ATTEMPTS} attempts."
        )
    )


# ============================================================
# THREADS API
# ============================================================

def publish_to_threads(
    text,
    topic_tag=None,
):

    # --------------------------------------------------------
    # 1. Create container
    # --------------------------------------------------------

    create_url = (
        f"https://graph.threads.net/v1.0/"
        f"{THREADS_USER_ID}/threads"
    )

    create_data = {
        "media_type": "TEXT",
        "text": text,
        "access_token": THREADS_ACCESS_TOKEN,
    }

    if THREADS_ADD_TOPIC_TAG and topic_tag:
        create_data["topic_tag"] = topic_tag

    logger.info(
        "Creating Threads container (topic_tag=%s)...",
        create_data.get("topic_tag", "disabled"),
    )

    response = http.post(
        create_url,
        data=create_data,
        timeout=30,
    )

    # If Meta explicitly rejects the optional topic tag with HTTP 400,
    # retry once without it. Never retry uncertain 5xx/network failures.
    if response.status_code == 400 and "topic_tag" in create_data:
        logger.warning(
            "Threads rejected topic_tag; retrying once without the tag."
        )
        create_data.pop("topic_tag", None)
        response = http.post(
            create_url,
            data=create_data,
            timeout=30,
        )

    logger.info(
        "Create status: %s",
        response.status_code,
    )

    if not response.ok:

        logger.error(
            "Threads create error: %s",
            response.text,
        )

    response.raise_for_status()

    create_payload = response.json()

    container_id = create_payload.get("id")

    if not container_id:

        raise RuntimeError(
            (
                "Threads container ID missing: "
                f"{create_payload}"
            )
        )

    # Give Threads time to process container.
    time.sleep(1)

    # --------------------------------------------------------
    # 2. Publish container
    # --------------------------------------------------------

    publish_url = (
        f"https://graph.threads.net/v1.0/"
        f"{THREADS_USER_ID}/threads_publish"
    )

    publish_data = {
        "creation_id": container_id,
        "access_token": THREADS_ACCESS_TOKEN,
    }

    logger.info(
        "Publishing container %s...",
        container_id,
    )

    response = http.post(
        publish_url,
        data=publish_data,
        timeout=30,
    )

    logger.info(
        "Publish status: %s",
        response.status_code,
    )

    if not response.ok:

        logger.error(
            "Threads publish error: %s",
            response.text,
        )

    response.raise_for_status()

    publish_payload = response.json()

    thread_id = publish_payload.get("id")

    if not thread_id:

        raise RuntimeError(
            (
                "Threads ID missing: "
                f"{publish_payload}"
            )
        )

    return {
        "container_id": container_id,
        "thread_id": thread_id,
    }


# ============================================================
# LOCK
# ============================================================

def acquire_lock():

    handle = open(
        LOCK_FILE,
        "w",
        encoding="utf-8",
    )

    try:

        fcntl.flock(
            handle,
            fcntl.LOCK_EX | fcntl.LOCK_NB,
        )

    except BlockingIOError:

        handle.close()

        raise RuntimeError(
            (
                "Another Threads agent "
                "instance is already running."
            )
        )

    return handle


# ============================================================
# MAIN RUN
# ============================================================

def run_agent():

    logger.info(
        "=========================================="
    )

    logger.info(
        "OqyAI Threads Agent started"
    )

    logger.info(
        "=========================================="
    )

    # 1. Ensure table/schema/indexes.
    ensure_database_table()

    # IMPORTANT:
    # We DO NOT read Threads history.
    # We ONLY read agent-created DB history (source='agent').

    # 2. Generate a unique post.
    final_post = generate_unique_post()

    logger.info(
        "\n--- GENERATED POST ---\n%s",
        final_post["text"],
    )

    logger.info(
        "Characters: %s / %s",
        final_post["characters"],
        MAX_POST_CHARACTERS,
    )

    # 3. Dry-run mode.
    if THREADS_DRY_RUN:

        logger.info("THREADS_DRY_RUN=1")
        logger.info("Nothing will be published.")

        return

    # 4. Exact hash.
    content_hash = text_hash(
        final_post["text"]
    )

    # 5. Final duplicate check (defense in depth).
    if hash_exists(content_hash):

        raise RuntimeError(
            "Exact duplicate detected before publish."
        )

    # 6. Save generated post.
    row_id = save_generated_post(
        topic=final_post["topic"],
        content_format=final_post["format"],
        hook=final_post["hook"],
        cta=final_post["cta"],
        post_text=final_post["text"],
        content_hash=content_hash,
    )

    logger.info(
        "Generated post saved. row_id=%s",
        row_id,
    )

    # 7. Publish.
    try:

        result = publish_to_threads(
            final_post["text"],
            topic_tag=final_post.get("topic_tag"),
        )

        # 8. Mark published.
        mark_post_published(
            row_id=row_id,
            thread_id=result["thread_id"],
            container_id=result["container_id"],
        )

        logger.info("✅ Threads post published")

        logger.info(
            "Thread ID: %s",
            result["thread_id"],
        )

    except Exception as exc:

        logger.exception(
            "❌ Threads publishing failed"
        )

        mark_post_failed(
            row_id=row_id,
            error_message=str(exc),
        )

        raise


# ============================================================
# ENTRYPOINT
# ============================================================

def main():

    lock_handle = None

    try:

        lock_handle = acquire_lock()

        run_agent()

    except Exception as exc:

        logger.exception(
            "Agent failed: %s",
            exc,
        )

        raise

    finally:

        if lock_handle is not None:

            try:

                fcntl.flock(
                    lock_handle,
                    fcntl.LOCK_UN,
                )

            finally:

                lock_handle.close()


if __name__ == "__main__":
    main()

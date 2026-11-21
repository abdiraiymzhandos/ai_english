"""Current CRM classifications over the report population and retained evidence."""
from collections import Counter
import re

from lessons.services.registration_notifications import whatsapp_digits

SEGMENT_LABELS = {
    'HOT': 'HOT — Ыстық клиент', 'WARM': 'WARM — Жылы клиент',
    'COLD': 'COLD — Суық клиент', 'PAID': 'PAID — Ақылы клиент',
}
PRIORITIES = {'HOT': 'Жоғары', 'WARM': 'Орташа', 'COLD': 'Төмен', 'PAID': 'Сатып алған'}
FILTERS = {
    '': 'Барлығы', **SEGMENT_LABELS, 'registered': 'Сабақ ашқаны тіркелмеген',
    'opened': 'Сабақ ашылған, аяқтауы жоқ', 'one': 'Бір тегін сабақ', 'two': 'Екі тегін сабақ',
    'three': 'Үш тегін сабақ, ақысыз', 'no_view': 'Үш тегін сабақ, ұсыныс көргені тіркелмеген',
    'view': 'Ұсынысты көрді, сатып алу батырмасын басқаны тіркелмеген',
    'click': 'Сатып алуды таңдады, төлем расталмаған', 'wa': 'WhatsApp-қа өтті, ақысыз',
    'buyer': 'Төлемі расталған',
}
SORTS = {'priority': 'Байланысу кезегі', 'last': 'Соңғы белсенділік', 'joined': 'Тіркелген күні',
         'completed': 'Аяқталған сабақтар', 'views': 'Ұсынысты көру саны', 'clicks': 'Сатып алу батырмасын басу саны'}
SUMMARY_LABELS = {
    **SEGMENT_LABELS,
    'unpaid_intent': 'Unpaid accounts with retained purchase click or handoff',
    'unpaid_three': 'Unpaid accounts with all three saved free passes on one track',
    'unpaid_view_unconfirmed': 'Unpaid accounts with retained paywall view and no confirmed purchase',
    'handoff_unconfirmed': 'Accounts with retained WhatsApp handoff and no confirmed purchase',
}
INTENT_KINDS = ('lesson_opened', 'paywall_viewed', 'paywall_purchase_clicked', 'whatsapp_opened')


def classify(user, counts):
    opened, views, clicks, handoffs = (counts.get(kind, 0) for kind in INTENT_KINDS)
    access, free, verified = user['access'], user['free_count'], bool(user['confirmed_at'])
    if access:
        segment = 'PAID'
    elif clicks or handoffs:
        segment = 'HOT'
    elif free == 3 or views:
        segment = 'WARM'
    else:
        segment = 'COLD'
    flags = {'registered': not opened, 'opened': opened and not user['completed'], 'one': free == 1,
             'two': free == 2, 'three': free == 3 and not access, 'no_view': free == 3 and not views,
             'view': views and not clicks, 'click': clicks and not verified,
             'wa': handoffs and not access, 'buyer': verified}
    user.update(segment=segment, segment_label=SEGMENT_LABELS[segment], priority=PRIORITIES[segment],
                flags={key for key, value in flags.items() if value} | {segment},
                views=views, clicks=clicks, handoffs=handoffs)


def select_customers(users, params, contacts):
    segment = params.get('segment', '')
    term = params.get('q', '').strip().casefold()[:150]
    phone_query = re.sub(r'[ ()+\-]', '', term)

    def matches(user):
        if not term or term == str(user['id']):
            return True
        if not contacts:
            return False
        digits = whatsapp_digits(user['phone'])
        return (term in user['name'].casefold() or
                (phone_query.isascii() and phone_query.isdigit() and
                 (phone_query in re.sub(r'\D', '', user['phone']) or phone_query in digits or
                  (phone_query.startswith('8') and '7' + phone_query[1:] in digits))))
    selected = [u for u in users if (not segment or segment in u['flags']) and matches(u)]
    sort = params.get('sort', 'priority')
    def order(u):
        recent = -u['last'].timestamp() if u['last'] else float('inf')
        if sort in ('last', 'joined'):
            return (recent if sort == 'last' else -u['joined'].timestamp(), u['id'])
        if sort in ('completed', 'views', 'clicks'):
            return (-u[sort], recent, u['id'])
        return (list(PRIORITIES).index(u['segment']), recent, u['id'])
    return sorted(selected, key=order)


def summary(users):
    counts = Counter(u['segment'] for u in users)
    return {**{s: counts[s] for s in SEGMENT_LABELS}, 'unpaid_intent': counts['HOT'],
            'unpaid_three': sum('three' in u['flags'] for u in users),
            'unpaid_view_unconfirmed': sum(bool(u['views'] and not u['access'] and not u['confirmed_at']) for u in users),
            'handoff_unconfirmed': sum(bool(u['handoffs'] and not u['confirmed_at']) for u in users)}

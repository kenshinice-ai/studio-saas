"""Everything the showcase tenant says, in one place, in both languages.

``reset_professional_demo.py`` used to carry its own copy inline, which is how
the live tenant ended up publishing works titled ``Test`` and ``fasd``: the
seeder filled the CMS side (courses, students, attendance) and left the PORTAL
side — hero, principal, about, the studio's own work — to whoever typed into
the console last.

So the copy lives here as data. The seeder is plumbing; this file is the
studio. Adding a work, a class or a question means editing one literal, and
nothing in the seeder has to know what it says.

Every visitor-facing string is a ``{"zh": ..., "en": ...}`` pair. The portal
switches language client-side and the server strips the other half out of the
static pages, so a string that exists in only one language is a page that is
half-empty in the other.

── On the identity ────────────────────────────────────────────────────────

This studio is fictional. It borrows its SHAPE from a real Melbourne painting
studio — adult classes, colour as rest, an unhurried voice — and invents every
particular. Notably it does not borrow the real founder's biography: putting a
real person's real credentials on a demonstration tenant is impersonation, not
seeding. The principal is ``Janet M``, a deliberately partial name that points
at nobody.

── On the character limits ────────────────────────────────────────────────

The numbers in the comments are the server's, from ``api_v1.py``. The tight
ones are the navigation labels: a section label IS a navigation entry, clipped
to 10 characters in Chinese and 24 in English, and the action button is
tighter still (7 / 18). Copy written past those limits is not rejected — it is
silently truncated with an ellipsis, on the busiest line of the page.
"""

from __future__ import annotations

from decimal import Decimal

SLUG = "lets-paint-showcase"
NAME = "Let's Paint Studio"

# ── the tenant row ─────────────────────────────────────────────────────────
#
# `studio`, not `growth`: the showcase demonstrates the plan a studio this size
# would actually buy, and a 60-work ceiling with 12 works in it is a ceiling
# you can talk about. A 150 ceiling with 12 works in it says nothing.
PLAN_CODE = "studio"

IDENTITY = {
    "address": "Caulfield North, Melbourne VIC",
    "contact_phone": "0400 000 000",
    "contact_email": "hello@pwe-studio.invalid",
    "timezone": "Australia/Melbourne",
    # Kept from the existing record. They identify the studio in the platform
    # console; the portal's palette is solved from the style preset, never
    # from these. See the v8.5.4 note in `_default_visual_theme`.
    "primary_color": "#955037",
    "secondary_color": "#3f6b61",
    "category": "art",
    "website": "https://showcase.pwe-studio.invalid",
    "billing_email": "accounts@pwe-studio.invalid",
}

# `atelier-clay light` is the art preset's own recommendation and it is what
# the tenant already runs. Stated explicitly so a reset cannot silently
# repaint the studio the day the preset default moves.
VISUAL_THEME = {"style_id": "atelier-clay", "color_scheme": "light"}

# ── what the studio says about itself ──────────────────────────────────────

SLOGAN = {
    "zh": "颜色会把人放慢下来。",
    "en": "Colour is a slower way to spend an afternoon.",
}

# hero_title IS the slogan — derived, never a second literal. A studio that can
# edit its slogan and still see the old one on its own front page has two
# sources for one sentence, which is how the industry presets went wrong once
# already.
LOCALIZED_COPY = {
    "slogan": SLOGAN,
    "hero_title": SLOGAN,
    "hero_subtitle": {  # ≤240
        "zh": "墨尔本 Caulfield North 的一间小画室。成人小班，一次不超过八个人，从握笔开始也来得及。",
        "en": "A small studio in Caulfield North, Melbourne. Adult classes of eight or fewer — starting from scratch is still starting.",
    },
    "welcome_message": {  # ≤240
        "zh": "我们不赶进度。你可以每周来两小时，也可以只来一次看看合不合适。",
        "en": "There is no schedule to keep up with. Come two hours a week, or come once to see whether it suits you.",
    },
    "primary_cta": {"zh": "预约体验", "en": "Book a trial"},        # 中文 ≤7
    "secondary_cta": {"zh": "看看作品", "en": "See the work"},      # 中文 ≤7

    # Section labels double as navigation entries: 中文 ≤10 / 英文 ≤24.
    "courses_label": {"zh": "课程与班次", "en": "Courses & Classes"},
    "gallery_label": {"zh": "学员作品", "en": "Student Work"},
    "faq_label": {"zh": "常见问题", "en": "Questions"},
    "contact_label": {"zh": "联系我们", "en": "Contact"},

    "courses_title": {  # ≤120
        "zh": "先挑一个能坚持的时间",
        "en": "Start with an hour you can actually keep",
    },
    "courses_lead": {  # ≤240
        "zh": "四门课，每周固定时间。买课包，按实际上课扣课时，余额随时能查。",
        "en": "Four classes, same time every week. Buy a pack, spend it as you attend, and check the balance whenever you like.",
    },

    # The student gallery answers a different question from Janet's own work,
    # and the lead says so out loud — the consent model is the strongest thing
    # this product does and it belongs on the public page, not only in the
    # console.
    "gallery_title": {"zh": "在这里学，能学成什么样", "en": "What people make here"},
    "gallery_lead": {
        "zh": "学员的画，每一张都经本人同意才放上来。",
        "en": "Student work, published one piece at a time and only with the artist's consent.",
    },

    "faq_title": {"zh": "来之前会想问的", "en": "Things people ask first"},

    "registration_title": {"zh": "说说你想画什么", "en": "Tell us what you'd like to paint"},
    "registration_intro": {  # ≤300
        "zh": "填完之后 Janet 会亲自回你，通常在一两天内。没有基础不用写「零基础」——大部分人都是。",
        "en": "Janet answers these herself, usually within a day or two. You don't need to explain that you're a beginner — most people are.",
    },

    "principal_title": {"zh": "创办人 · 主理人", "en": "Founder & Principal"},
    "principal_bio": {  # ≤800
        "zh": (
            "Janet 在北京学的画，来墨尔本之后做了八年广告。"
            "2019 年她租下 Caulfield North 一间旧车间，刷成白色，摆了八张画架——"
            "最初只是想有个地方自己画画，后来有人问能不能一起。\n\n"
            "她的课没有进度表。第一节课通常在调色盘上度过：先弄清楚你眼睛里的灰到底是什么颜色，"
            "剩下的都好说。"
        ),
        "en": (
            "Janet studied painting in Beijing and spent eight years in advertising after "
            "moving to Melbourne. In 2019 she took over an old workshop in Caulfield North, "
            "painted it white and put in eight easels — at first only so she would have "
            "somewhere to paint, then because people asked to join her.\n\n"
            "Her classes have no syllabus. The first one usually happens on the palette: "
            "work out what colour the grey in front of you actually is, and the rest follows."
        ),
    },
    "principal_quote": {  # ≤180
        "zh": "你眼睛里的灰，永远不是灰色。",
        "en": "The grey you're looking at is never grey.",
    },
}

PRINCIPAL = {
    "show": True,
    "name": "Janet M",
    # principal_profile is single-language; the bilingual pair above wins on
    # the portal. These are the fallback for anything that reads the flat
    # record, so they carry the English.
    "title": "Founder & Principal",
    "bio": LOCALIZED_COPY["principal_bio"]["en"],
    "quote": LOCALIZED_COPY["principal_quote"]["en"],
}

# ── the room ───────────────────────────────────────────────────────────────
#
# South-facing, and that is not a detail to get wrong: this is Melbourne. In
# the southern hemisphere the steady, colour-neutral light a painter wants
# comes from the south. A studio boasting about its north window is a studio
# written by somebody who has never stood at an easel.
ABOUT = {
    "eyebrow": {"zh": "空间", "en": "The room"},
    "title": {"zh": "一间朝南开窗的旧车间", "en": "An old workshop with a south window"},
    "body": {  # ≤600
        "zh": (
            "车间是 1960 年代的，天花板五米高，南墙一整排窗。"
            "我们没装射灯——南边的光一整天都不变色，这是画画的人唯一挑不出毛病的光。\n\n"
            "颜料、画布、画架、围裙都在。你带一件不怕脏的衣服就行。"
        ),
        "en": (
            "The building is 1960s: five metres to the ceiling and a full wall of "
            "south-facing windows. We didn't put in spotlights — south light doesn't "
            "change colour all day, which is the only light a painter never argues with.\n\n"
            "Paint, canvas, easels and aprons are here. Bring a shirt you don't mind ruining."
        ),
    },
    "items": [  # title ≤80, body ≤300
        {
            "title": {"zh": "一次最多八个人", "en": "Eight easels, no more"},
            "body": {
                "zh": "八张画架是硬上限。老师能在两小时里走到每个人身后三次——小班唯一的意义就在这里。",
                "en": "Eight is a hard limit. It is what lets the teacher stand behind each person three times in two hours, which is the only thing a small class is actually for.",
            },
        },
        {
            "title": {"zh": "材料都在这里", "en": "Materials are included"},
            "body": {
                "zh": "油画颜料、亚麻布、松节油、围裙都由画室提供。第一次来什么都不用买。",
                "en": "Oils, linen, solvent and aprons belong to the studio. You don't need to buy anything to come once.",
            },
        },
        {
            "title": {"zh": "画完了可以放着", "en": "Leave the wet ones here"},
            "body": {
                "zh": "油画干得慢。没画完的可以留在画室，架子上有你的位置，下周接着画。",
                "en": "Oil takes its time. Unfinished work stays on your shelf between classes.",
            },
        },
    ],
}

# ── the studio's own work ──────────────────────────────────────────────────

SHOWCASE_SECTION = {
    "label": {"zh": "主理人作品", "en": "Work by Janet"},        # nav: 5 / 13
    "title": {"zh": "教画的人，自己也在画", "en": "The person teaching also paints"},
    "lead": {  # ≤300
        "zh": "下面这些是 Janet 自己的画。看老师的画，比看老师的简历更能判断要不要来上课。",
        "en": "These are Janet's own paintings. Looking at a teacher's work tells you more than reading their CV.",
    },
}

TIMETABLE_SECTION = {
    "label": {"zh": "课程安排", "en": "Timetable"},
    "lead": {
        "zh": "未来两周的公开课。位置按已批准的约课实时计算，不是写死的数字。",
        "en": "Public classes for the next fortnight. Seats left are counted from approved bookings, not typed in.",
    },
}

# ── questions ──────────────────────────────────────────────────────────────
#
# Eight is the server's ceiling and these are the eight an adult beginner
# actually asks. The last one is deliberate: it puts the consent model in
# front of the visitor before they ever fill in a form.
FAQ = [  # question ≤140, answer ≤500
    {
        "question": {"zh": "完全没画过，可以来吗？", "en": "I've never painted. Can I come?"},
        "answer": {
            "zh": "可以，而且大部分人都是这样开始的。基础班默认从没画过教起：怎么握笔、怎么调一个准确的颜色、怎么把看到的东西放到画布上。不需要提前买书或练素描。",
            "en": "Yes, and most people start exactly there. The foundation class assumes no experience: how to hold a brush, how to mix a colour that is actually right, how to get what you see onto canvas. There is nothing to read or practise beforehand.",
        },
    },
    {
        "question": {"zh": "要自己买材料吗？", "en": "Do I need to buy materials?"},
        "answer": {
            "zh": "不用。颜料、画布、画笔、松节油、围裙都是画室的。上过几次以后如果你想要自己顺手的笔，我们会告诉你买什么，但那不是开始的条件。",
            "en": "No. Paint, canvas, brushes, solvent and aprons are the studio's. After a few classes you may want brushes of your own, and we'll tell you which — but that is never a condition of starting.",
        },
    },
    {
        "question": {"zh": "一节课多久？", "en": "How long is a class?"},
        "answer": {
            "zh": "油画基础两小时，水彩与速写一个半小时，人像专题两个半小时。周六儿童班一个半小时。时间都写在课程安排里。",
            "en": "Two hours for foundation oil, ninety minutes for watercolour and sketching, two and a half hours for the portrait intensive, ninety minutes for the Saturday children's class. Every time is on the timetable.",
        },
    },
    {
        "question": {"zh": "请假了怎么办？", "en": "What happens if I miss a class?"},
        "answer": {
            "zh": "课时按实际上课扣，请假不扣。提前告诉我们就行，同一周内可以补到另一个班，位置够的话当场安排。",
            "en": "Credits are spent when you attend, so a missed class costs nothing. Tell us in advance and you can make it up in another class the same week, subject to a free easel.",
        },
    },
    {
        "question": {"zh": "小孩可以来吗？", "en": "Do you teach children?"},
        "answer": {
            "zh": "周六上午有一节 6 到 11 岁的儿童创作课。平日晚上的班是成人班，不收小孩——不是不欢迎，是两种课的节奏完全不一样。",
            "en": "There is a Saturday morning class for ages 6 to 11. The weekday evening classes are for adults only — not for want of welcome, but because the two run at completely different speeds.",
        },
    },
    {
        "question": {"zh": "可以只上一次吗？", "en": "Can I just come once?"},
        "answer": {
            "zh": "可以。有单次体验，价格按一节课算，不需要先买课包。来过之后觉得合适再说。",
            "en": "Yes. A single trial session is priced as one class and does not require a pack. Decide afterwards.",
        },
    },
    {
        "question": {"zh": "画完的画归谁？", "en": "Who keeps the paintings?"},
        "answer": {
            "zh": "归你。画室不留学员的画，也不拿去卖。干透了随时带走，太大的我们帮你叫车。",
            "en": "You do. The studio does not keep or sell student work. Take it when it's dry; if it's too big for a car we'll help you arrange one.",
        },
    },
    {
        "question": {"zh": "会把我的画发到网上吗？", "en": "Will my work be posted online?"},
        "answer": {
            "zh": "只有你同意的那一张会。同意是一张一张给的，不是入学时签一次就永久有效；你随时可以撤回，撤回之后网站上立刻就没有了。",
            "en": "Only the piece you agree to. Consent is given one work at a time — not signed once when you enrol — and you can withdraw it at any point, after which it comes off the site immediately.",
        },
    },
]

# ── registration form ──────────────────────────────────────────────────────
#
# The industry default asks a parent about a child. This studio's visitor is a
# 34-year-old who has not drawn since school, so it asks them instead.
REGISTRATION_PROFILE = {
    "title": "Tell us what you'd like to paint",
    "fields": [
        {
            "key": "experience",
            "label": "Where you're at",
            "label_zh": "现在画到哪一步",
            "placeholder": "Never painted, painted years ago, or painting already",
            "placeholder_zh": "没画过 / 以前学过 / 一直在画",
            "type": "text",
        },
        {
            "key": "goals",
            "label": "What you're hoping for",
            "label_zh": "想解决什么",
            "placeholder": "Somewhere to switch off, colour, drawing, portraits",
            "placeholder_zh": "想找个地方放空、想学配色、想学素描、想画人",
            "type": "text",
        },
        {
            "key": "availability",
            "label": "When you're free",
            "label_zh": "什么时段方便",
            "placeholder": "Weeknights, Saturday afternoon, Sunday morning",
            "placeholder_zh": "工作日晚上 / 周六下午 / 周日上午",
            "type": "text",
        },
    ],
}

COPY_PACK = {
    "portal_label": "Student & Family Studio",
    "register_intro": LOCALIZED_COPY["registration_intro"]["en"],
}

# ── people ─────────────────────────────────────────────────────────────────
#
# (role, email, full name, presenter label, public display name, on timetable)
#
# The emails are unchanged from the existing showcase: they are printed in the
# presenter credential file and in Demo_Runbook.md, and renaming a login to
# improve a demo is how a demo stops working.
#
# Two of four consent to appear on the public timetable. That ratio is the
# point — a seed where everybody is public demonstrates nothing about a switch
# that defaults to off.
ROLE_ACCOUNTS = (
    ("owner", "owner.showcase@pwe-studio.invalid", "Janet M", "Owner", "Janet", True),
    ("manager", "manager.showcase@pwe-studio.invalid", "Wen Zhao", "Studio Manager", "", False),
    ("teacher", "teacher.showcase@pwe-studio.invalid", "Marika Lund", "Lead Teacher", "Marika", True),
    ("front_desk", "frontdesk.showcase@pwe-studio.invalid", "Sam Rios", "Front Desk", "", False),
)

# (first, last, parent_name, mobile, email, balance)
#
# Adults have no parent_name — the field is for the two children in the
# Saturday class. A roster where every adult has a "parent" is a roster
# copied from a children's studio, which is what this one was.
STUDENTS = (
    ("Priya", "Raman", "", "0400000101", "priya@example.com", Decimal("8")),
    ("Tom", "Whelan", "", "0400000102", "tom@example.com", Decimal("3")),
    ("Ana", "Bianchi", "", "0400000103", "ana@example.com", Decimal("12")),
    ("Xi", "Chen", "", "0400000104", "xi@example.com", Decimal("1")),
    ("Marcus", "Ely", "", "0400000105", "marcus@example.com", Decimal("6")),
    ("Hana", "Sato", "", "0400000106", "hana@example.com", Decimal("10")),
    ("Lucy", "Ferreira", "", "0400000107", "lucy@example.com", Decimal("4")),
    ("Dave", "Okonkwo", "", "0400000108", "dave@example.com", Decimal("2")),
    ("Xiaoman", "Lin", "", "0400000109", "xiaoman@example.com", Decimal("9")),
    ("Rosie", "Hartnett", "", "0400000110", "rosie@example.com", Decimal("5")),
    # The Saturday children's class. Eli is Tom's — a detail that costs nothing
    # and makes a roster read like a roster.
    ("Eli", "Whelan", "Tom Whelan", "0400000102", "tom@example.com", Decimal("7")),
    ("Xiaoyu", "Zhou", "Mei Zhou", "0400000112", "mei.zhou@example.com", Decimal("11")),
)
ADULT_COUNT = 10

# ── the catalogue ──────────────────────────────────────────────────────────
#
# `courses.name`, `.description` and `.category` are single-language columns
# and the portal renders them verbatim in both language modes. Rather than
# pick a language and leave half the visitors reading the wrong one, the names
# carry both — which is also how a bilingual Melbourne studio writes its own
# signage. The product gap is recorded in Showcase_Tenant_Build.md §7.
#
# (name, description, category, age_range, minutes, price_aud_cents)
COURSES = (
    (
        "油画基础 Foundation Oil",
        "从调色开始，两小时画一张。没画过也从这里开始。 / Start at the palette and paint for two hours. This is where beginners begin.",
        "油画 Oil",
        "18+",
        120,
        6500,
    ),
    (
        "水彩与速写 Watercolour & Sketching",
        "轻装上阵：一支笔、一盒颜料、一个半小时。 / Light equipment: one brush, one box, ninety minutes.",
        "水彩 Watercolour",
        "18+",
        90,
        5500,
    ),
    (
        "人像专题 Portrait Intensive",
        "画人。需要一点基础，一次两个半小时，只收六个人。 / Painting people. Some experience needed; six places, two and a half hours.",
        "人像 Portrait",
        "有基础 Experienced",
        150,
        8500,
    ),
    (
        "周六儿童创作 Saturday Kids",
        "6 到 11 岁，材料随便用，画什么都行。 / Ages 6 to 11. Any material, any subject.",
        "儿童 Children",
        "6–11",
        90,
        4500,
    ),
)

# (course index, name, credits, price_aud_cents, expires_after_days)
PACKAGES = (
    (0, "单次体验 Single trial", Decimal("1"), 6500, 60),
    (0, "十次课包 Ten-class pack", Decimal("10"), 58500, 180),
    (1, "水彩十次包 Watercolour ten-pack", Decimal("10"), 49500, 180),
    (2, "人像六次包 Portrait six-pack", Decimal("6"), 45900, 120),
    (3, "儿童一学期 Kids term", Decimal("10"), 40500, 180),
)

# ── the week ───────────────────────────────────────────────────────────────
#
# weekday follows JS getDay(): 0=Sunday .. 6=Saturday.
#
# All seven are public. `is_public` defaults to FALSE for a good reason (a
# schedule is not an advertisement), but a demonstration tenant whose
# timetable page is empty demonstrates the wrong half of that decision.
#
# (course index, label, weekday, start, minutes, capacity, room, teacher role, roster slice)
SCHEDULES = (
    (0, "油画基础 · 周二晚 Foundation Oil · Tue", 2, "18:30", 120, 8, "主画室 Main room", "owner", (0, 6)),
    (1, "水彩与速写 · 周三上午 Watercolour · Wed", 3, "10:00", 90, 8, "主画室 Main room", "teacher", (2, 8)),
    (0, "油画基础 · 周三晚 Foundation Oil · Wed", 3, "18:30", 120, 8, "主画室 Main room", "owner", (4, 10)),
    (2, "人像专题 · 周四晚 Portrait · Thu", 4, "18:30", 150, 6, "小画室 Back room", "owner", (0, 4)),
    (3, "周六儿童创作 Saturday Kids", 6, "10:00", 90, 10, "小画室 Back room", "teacher", (10, 12)),
    (0, "油画基础 · 周六下午 Foundation Oil · Sat", 6, "13:30", 120, 8, "主画室 Main room", "owner", (2, 10)),
    (1, "水彩与速写 · 周日上午 Watercolour · Sun", 0, "10:30", 90, 8, "主画室 Main room", "teacher", (5, 10)),
)

# Two cancellations, because a timetable that has never been corrected does
# not demonstrate that it CAN be. (schedule index, days from today, note)
# Both dates have to land INSIDE the two-week window the page projects, or the
# seed silently demonstrates nothing: `_next_occurrence` walks forward to the
# class's own weekday, so a naive "12 days out" can end up on day 15.
SCHEDULE_EXCEPTIONS = (
    (4, 9, "停课 · 公众假期 Closed · public holiday"),
    (3, 5, "停课 · 老师外出 Closed · teacher away"),
)

# Three pending requests against the next occurrence of a class.
# (schedule index, days ahead, name, phone, message)
BOOKINGS = (
    (0, 4, "Ivy Nguyen", "0400000301", "想先来一次看看，从来没画过油画。 / Would like to try one class first — never painted in oil."),
    (5, 6, "Ben Carter", "0400000302", "周六下午方便，两个人可以一起吗？ / Saturday afternoon suits us. Could two of us come?"),
    (1, 8, "周敏 Min Zhou", "0400000303", "水彩班还有位置吗？ / Is there a place in the watercolour class?"),
)

# The enquiry pipeline, one row per state the CMS can show.
# (status, first, last, parent, mobile, email, message, follow_up_days)
REGISTRATIONS = (
    ("pending", "Isla", "Moore", "", "0400000201", "isla@example.com",
     "看到你们的作品页找过来的，想问周三晚上。 / Found you through the work page — asking about Wednesday evenings.", None),
    ("contacted", "Finn", "Davis", "", "0400000202", "finn@example.com",
     "高中之后没画过，想重新开始。 / Haven't drawn since school and would like to start again.", 3),
    ("trial_booked", "Lily", "Thomas", "", "0400000203", "lily@example.com",
     "已约周六下午的体验课。 / Trial booked for Saturday afternoon.", 5),
    ("waiting", "Max", "Walker", "", "0400000204", "max@example.com",
     "想上人像专题，等下一期有位置。 / Waiting for a place in the portrait intensive.", 8),
    ("converted", "Evie", "Hall", "", "0400000205", "evie@example.com",
     "已购十次课包，周二晚。 / Bought the ten-class pack, Tuesday evenings.", None),
)

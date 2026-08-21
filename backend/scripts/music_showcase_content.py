"""Everything the music showcase tenant says, in one place, in both languages.

The sibling of ``showcase_content.py``, and deliberately the same shape: same
exported names, same tuple arities, same conventions. A second demonstration
tenant is only worth having if it can be read side by side with the first —
one file to diff, one set of names for a seeder to import.

Every visitor-facing string is a ``{"zh": ..., "en": ...}`` pair. The portal
switches language client-side and the server strips the other half out of the
static pages, so a string that exists in only one language is a page that is
half-empty in the other.

── On the identity ────────────────────────────────────────────────────────

知音音乐 / Zhiyin Music is fictional. It borrows its SHAPE from the bilingual
music schools of Melbourne's eastern suburbs — Chinese and Western instruments
under one roof, AMEB and VCE as the exam spine, an ensemble on Saturday — and
invents every particular. No real school, teacher, student, venue, competition
or examiner is named. AMEB, VCAA and the Central Conservatory's overseas
grading appear because they are the pathways a real family asks about; nothing
here claims a result from any of them.

The principal is ``Vivian H``: a deliberately partial name that points at
nobody, the same discipline as the art pack's ``Janet M``.

知音 is a real phrase, not an invented one — the listener who hears what you
meant, from the Boya / Zhong Ziqi story. It is the reason the studio has this
name, and the principal's own bio says so.

── On the character limits ────────────────────────────────────────────────

The numbers in the comments are the server's, from ``api_v1/_shared.py``. The
tight ones are the navigation labels: a section label IS a navigation entry,
clipped to 10 characters in Chinese and 24 in English, and the action button is
tighter still (7 / 18). Copy written past those limits is not rejected — it is
silently truncated with an ellipsis, on the busiest line of the page.

── What this file does NOT own ────────────────────────────────────────────

The pictures and what is said about each of them live in
``seed-assets/music-showcase/manifest.json``, exactly as the art pack splits
them.

The money layer is half here and half in the seeder, which is where the art
pack drew the line: the payers, the invoice plan and the progress reports are
data at the bottom of this file, while the supplier identity, the teacher pay
rates and the pay period are still literals inside
``_seed_money_layer``. Everything priced here is priced so the two halves
agree — see the note on ``COURSES``.
"""

from __future__ import annotations

from decimal import Decimal

SLUG = "music-studio-showcase"
NAME = "Zhiyin Music"

# ── the tenant row ─────────────────────────────────────────────────────────
#
# `growth`, not `studio`, and this is the one line in the file that is a
# product decision rather than a copy decision. Management reports are a
# growth-plan feature (migration 0039), so on `studio` the CMS finance →
# reports tab answers 403 feature_not_available — and revenue by source,
# receivables ageing and teacher cost are the half of the money story a school
# with nineteen teachers is actually being pitched.
#
# The cost is real and worth saying out loud: the art showcase runs `studio`
# precisely because a 60-work ceiling with 12 works in it is a ceiling you can
# talk about, and growth's 150/500/20 ceilings against this tenant's 12 pieces,
# 12 students and 4 accounts are ceilings nobody can see. If the walkthrough
# never opens the reports tab, move this back to "studio" and nothing else in
# the file changes.
PLAN_CODE = "growth"

IDENTITY = {
    "address": "Glen Waverley, Melbourne VIC",
    # A landline, because a school with a front room answers one. 5550 is the
    # block Australian film and television use for numbers that must never
    # reach a real subscriber — the same intent as the art pack's
    # 0400 000 000, in the shape a school would actually print.
    "contact_phone": "03 5550 0180",
    # `.example` and `.invalid` are both reserved and unroutable. The split is
    # deliberate: the studio's own public addresses read like a studio's
    # (zhiyinmusic.example), and only the STAFF LOGINS sit on
    # pwe-studio.invalid — see the comment on ROLE_ACCOUNTS for why those
    # cannot be shared with the art pack.
    "contact_email": "hello@zhiyinmusic.example",
    "timezone": "Australia/Melbourne",
    # The recital-plum light accent and its analogous violet. They identify the
    # studio in the platform console; the portal's palette is solved from the
    # style preset, never from these two columns.
    "primary_color": "#89469D",
    "secondary_color": "#5656B7",
    "category": "music",
    "website": "https://zhiyinmusic.example",
    "billing_email": "accounts@zhiyinmusic.example",
}

# `recital-plum light` is the music preset's own recommendation
# (presets.py: STYLE_FOR_CATEGORY). Stated explicitly so a reset cannot
# silently repaint the studio the day the preset default moves.
VISUAL_THEME = {"style_id": "recital-plum", "color_scheme": "light"}

# ── what the studio says about itself ──────────────────────────────────────
#
# The slogan is the music preset's own line, kept rather than replaced. It is
# the one preset string that is already right for this school — and it rhymes
# with the principal's quote further down, which is the sentence the studio
# actually teaches by. Restated here so a reset cannot drift if the preset
# default moves.
SLOGAN = {
    "zh": "找到自己的节奏，让每次练习都算数。",
    "en": "Find your rhythm. Make every practice count.",
}

# hero_title IS the slogan — derived, never a second literal. A studio that can
# edit its slogan and still see the old one on its own front page has two
# sources for one sentence, which is how the industry presets went wrong once
# already.
LOCALIZED_COPY = {
    "slogan": SLOGAN,
    "hero_title": SLOGAN,
    "hero_subtitle": {  # ≤240
        "zh": "墨尔本 Glen Waverley 的一间音乐教室。钢琴、小提琴、声乐，古筝、二胡、琵琶——一对一，四到六人的小组，周六下午还有一个合奏小组。",
        "en": "A teaching studio in Glen Waverley, Melbourne. Piano, violin and voice; guzheng, erhu and pipa. One-on-one lessons, groups of four to six, and an ensemble that rehearses on Saturday afternoons.",
    },
    "welcome_message": {  # ≤240
        "zh": "第一节课先坐下来弹一点、听一点，我们和你一起看看合不合适。不合适就说，不必先报一整个学期。",
        "en": "The first lesson is mostly playing and listening, so everyone can see whether this fits. If it doesn't, say so — nobody has to commit to a term first.",
    },
    "primary_cta": {"zh": "预约试课", "en": "Book a trial"},        # 中文 ≤7 / 英文 ≤18
    "secondary_cta": {"zh": "听听看", "en": "Have a listen"},       # 中文 ≤7 / 英文 ≤18

    # Section labels double as navigation entries: 中文 ≤10 / 英文 ≤24.
    "courses_label": {"zh": "课程与班次", "en": "Lessons & Classes"},
    "gallery_label": {"zh": "学员演奏", "en": "Student Performances"},
    "faq_label": {"zh": "常见问题", "en": "Questions"},
    "contact_label": {"zh": "联系我们", "en": "Contact"},

    "courses_title": {  # ≤120
        "zh": "先挑乐器，再挑时间",
        "en": "Pick the instrument, then pick the hour",
    },
    "courses_lead": {  # ≤240
        "zh": "一对一按乐器分，小组课四到六人。学费按学期算，提前请假记一次补课，不白扣。",
        "en": "One-on-one by instrument, groups of four to six. Fees are billed by the term, and a lesson cancelled with notice becomes a make-up rather than a loss.",
    },

    # The student gallery answers a different question from the studio's own
    # board, and the lead says so out loud — the consent model is the strongest
    # thing this product does and it belongs on the public page, not only in
    # the console. For a school full of children it is also the first thing a
    # parent wants answered.
    "gallery_title": {"zh": "在这里学，能弹成什么样", "en": "What people play after a while here"},
    "gallery_lead": {
        "zh": "学员的演奏，每一段都经本人或家长同意才放上来。",
        "en": "Student performances, published one at a time and only with the family's consent.",
    },

    "faq_title": {"zh": "坐上琴凳之前", "en": "Before the first lesson"},

    "registration_title": {"zh": "先说说想学什么乐器", "en": "Tell us what they'd like to play"},
    "registration_intro": {  # ≤300
        "zh": "告诉我们学员现在弹到哪一步、想学什么乐器，我们通常一两天内回，先约一节 30 分钟的试课。还没想好学什么也没关系——试课那天可以坐下来试试钢琴和古筝，之后再定。",
        "en": "Tell us what they play now and what they would like to learn. We answer within a day or two and start with a thirty-minute trial lesson. Not knowing which instrument yet is a fine answer — sit down at the piano and the guzheng on the day, and decide afterwards.",
    },

    "principal_title": {"zh": "创办人 · 主理老师", "en": "Founder & Principal Teacher"},
    "principal_bio": {  # ≤800
        "zh": (
            "Vivian 六岁在上海学古筝，十四岁跟家里来墨尔本，在这边接着学钢琴，"
            "考完八级就停了。大学念的会计，在事务所做了六年，周末一直带两三个学生——"
            "那几年她自己也讲不清楚哪一头才是正职。\n\n"
            "2020 年她在 Glen Waverley 租下这栋房子，把前面的几间房隔成四间琴房。"
            "「知音」这两个字来自伯牙和钟子期：一个人弹，另一个人听得出他心里是高山还是流水。"
            "她说教琴大半时间做的就是这件事——先听清楚学生弹的是什么，再说下一步。"
        ),
        "en": (
            "Vivian started guzheng in Shanghai at six, came to Melbourne with her family "
            "at fourteen and carried on here on piano, stopping after Grade 8. She studied "
            "accounting, spent six years at a firm, and taught two or three students every "
            "weekend throughout — for a while she could not have told you which was the job.\n\n"
            "In 2020 she took the lease on the Glen Waverley house and divided the front "
            "rooms into four studios. The name comes from zhiyin, the listener who hears "
            "what you meant: in the old story Boya plays and Zhong Ziqi hears the mountain "
            "and the river in it. Most of teaching, she says, is that — work out what the "
            "student is actually playing, then say what comes next."
        ),
    },
    "principal_quote": {  # ≤180
        "zh": "把一小段练到自己想再弹一遍，这一天的练习就成了。",
        "en": "Practise one phrase until you want to play it again — that is the day done.",
    },
}

PRINCIPAL = {
    "show": True,
    "name": "Vivian H",
    # principal_profile is single-language; the bilingual pair above wins on
    # the portal. These are the fallback for anything that reads the flat
    # record, so they carry the English.
    "title": "Founder & Principal Teacher",
    "bio": LOCALIZED_COPY["principal_bio"]["en"],
    "quote": LOCALIZED_COPY["principal_quote"]["en"],
}

# ── the rooms ──────────────────────────────────────────────────────────────
#
# The art pack's equivalent gets one physical fact exactly right for its craft:
# south light, because this is the southern hemisphere. The music equivalent is
# the wall between two rooms. Whether an erhu lesson and a piano lesson can run
# at the same time is not a decorating question — it decides whether the
# timetable further down this file is physically possible at all, and a music
# school that has not spent money on it teaches one student at a time.
#
# Four teaching rooms, six photographs: two small studios with uprights, the
# guzheng room, the big room with the grand, and the front room where parents
# wait. The counts here, in `SCHEDULES` and in the manifest's room captions all
# have to agree — five guzheng, one grand in the big room, an upright in Studio
# 1 and a digital piano in Studio 2. Two acoustic pianos, which is what the
# "tuned twice a year" item counts; a digital one is not tuned and not counted.
ABOUT = {
    "eyebrow": {"zh": "琴房", "en": "The rooms"},
    "title": {"zh": "四间琴房，一间留给整个乐团", "en": "Four rooms, and one that fits the whole ensemble"},
    "body": {  # ≤600
        "zh": (
            "教室在 Glen Waverley 一条横街上，1970 年代的砖房，走到火车站六分钟，"
            "门口有两小时免费停车。前面隔出四间琴房，墙里塞了岩棉，门缝压了条——"
            "隔壁在拉二胡的时候，这边的钢琴课听不见。"
            "最大的一间放得下十几个人和一台三角钢琴，周六下午归乐团。\n\n"
            "前厅有两张沙发，家长可以坐着等；每节课最后十分钟想进来听，随时都可以。"
        ),
        "en": (
            "The studio is a 1970s brick house on a side street in Glen Waverley — six "
            "minutes from the station, two hours' free parking at the door. The front of "
            "the house is divided into four teaching rooms with rockwool in the walls and "
            "seals on the doors, so an erhu next door does not turn up in a piano lesson. "
            "The largest room holds a dozen people and the grand piano, and belongs to the "
            "ensemble on Saturday afternoons.\n\n"
            "There are two sofas in the front room for waiting parents, and you are welcome "
            "in for the last ten minutes of any lesson."
        ),
    },
    "items": [  # title ≤80, body ≤300 — six is the server's ceiling
        {
            "title": {"zh": "隔音做在墙里", "en": "The soundproofing is in the walls"},
            "body": {
                "zh": "四间琴房是重做的隔墙，里面填岩棉，门缝压了条。二胡课和钢琴课可以同时上，谁也不吵谁——这不是装修上的讲究，是排得出课表的前提。",
                "en": "The four teaching rooms were rebuilt with insulated stud walls and sealed doors. An erhu lesson and a piano lesson can run at the same time without either being in the other's way — less a renovation detail than the reason a timetable is possible at all.",
            },
        },
        {
            "title": {"zh": "两台钢琴，一年调两次", "en": "Two pianos, tuned twice a year"},
            "body": {
                # The June concert, not December: the FAQ and the item below
                # both say December is in a hired community hall, and the first
                # draft of this line put it in the big room as well.
                "zh": "琴房一一台立式，大琴房一台三角——要调的是这两台，考级前走台和六月的音乐会都在大琴房。琴房二放的是电钢琴，启蒙小组用。古筝房里五台古筝，弦一学期换一轮；二胡和琵琶各备了一把练习琴。",
                "en": "An upright in Studio 1 and a grand in the big room — the two that get tuned — where exam run-throughs and the June concert happen. Studio 2 has a digital piano for the early-years group. Five guzheng in the guzheng room, restrung once a term, plus a practice erhu and a practice pipa.",
            },
        },
        {
            "title": {"zh": "家长可以坐着等", "en": "Somewhere for parents to wait"},
            "body": {
                "zh": "前厅两张沙发，有无线网络，走十分钟有咖啡。每节课最后十分钟，老师会当着家长把这周要练的地方再说一遍——不是汇报，是让回家陪练的人也听见。",
                "en": "Two sofas, wifi, and coffee ten minutes' walk away. In the last ten minutes of each lesson the teacher goes through the week's practice points with the parent in the room — not a report, just so whoever supervises practice has heard it too.",
            },
        },
        {
            "title": {"zh": "中文英文都能上课", "en": "Lessons in English or Mandarin"},
            "body": {
                "zh": "老师大多两种语言都教得了，报名时说一句就行。课堂记录和学期末的学习报告中英文都写，给学校看、给家里长辈看，都够用。",
                "en": "Most teachers work in either language; say which you would prefer when you enrol. Lesson notes and the end-of-term report are written in both, which covers the school and the grandparents at once.",
            },
        },
        {
            "title": {"zh": "周六下午是乐团", "en": "Saturday afternoons are the ensemble"},
            "body": {
                "zh": "八到十二个人，民乐和西乐排在一起。学满一年就可以进，不考级也可以。一年两次上台：六月在教室，十二月在社区中心。",
                "en": "Eight to twelve players, Chinese and Western instruments in the same room. A year of lessons is the only way in — no grade required. They play twice a year: June in the studio, December in a community hall.",
            },
        },
        {
            "title": {"zh": "考试的日子贴在墙上", "en": "The exam dates are on the wall"},
            "body": {
                "zh": "AMEB 每年的考期和报名截止贴在前厅，走台时间由教室统一约。VCE 的学生每学期在大琴房完整走一遍曲目——不打分，只是把上台这件事先做过一次。",
                "en": "AMEB session dates and entry deadlines go up in the front room, and we book the run-through slots as a studio. VCE students play their whole program in the big room once a term — not marked, just so the standing-up part has already happened once.",
            },
        },
    ],
}

# ── what gets played here ──────────────────────────────────────────────────
#
# The art pack's showcase board is the principal's own paintings, because a
# painting teacher's work answers "should I learn from this person". A music
# school's board cannot be that: what a prospective family wants to hear is
# students, and students are children. So the lead carries the consent rule
# onto the board itself — the same promise the last FAQ makes, said where the
# recordings actually are.
SHOWCASE_SECTION = {
    "label": {"zh": "曲目与演出", "en": "Repertoire & Concerts"},   # nav: 5 / 21
    "title": {"zh": "这里的人，都在弹什么", "en": "What gets played here"},
    "lead": {  # ≤300
        "zh": "学期音乐会、考级曲目，还有乐团在排的东西。有录像就放录像，没有就只放一张照片——没经过同意的录音，我们不放。",
        "en": "Term concerts, exam programs, and whatever the ensemble is working on. Where there is a recording we publish it; where there is not, a photograph. We never publish a recording nobody agreed to.",
    },
}

TIMETABLE_SECTION = {
    "label": {"zh": "课程表", "en": "Timetable"},
    "lead": {
        # Product-accurate and worth saying: one-to-one teaching lives in
        # lesson_series, which never reaches the public timetable. A music
        # school's week is mostly one-to-one, so a visitor who is not told this
        # reads an eight-row page as a nearly empty school.
        "zh": "未来两周的小组课与乐团排练。一对一的时间不在这里——那是跟老师单独约的。",
        "en": "Group classes and ensemble rehearsals for the next fortnight. One-on-one lessons are not listed: those times are arranged with the teacher.",
    },
}

# ── questions ──────────────────────────────────────────────────────────────
#
# Eight is the server's ceiling and these are the eight a parent actually asks,
# in the order they ask them. Two are load-bearing beyond their content: the
# exam answer is where every music school gets AMEB wrong, and the last one
# puts the consent model in front of the visitor before they ever fill in a
# form.
#
# On the exam answer — AMEB pairs practical Grade 6 with a Grade 2 written
# subject, Grade 7 with Grade 3, Grade 8 with Grade 4, and it is a co-requisite
# that gates release of the CERTIFICATE, not a gate before the practical exam.
# "Grade 5 theory before Grade 6 practical" is the ABRSM rule and belongs to a
# different examiner. AMEB also has no guzheng, erhu or pipa syllabus at all,
# which is why the Chinese instruments are sent somewhere else in the same
# breath.
FAQ = [  # question ≤140, answer ≤500
    {
        "question": {"zh": "第一次来怎么开始？", "en": "How do we start?"},
        "answer": {
            "zh": "先来一节 30 分钟的试课，按单次算，不用先买课包。那天孩子坐下来弹一点、听一点，我们也看看和哪位老师合得来。还没想好学什么乐器完全可以——钢琴和古筝当场都能试。试完再决定要不要报这个学期。",
            "en": "Start with a thirty-minute trial lesson, priced as a single lesson with no pack to buy first. On the day they play a little, listen a little, and everyone finds out which teacher they get on with. Not having chosen an instrument is a perfectly good answer — the piano and the guzheng are both there to try. Decide about the term afterwards.",
        },
    },
    {
        "question": {"zh": "学费怎么算？", "en": "How are fees worked out?"},
        "answer": {
            "zh": "按学期收费，学期跟着维州公立学校的校历走，一学期十到十一周。一对一 30 分钟 $55、45 分钟 $77、60 分钟 $99；四到六人的小组课一小时每人 $44；乐团每学期 $198。学期第一周开账单，中途插班按剩下的节数算。发票上的单价是不含 GST 的数，加 10% 之后正好回到上面这些数字。考级报名费是 AMEB 收的，我们代交，收多少交多少。",
            "en": "We bill by the term and follow the Victorian school calendar — ten or eleven weeks. One-on-one is $55 for 30 minutes, $77 for 45 and $99 for the hour; a group of four to six is $44 each per hour, and the ensemble is $198 a term. The invoice goes out in week one, and a mid-term start is pro-rata on the lessons left. Unit prices on the invoice are shown before GST and come back to exactly those figures once the 10% is added. Exam entry fees are AMEB's and we pass them on at cost.",
        },
    },
    {
        "question": {"zh": "请假能补课吗？", "en": "Can we make up a missed lesson?"},
        "answer": {
            "zh": "提前 24 小时告诉我们，这节课记一次补课额度，学期内约回来，一学期最多两次。24 小时以内请假或者当天没来，课时照扣——那段时间老师已经留给你了。老师那边停的课不算在两次里，我们另外补，或者把课时退回去。",
            "en": "Tell us more than 24 hours ahead and the lesson becomes a make-up credit, to be used inside the same term, twice a term at most. Inside 24 hours, or a no-show, the lesson is charged — the teacher held the time. Lessons we cancel never count towards your two: we rebook them, or credit them back.",
        },
    },
    {
        "question": {"zh": "一定要考级吗？", "en": "Does my child have to sit exams?"},
        "answer": {
            "zh": "不一定，想考我们再准备。西洋乐器走 AMEB：墨尔本的实技考期集中在四月底到六月初、八月到十一月，报名一般提前两个月截止。六级以上的实技要配一门笔试（乐理、Musicianship 或 Music Craft）：六级配二级，七级配三级，八级配四级；笔试不必赶在实技之前，但证书要等笔试过了才发。古筝、二胡、琵琶不在 AMEB 的科目里，走中央音乐学院的海外考级，一到十级。",
            "en": "Only if you want to. Western instruments sit AMEB — Melbourne practical sessions run late April to early June and again August to November, entries closing about two months ahead. From Grade 6 each practical is paired with a written subject (Grade 2 for practical Grade 6, Grade 3 for 7, Grade 4 for 8); it need not be passed first, but the certificate waits for it. AMEB does not examine guzheng, erhu or pipa — those sit the Central Conservatory overseas grades, 1 to 10.",
        },
    },
    {
        "question": {"zh": "在家要练多久？", "en": "How much practice at home?"},
        "answer": {
            "zh": "刚开始的孩子，一周五天、每天十五分钟，比周日晚上补九十分钟管用得多。准备考级的一般三十到四十五分钟。老师每节课把这周要练的一两个地方写进课堂记录，家长在最后十分钟听得到；学期末这些记录会汇成一份学习报告。我们不看打卡表。",
            "en": "For a child starting out, fifteen minutes on five days beats ninety minutes on Sunday night. Students working towards a grade usually do thirty to forty-five. The teacher writes the week's one or two practice points into the lesson record, you hear them in the last ten minutes of the lesson, and at the end of term those records become a written progress report. Nobody is asked to fill in a practice chart.",
        },
    },
    {
        "question": {"zh": "琴要自己买吗？可以租吗？", "en": "Do we buy an instrument, or can we hire one?"},
        "answer": {
            "zh": "我们不卖琴也不租琴——这不是我们做的生意，推荐哪一家也不拿回扣。第一学期用家里的电钢琴，或者借一把来，都可以；学古筝的可以先用教室的琴练。真要买的时候跟老师说一声，他会告诉你看什么、大概什么价，需要的话也能陪你去挑。",
            "en": "We do not sell or hire instruments — it is not our business, and we take nothing from anyone we point you to. A digital piano, or a borrowed instrument, is fine for the first term, and guzheng students can practise on a studio instrument until they buy. When you are ready, ask your teacher: they will tell you what to look for and roughly what it costs, and will come along if that helps.",
        },
    },
    {
        "question": {"zh": "有演出吗？", "en": "Are there concerts?"},
        "answer": {
            "zh": "一年两次。六月一个周日下午在大琴房，一人一首，家里人来听，弹完吃点东西；十二月租社区中心的礼堂，正式一些，乐团也上。两场都不卖票，想带谁来都行。不想上台可以不上，只弹六月那场也很常见。",
            "en": "Twice a year. In June we use the big room on a Sunday afternoon — one piece each, family only, food afterwards. In December we hire a community hall and make it a proper concert, with the ensemble playing. Neither is ticketed; bring whoever you like. Nobody has to play, and playing only in June is a perfectly ordinary choice.",
        },
    },
    {
        "question": {"zh": "会把孩子的演奏放到网上吗？", "en": "Will my child's playing be posted online?"},
        "answer": {
            "zh": "只有你同意的那一段会。同意是一段一段给的，不是报名时签一次就永久有效；你随时可以撤回，撤回之后网站上立刻就没有了。有的家庭同意放照片、不同意放录音，那我们就只放照片——这样回答完全可以。",
            "en": "Only the piece you agree to. Consent is given one recording at a time — not signed once when you enrol — and you can withdraw it at any point, after which it comes off the site immediately. Some families say yes to a photograph and no to a recording; that is an ordinary answer and we simply stop there.",
        },
    },
]

# ── registration form ──────────────────────────────────────────────────────
#
# The music preset asks instrument / level / goals. The third one is replaced
# here, because "goals" is the question a family cannot answer before the first
# lesson and "when are you free" is the one that decides whether the enrolment
# happens at all: a weekly slot at a fixed time IS the product, and the studio
# has four rooms and four teachers to fit it into.
#
# What a seeded enquiry actually answered is REGISTRATION_ANSWERS, at the foot
# of this file; its keys are the three below. The seeder used to write the art
# pack's keys (experience / goals / availability) for every tenant.
REGISTRATION_PROFILE = {
    "title": "Tell us what they'd like to play",
    "fields": [
        {
            "key": "instrument",
            "label": "Instrument",
            "label_zh": "想学的乐器",
            "placeholder": "Piano, violin, voice, guzheng, erhu, pipa — or not sure yet",
            "placeholder_zh": "钢琴、小提琴、声乐、古筝、二胡、琵琶，或者还没想好",
            "type": "text",
        },
        {
            "key": "level",
            "label": "Where they're up to",
            "label_zh": "现在到哪一步",
            "placeholder": "Never played, a year or two, working towards a grade",
            "placeholder_zh": "没学过 / 学过一两年 / 在准备考级",
            "type": "text",
        },
        {
            "key": "availability",
            "label": "When you're free",
            "label_zh": "什么时段方便",
            "placeholder": "After school, weeknights, Saturday morning",
            "placeholder_zh": "放学后 / 工作日晚上 / 周六上午",
            "type": "text",
        },
    ],
}

COPY_PACK = {
    "portal_label": "Student & Family Portal",
    "register_intro": LOCALIZED_COPY["registration_intro"]["en"],
}

# ── people ─────────────────────────────────────────────────────────────────
#
# (role, email, full name, presenter label, public display name, on timetable)
#
# THE EMAILS MUST NOT MATCH THE ART PACK'S. `users` is keyed globally by email
# and `_seed_roles` upserts `ON CONFLICT (email) DO UPDATE`, so an address
# shared between the two packs is one row: resetting the music demo would
# rewrite the art demo's staff name and password hash, and the art demo would
# keep working right up until someone read the credential file. Hence the
# `.music` discriminator on every one of them.
#
# THE FOUR ROLE KEYS MUST BE DISTINCT. `_seed_roles` returns `key = role` and
# `_seed_schedules` looks teachers up by that key, so two accounts both with
# role 'teacher' collapse into one dict entry and every class assigned to the
# first one silently moves to the second. That is why Coral Xu — who really
# does teach — is on a `staff` account rather than a second `teacher` one, and
# the story fits: she started this term, her engagement type is not recorded
# yet, and she is on the restricted account until it is.
#
# Two of four consent to appear on the public timetable. That ratio is the
# point — a seed where everybody is public demonstrates nothing about a switch
# that defaults to off. It also produces the more interesting case: Coral
# teaches a public class, so that row renders on the public timetable with the
# room and the time and no teacher name.
ROLE_ACCOUNTS = (
    ("owner", "owner.music@pwe-studio.invalid", "Vivian H", "Owner", "Vivian", True),
    ("manager", "manager.music@pwe-studio.invalid", "Naomi Grech", "Studio Manager", "", False),
    ("teacher", "teacher.music@pwe-studio.invalid", "Hannah Delaney", "Strings Teacher", "Hannah", True),
    ("staff", "teacher2.music@pwe-studio.invalid", "Coral Xu", "Chinese Instruments Teacher", "", False),
)

# (first, last, parent_name, mobile, email, balance)
#
# Adults first, then children, because ADULT_COUNT is a boundary and not a
# filter — the seeder treats every index at or past it as a child. A music
# school inverts the art studio: three adults and nine children, where the art
# studio had ten adults and two children.
#
# The ORDER of the children is not decorative. `SCHEDULES` addresses a class
# roster as a CONTIGUOUS SLICE of this tuple, so the children are sorted so
# that every group class is one slice: the two early-years children first, then
# the strings, then the graded students who sit theory and play in the
# ensemble, then the two on Chinese instruments. Re-sorting this roster
# silently re-sorts five class rosters with it.
#
# The balances carry the operator states the CMS is meant to surface, against
# the `low_balance_threshold = 2` the seeder writes: Oliver at 1 (the next
# lesson empties the account), Daniel at 2 (on the line), Jasmine at 3 and
# Marcus at 4 (thin). A roster where everybody is comfortable demonstrates none
# of the screens that exist for the ones who are not.
#
# Angela and Ethan are siblings — same parent, same mobile, same email. They
# are the pair the money layer puts on ONE billing account, which is the case
# that makes the payer/student split worth explaining.
STUDENTS = (
    ("Rachel", "Tan", "", "0400000401", "rachel.tan@example.com", Decimal("6")),
    ("Daniel", "Okafor", "", "0400000402", "daniel.okafor@example.com", Decimal("2")),
    ("Sophie", "Nguyen", "", "0400000403", "sophie.nguyen@example.com", Decimal("8")),
    ("Chloe", "Zhang", "Yiran Zhang", "0400000407", "yiran.zhang@example.com", Decimal("9")),
    ("Jasmine", "Patel", "Nisha Patel", "0400000411", "nisha.patel@example.com", Decimal("3")),
    ("Angela", "Lin", "Grace Lin", "0400000404", "grace.lin@example.com", Decimal("9")),
    ("Oliver", "Brennan", "Deirdre Brennan", "0400000408", "d.brennan@example.com", Decimal("1")),
    ("Marcus", "Webb", "Kate Webb", "0400000406", "kate.webb@example.com", Decimal("4")),
    ("Ethan", "Lin", "Grace Lin", "0400000404", "grace.lin@example.com", Decimal("9")),
    ("Noah", "Kim", "Jihye Kim", "0400000410", "jihye.kim@example.com", Decimal("7")),
    ("Isabella", "Moretti", "Elena Moretti", "0400000405", "elena.moretti@example.com", Decimal("12")),
    ("Amelia", "Fitzgerald", "Sam Fitzgerald", "0400000409", "sam.fitzgerald@example.com", Decimal("5")),
)
ADULT_COUNT = 3

# ── the catalogue ──────────────────────────────────────────────────────────
#
# `courses.name`, `.description` and `.category` are single-language columns
# and the portal renders them verbatim in both language modes, so the names
# carry both — which is also how a bilingual Melbourne school writes its own
# signage. Nine rows rather than the art studio's four: a school teaching six
# instruments across a graded track, a VCE track, an early-years track and an
# ensemble genuinely has more product lines than a painting studio has.
#
# PRICES ARE GST-INCLUSIVE, and every one of them divides back to a whole
# number of dollars before GST ($55 → $50, $77 → $70, $99 → $90, $44 → $40,
# $19.80 → $18). That is not tidiness: invoice lines are priced ex-GST, and a
# rate card whose ex-GST figure has a fraction of a cent in it produces an
# invoice a dollar off the price a parent was quoted. The art pack advertises
# $65 and invoices $71.50; this pack does not have that gap.
#
# The ensemble is the one row where the advertised figure is a TERM levy of
# $198.00; the course carries the per-rehearsal price it divides into, and the
# $198.00 lives in `PACKAGES` where a term-length purchase belongs.
#
# THE ORDER IS LOAD-BEARING, and not in a good way. `_seed_students` picks the
# attendance course as `course_ids[3 if is_child else index % 3]`, so indices
# 0/1/2 have to be the three courses the three adults actually take (piano,
# Chinese instruments, voice — in that order) and index 3 is the single course
# every child's attendance history is written against. Musicianship is the
# least-wrong single answer for nine children on six instruments, and it is
# still wrong for the six- and seven-year-old. The music seeder should read the
# course per student rather than derive it; until it does, this ordering is the
# thing holding the roster together.
#
# (name, description, category, age_range, minutes, price_aud_cents)
COURSES = (
    (
        "钢琴一对一 Piano One-on-One",
        "五岁起，一节 30 分钟：基本功、当周曲目，最后十分钟当着家长说清楚这周练什么。也有 45 分钟和 60 分钟的课。 / From age five, thirty minutes a lesson — technique, this week's piece, and ten minutes with a parent on exactly what to practise. Forty-five and sixty-minute lessons are also available.",
        "钢琴 Piano",
        "5+",
        30,
        5500,
    ),
    (
        "民乐一对一 Chinese Instruments One-on-One",
        "古筝、二胡、琵琶，七岁起，一节 45 分钟：指法、传统曲目与视奏。教室备琴上课，家里要有一台能练。 / Guzheng, erhu and pipa from age seven, forty-five minutes: right-hand technique, traditional repertoire and reading. There are instruments here for lessons; you need one at home to practise on.",
        "民乐 Chinese instruments",
        "7+",
        45,
        7700,
    ),
    (
        "声乐一对一 Voice One-on-One",
        "八岁起，一节 30 分钟：呼吸、咬字，和一首从头唱到尾的歌。变声期照常上课，只是曲目跟着嗓子走。 / From age eight, thirty minutes: breathing, diction, and one song all the way through. Lessons carry on through a voice change; the repertoire moves with the voice.",
        "声乐 Voice",
        "8+",
        30,
        5500,
    ),
    (
        "乐理与视唱练耳 Musicianship & Aural",
        "在读学员的小组课，八人以内：乐理、听觉与视奏，对应 AMEB 六级以上实技要配的笔试科目；考期前加一次模拟。 / A group of up to eight for students already having lessons: theory, aural and sight-reading, covering the written subject AMEB pairs with practical Grade 6 and above, with a mock run-through before exam week.",
        "乐理与考级 Theory & exams",
        "在读学员 Enrolled students",
        60,
        4400,
    ),
    (
        "弦乐一对一 Strings One-on-One",
        "小提琴与大提琴，六岁起，一节 30 分钟。音阶每节都拉，曲子大约两周换一首。 / Violin and cello from age six, thirty minutes a lesson. Scales every time, and a new piece about every fortnight.",
        "弦乐 Strings",
        "6+",
        30,
        5500,
    ),
    (
        "音乐启蒙小组 Early Music Group",
        "四到六岁，六人一组 45 分钟：节奏、听辨与最初的识谱，用打击乐和游戏带着走，学期末各自挑一件乐器。 / Ages four to six, six to a group for forty-five minutes: rhythm, listening and first note-reading through percussion and games, ending the term by choosing an instrument.",
        "启蒙 Early years",
        "4–6",
        45,
        4400,
    ),
    (
        "少年乐团 Youth Ensemble",
        "九到十七岁，周六下午 90 分钟。中西乐器同台，一学期排两首，十二月在社区礼堂完整演一遍。团费按学期收，每学期 $198。 / Ages nine to seventeen, ninety minutes on Saturday afternoons. Chinese and Western instruments in one room, two works a term, played right through in December in a community hall. The levy is charged by the term at $198.",
        "合奏 Ensemble",
        "9–17",
        90,
        1980,
    ),
    (
        "小组课 · 弦乐与民乐 Small Group · Strings & Chinese Instruments",
        "同一件乐器的三到六人一组，一小时：齐奏、分部，和跟别人一起弹。要先在这里上过一对一，进度差不多的排在一组。 / Three to six players on the same instrument for an hour: unison, parts, and playing alongside other people. Open to students already having one-on-one lessons here, grouped by where they are up to.",
        "小组课 Small groups",
        "7–16",
        60,
        4400,
    ),
    (
        "VCE 音乐辅导 VCE Music Support",
        "11–12 年级，每周一小时：选曲、排练与演出准备，Repertoire 与 Contemporary Performance 两条路径都做；中乐学员另办替代乐器申请。 / Year 11 and 12, one hour a week: choosing the program, rehearsing it and getting it performance-ready, for either the Repertoire or Contemporary Performance sequence. Students on a Chinese instrument also work through the alternative instrument application.",
        "VCE",
        "Year 11–12",
        60,
        9900,
    ),
)

# (course index, name, credits, price_aud_cents, expires_after_days)
#
# A pack belongs to a COURSE, not to the studio, and that is the constraint
# worth showing: a 30-minute piano lesson and a 45-minute guzheng lesson both
# debit one credit and cost different money, so a single all-purpose pack
# cannot exist. The trial is a pack of one against the piano course because it
# has to hang somewhere; the front desk sells it for any instrument.
PACKAGES = (
    (0, "试课 · 一次 Single trial", Decimal("1"), 2750, 60),
    (0, "钢琴十次课包 · 30 分钟 Piano ten-lesson pack · 30 min", Decimal("10"), 55000, 180),
    (1, "民乐十次课包 · 45 分钟 Chinese instruments ten-lesson pack · 45 min", Decimal("10"), 77000, 180),
    (3, "乐理小组学期包 Musicianship term pack", Decimal("10"), 44000, 180),
    (6, "少年乐团 · 一学期 Youth ensemble · one term", Decimal("10"), 19800, 180),
)

# ── the week ───────────────────────────────────────────────────────────────
#
# weekday follows JS getDay(): 0=Sunday .. 6=Saturday.
#
# Seven public rows, and they are the whole of what a visitor can see. The
# studio's real week is about three times this, because piano, strings, voice,
# Chinese-instrument and VCE lessons are one-to-one and one-to-one teaching
# belongs in `lesson_series`, which the public timetable never shows —
# `is_public` defaults to FALSE on class_schedules for exactly that reason.
# `TIMETABLE_SECTION.lead` says so on the page, so an empty-looking Tuesday
# reads as a school with a full diary rather than a school with no students.
#
# Saturday is the busy day, which is what a music school's week actually looks
# like: nothing before school, weekday classes from 16:00 once pickup is done,
# and everything else on Saturday. Checked by hand: no teacher and no room is
# booked twice, and Hannah's 11:00 theory runs straight into her 12:00 strings
# group in a different room.
#
# (course index, label, weekday, start, minutes, capacity, room, teacher role, roster slice)
SCHEDULES = (
    (5, "音乐启蒙 · 周三放学后 Early Music · Wed", 3, "16:00", 45, 6, "琴房二 Studio 2", "manager", (3, 5)),
    (3, "乐理与视唱练耳 · 周三晚 Musicianship · Wed", 3, "17:30", 60, 8, "大琴房 Recital Room", "teacher", (7, 10)),
    (5, "音乐启蒙 · 周六上午 Early Music · Sat", 6, "10:00", 45, 6, "琴房二 Studio 2", "manager", (3, 5)),
    (3, "乐理与视唱练耳 · 周六上午 Musicianship · Sat", 6, "11:00", 60, 8, "大琴房 Recital Room", "teacher", (7, 11)),
    (7, "小组课 · 弦乐 · 周六 Strings Small Group · Sat", 6, "12:00", 60, 6, "琴房一 Studio 1", "teacher", (5, 8)),
    (6, "少年乐团 · 周六下午 Youth Ensemble · Sat", 6, "13:00", 90, 12, "大琴房 Recital Room", "owner", (6, 12)),
    (7, "小组课 · 民乐 · 周六 Chinese Instruments Small Group · Sat", 6, "14:30", 60, 6, "古筝房 Guzheng Room", "staff", (10, 12)),
)

# Two cancellations, because a timetable that has never been corrected does
# not demonstrate that it CAN be. (schedule index, days from today, note)
#
# Both dates have to land INSIDE the two-week window the page projects, or the
# seed silently demonstrates nothing: `_next_occurrence` walks forward to the
# class's own weekday, so a naive "12 days out" can end up on day 18 for a
# Saturday class. Five days from today on a Wednesday class reaches day 11 at
# worst; three days on a Saturday class reaches day 9.
SCHEDULE_EXCEPTIONS = (
    (0, 5, "停课 · 学校公众假期 Closed · school public holiday"),
    (4, 3, "停课 · 老师带学生去考场 Closed · teacher at an exam session"),
)

# Three pending requests against the next occurrence of a class.
# (schedule index, days ahead, name, phone, message)
#
# All three land on Saturday classes, so the same walk-forward arithmetic
# applies: 2, 4 and 6 days out reach day 8, 10 and 12 at worst.
BOOKINGS = (
    (2, 2, "Wendy Lam", "0400000301",
     "女儿四岁半，想先来听一次周六的启蒙课。 / Our daughter is four and a half — could she sit in on a Saturday early music class first?"),
    (5, 4, "陈立 Li Chen", "0400000302",
     "孩子二胡学了两年，想问乐团还收人吗？ / Two years of erhu behind him — is the ensemble taking new players?"),
    (3, 6, "Priya Anand", "0400000303",
     "钢琴要考六级，笔试还没着落，周六的乐理课有位置吗？ / Working towards Grade 6 piano and still needs the written subject — is there a place on Saturday?"),
)

# The enquiry pipeline, one row per state the CMS can show.
# (status, first, last, parent, mobile, email, message, follow_up_days)
#
# first/last is the STUDENT and `parent` is whoever is asking, which is why
# most of these have one and the adult beginner does not — the field is the
# difference between an enquiry about a child and an enquiry about oneself,
# and a pipeline where every row has a parent is a pipeline copied from a
# children's studio.
REGISTRATIONS = (
    ("pending", "Ivy", "Sandoval", "Marisol Sandoval", "0400000201", "marisol.sandoval@example.com",
     "女儿七岁，想学钢琴，周六上午方便。 / Our daughter is seven and would like to start piano; Saturday mornings suit us.", None),
    ("contacted", "Hugo", "Bennett", "Claire Bennett", "0400000202", "claire.bennett@example.com",
     "小提琴学了三年，想换个老师，先上一节看看。 / Three years of violin and looking for a new teacher — happy to start with one lesson.", 3),
    ("trial_booked", "Lena", "Kowalski", "", "0400000203", "lena.kowalski@example.com",
     "成人零基础，已约周三晚上的试课。 / Adult beginner; trial booked for Wednesday evening.", 5),
    ("waiting", "Tommy", "Zhao", "赵敏 Min Zhao", "0400000204", "min.zhao@example.com",
     "想学古筝，等下学期有位置。 / Would like to learn guzheng and is waiting for a place next term.", 8),
    ("converted", "Ruby", "Nakamura", "Mari Nakamura", "0400000205", "mari.nakamura@example.com",
     "已报名周六上午的启蒙小组。 / Enrolled in the Saturday morning early music group.", None),
)


# ── what the seeder used to hold ─────────────────────────────────────────────
#
# The same six the art pack lifted out of reset_professional_demo.py, so that a
# second industry is a second module rather than a branch in the seeder.

#: Follows the studio name in the public page title.
SEO_TAGLINE = {
    "zh": "墨尔本 Glen Waverley 音乐教室",
    "en": "music lessons in Glen Waverley, Melbourne",
}

#: Printed on every issued invoice, under the bank details. Bilingual, because
#: this studio's families are: the Chinese half is not a translation of the
#: English one, it is the sentence the Chinese-speaking parents are actually
#: sent. The art pack's is Chinese only.
PAYMENT_NOTE = (
    "请在到期日前转账，备注里写上发票号；也可以在前台刷卡。 / "
    "Please transfer before the due date with the invoice number as the "
    "reference, or pay by card at the front desk."
)

#: The rooms a recurring class can be scheduled into. Index 0 is the room a
#: one-to-one lesson lands in by default — and the first two are the two small
#: studios with the uprights, because the seeder's two standing lessons are
#: both piano students and it picks rooms by `index % len`. The same four names
#: appear in `SCHEDULES` and in the manifest's room captions; there are four
#: rooms, and `ABOUT` says so on the public page.
ROOM_NAMES = [
    "琴房一 Studio 1",
    "琴房二 Studio 2",
    "古筝房 Guzheng Room",
    "大琴房 Recital Room",
]

#: (name, kind, contact_name, email, mobile, payment_terms_days)
#: `kind` is person / family / organisation.
#:
#: Four payers because there are four cases: a family with two children on one
#: invoice, an adult who is her own payer, a family with one child, and a school
#: that buys a programme rather than a child's lessons. The adult is the row
#: that makes the point — a payer is not a synonym for a parent.
#:
#: Which student sits on which account is BILLING_LINKS, below — the seeder
#: used to hold the art roster's pairs as a literal and would have put an
#: unrelated adult and child on the Lin family account.
PAYERS = [
    ("Lin 一家 Lin family", "family", "Grace Lin", "grace.lin@example.com", "0400000404", 14),
    ("Rachel Tan", "person", "Rachel Tan", "rachel.tan@example.com", "0400000401", 14),
    ("Zhang 一家 Zhang family", "family", "Yiran Zhang", "yiran.zhang@example.com", "0400000407", 14),
    ("Kellerton Park Primary School", "organisation", "Alice Freeman",
     "office@kellertonpark.example", "03 5550 0712", 30),
]

#: (payer index, issued days ago, status, [(description, qty, unit_cents, tax_bp, kind)])
#: Every state a studio meets: paid, part paid, an overdue one, an issued one
#: not yet due, and a draft the front desk has not sent.
#:
#: UNIT PRICES ARE EX-GST and every one is a whole number of dollars, so
#: quantity × unit × 1.1 lands on an exact cent and each line comes back to the
#: figure on the rate card in the FAQ: $50 → $55, $70 → $77, $90 → $99,
#: $40 → $44, $180 → $198. A studio whose invoice does not match its own price
#: list is the first thing a parent rings about.
#:
#: There is no 'overdue' status in the schema and none is written here: row 2
#: is `issued` with an issue date 45 days back against 14-day terms, so the
#: ageing report derives 31 days overdue. Seeding a literal would produce a row
#: that stops being true tomorrow.
#:
#: The order matters: `_seed_money_layer` takes the payment for invoice 0 from
#: payer 0 and the payment for invoice 1 from payer 1, so the paid row and the
#: part-paid row have to be the first two.
INVOICE_PLAN = [
    (0, 34, "paid", [
        ("第三学期学费 · 小提琴一对一 30 分钟 · Angela Lin / "
         "Term 3 tuition · violin 1-on-1 30 min · Angela Lin", "10", 5000, 1000, "tuition"),
        ("第三学期学费 · 钢琴一对一 30 分钟 · Ethan Lin / "
         "Term 3 tuition · piano 1-on-1 30 min · Ethan Lin", "10", 5000, 1000, "tuition"),
        ("少年乐团 · 第三学期团费 · Ethan Lin / "
         "Youth ensemble · Term 3 levy · Ethan Lin", "1", 18000, 1000, "tuition"),
    ]),
    (1, 20, "part_paid", [
        ("第三学期学费 · 钢琴一对一 45 分钟 · Rachel Tan / "
         "Term 3 tuition · piano 1-on-1 45 min · Rachel Tan", "10", 7000, 1000, "tuition"),
    ]),
    (2, 45, "issued", [
        ("第三学期学费 · 钢琴一对一 30 分钟 · Chloe Zhang / "
         "Term 3 tuition · piano 1-on-1 30 min · Chloe Zhang", "10", 5000, 1000, "tuition"),
        ("音乐启蒙小组 · 第三学期 · Chloe Zhang / "
         "Early music group · Term 3 · Chloe Zhang", "10", 4000, 1000, "tuition"),
    ]),
    (3, 12, "issued", [
        ("校内合奏工作坊 · 第三学期共 8 次 / "
         "In-school ensemble workshop · 8 sessions across Term 3", "8", 32000, 1000, "engagement"),
        # A hire, not a shop: the product bills for four instruments going out
        # the door and does not pretend to manage a fleet. It is here because
        # revenue-by-source with one bar on it teaches nothing — delete this one
        # line if the instrument-retail question would be unwelcome in the room.
        ("古筝借用 · 4 台 · 一学期 / Guzheng hire · 4 instruments · one term",
         "4", 12000, 1000, "rental"),
    ]),
    (0, None, "draft", [
        ("第四学期学费 · 小提琴一对一 30 分钟 · Angela Lin / "
         "Term 4 tuition · violin 1-on-1 30 min · Angela Lin", "10", 5000, 1000, "tuition"),
        ("第四学期学费 · 钢琴一对一 30 分钟 · Ethan Lin / "
         "Term 4 tuition · piano 1-on-1 30 min · Ethan Lin", "10", 5000, 1000, "tuition"),
        ("十二月音乐会服装与场地分摊 · 两人 / "
         "December concert costume and venue share · two students", "2", 4000, 1000, "manual"),
    ]),
]

#: What a generated progress report says. `lessons` is (days before period end,
#: the teacher's note); the seeder supplies the dates and the attendance
#: roll-up.
#:
#: FOUR of them, one per student, because the seeder hands report `index % len`
#: to student `index` over the first four of the roster — with a single entry
#: every family reads the same three sentences, and with four the piano student
#: gets the piano report. Order follows STUDENTS: Rachel (piano), Daniel
#: (erhu), Sophie (voice), Chloe (piano, six years old and one term in). The
#: first two are published; the last two stay draft, which is what puts
#: something in the Pending worklist.
#:
#: The notes are bilingual because `ABOUT` promises on the public page that
#: lesson notes and the end-of-term report are written in both. A note is the
#: only place in the whole schema where instrument, repertoire and exam
#: progress can live — there is no column for any of them — so this is also
#: where the demonstration of "the product collects what a teacher writes and
#: freezes it" actually happens.
PROGRESS_REPORTS = [
    {
        "course_name": "钢琴一对一 Piano One-on-One",
        "lessons": (
            (21, "巴赫那首前奏曲还在分段练，右手比左手快半拍。 / "
                 "Still working the Bach prelude in sections; the right hand runs ahead of the left."),
            (14, "整首连起来了，踏板每次都换晚半拍。 / "
                 "It holds together now, but the pedal is half a beat late every time."),
            (7, "这节课只练踏板，一小节一小节地对。 / "
                "Pedal only this lesson, one bar at a time."),
        ),
        "comment": "这一段最大的进步是肯把速度放下来。踏板还是慢半拍——这不是耳朵的问题，是脚在等手。"
                   "下一段先把踏板单独练熟，再回到整首。 / "
                   "The real gain this term was being willing to slow down. The pedal is still "
                   "late, which is not a listening problem — the foot is waiting for the hand. "
                   "Next block: practise the pedal on its own, then put the piece back together.",
    },
    {
        "course_name": "民乐一对一 Chinese Instruments One-on-One",
        "lessons": (
            (21, "《良宵》分段慢练，换把的时候左肩跟着抬起来。 / "
                 "Peaceful Evening section by section; the left shoulder rides up on every shift."),
            (14, "空弦长弓，先把肩膀放回去。 / "
                 "Long bows on open strings, to put the shoulder back down."),
            (7, "整首能拉下来了，换把的地方还紧。 / "
                "He can play right through now; the position changes are still tight."),
        ),
        "comment": "整首拉下来是这一段的目标，已经做到了。剩下的问题都在左肩：一紧就抬。"
                   "回家每天三分钟空弦长弓就够，练多了反而把毛病练牢。 / "
                   "Playing it right through was the goal for this block, and he got there. What "
                   "is left is all in the left shoulder, which lifts the moment he tenses. Three "
                   "minutes of long bows on open strings a day is enough — more than that and he "
                   "practises the fault in.",
    },
    {
        "course_name": "声乐一对一 Voice One-on-One",
        "lessons": (
            (21, "《Santa Lucia》先把词念一遍再唱，咬字稳了不少。 / "
                 "Speaking the words before singing them has steadied the diction in Santa Lucia."),
            (14, "换声区还是挤，用哼鸣找位置。 / "
                 "The register change still tightens; humming first to find the placement."),
            (7, "整句连起来唱，换声的地方还要再松一点。 / "
                "Singing whole phrases now; the change still needs to loosen."),
        ),
        "comment": "换声区是这一段唯一的重点，别的都往后放。哼鸣找到的位置要能带进整句里，"
                   "现在还只在单音上站得住。 / "
                   "The register change is the only thing to work on this block; everything else "
                   "can wait. The placement she finds when humming has to survive into a whole "
                   "phrase, and right now it only holds on single notes.",
    },
    {
        "course_name": "钢琴一对一 Piano One-on-One",
        "lessons": (
            (21, "第一节课认了五个音，坐姿要一直提醒。 / "
                 "Five notes named in her first lesson; she still needs reminding to sit tall."),
            (14, "五指位置自己能找到了，手腕还塌。 / "
                 "She finds the five-finger position herself now; the wrist still drops."),
            (7, "在家每天摸五分钟琴，这周就够了。 / "
                "Five minutes at the piano a day is plenty this week."),
        ),
        "comment": "六岁的第一个学期，能坐满三十分钟本身就是进度。手腕和坐姿慢慢来，在家别纠。 / "
                   "A first term at six: sitting through thirty minutes is itself the progress. "
                   "The wrist and the posture will come — please don't correct them at home.",
    },
]


#: (billing account index, student index) — who shares an account with whom.
#:
#: Angela and Ethan Lin are the siblings, and they are indices 5 and 8 rather
#: than 0 and 1, because this roster is ordered by CLASS so that every group
#: class is a contiguous slice. Rachel Tan pays for herself, which is the row
#: that shows a payer need not be a parent. The school buys a programme and has
#: no student attached at all.
BILLING_LINKS = ((0, 5), (0, 8), (1, 0), (2, 3))

#: One course index per student, positionally — which class that student's
#: attendance history is written against.
#:
#: This has to agree with what the rest of the pack already says about each
#: student, because the CMS shows them on one screen: Angela's invoice line
#: says violin, so her attendance is strings; Isabella and Amelia are the two
#: on Chinese instruments; the three adults take the three courses their
#: progress reports are written about. A roster-wide default cannot get this
#: right at a school teaching six instruments — the art studio could, because
#: every child there was in the same Saturday class.
#:
#:   0 Rachel    piano          3 Chloe    piano        6 Oliver   strings
#:   1 Daniel    erhu           4 Jasmine  early years  7 Marcus   musicianship
#:   2 Sophie    voice          5 Angela   violin       8 Ethan    piano
#:   9 Noah      musicianship  10 Isabella guzheng     11 Amelia   guzheng
ATTENDANCE_COURSE_INDEX = (0, 1, 2, 0, 5, 4, 4, 3, 0, 3, 1, 1)


#: What each seeded enquiry answered on the registration form. The KEYS are the
#: `key` of each field in REGISTRATION_PROFILE — instrument / level /
#: availability — and NOT the art pack's experience / goals / availability.
#:
#: One entry per row of REGISTRATIONS, in the same order, because an operator
#: opening the pipeline reads the message and the answers side by side: a
#: seven-year-old starting piano and an adult beginner who has already booked a
#: Wednesday trial cannot both have answered the same three questions the same
#: way.
REGISTRATION_ANSWERS = (
    {"instrument": "Piano", "level": "Never played",
     "availability": "Saturday morning"},
    {"instrument": "Violin", "level": "Three years, working towards Grade 4",
     "availability": "After school, weeknights"},
    {"instrument": "Piano", "level": "Adult beginner, never played",
     "availability": "Wednesday evening"},
    {"instrument": "Guzheng", "level": "Never played",
     "availability": "Saturday, any time"},
    {"instrument": "Not sure yet — whatever suits a five-year-old",
     "level": "Never played", "availability": "Saturday morning"},
)

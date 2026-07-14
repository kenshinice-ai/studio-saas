"""Single source of truth for industry onboarding and public-site presets."""

from __future__ import annotations


def _field(
    key: str,
    label_en: str,
    label_zh: str,
    placeholder_en: str,
    placeholder_zh: str,
) -> dict:
    return {
        "key": key,
        "label": label_en,
        "label_en": label_en,
        "label_zh": label_zh,
        "placeholder": placeholder_en,
        "placeholder_en": placeholder_en,
        "placeholder_zh": placeholder_zh,
        "type": "text",
        "required": False,
        "options": [],
    }


INDUSTRY_PRESETS: dict[str, dict] = {
    "art": {
        "label": "Art",
        "label_zh": "艺术",
        "layout": "editorial",
        "slogan": "Create boldly. Grow visibly.",
        "hero": {
            "title": {"zh": "让创意被看见，让成长有作品。", "en": "Create boldly. Grow visibly."},
            "subtitle": {"zh": "从兴趣启发到系统表达，记录每一次真实成长。", "en": "From first ideas to confident expression, make every stage of growth visible."},
        },
        "registration_title": "Creative Preferences",
        "registration_title_zh": "告诉我们学员喜欢怎样创作",
        "copy_pack": {"portal_label": "Student Art Portal", "register_intro": "Tell us about the student and their creative goals."},
        "register_intro_zh": "告诉我们学员喜欢的创作方式、经验与学习目标。",
        "theme": {"background_color": "#FFF7F3", "panel_color": "#FFFFFF", "text_color": "#2B2118", "accent_color": "#A23E5C", "secondary_accent_color": "#6B4F3A", "button_style": "soft", "font_mood": "serif"},
        "fields": [
            _field("artStyle", "Preferred style", "喜欢的艺术形式", "Watercolour, sketching, acrylic", "水彩、素描、丙烯等"),
            _field("experience", "Current experience", "目前经验", "Beginner, some experience, portfolio prep", "零基础、有一定经验、作品集准备"),
            _field("goals", "Creative goals", "创作目标", "Relax, build technique, portfolio prep", "培养兴趣、提升技法、准备作品集"),
        ],
    },
    "music": {
        "label": "Music", "label_zh": "音乐", "layout": "performance",
        "slogan": "Find your rhythm. Make every practice count.",
        "hero": {"title": {"zh": "找到自己的节奏，让每次练习都有回应。", "en": "Find your rhythm. Make every practice count."}, "subtitle": {"zh": "清晰的目标、适合的节奏与看得见的音乐成长。", "en": "Clear goals, the right pace, and musical progress you can hear."}},
        "registration_title": "Music Goals", "registration_title_zh": "告诉我们学员的音乐目标",
        "copy_pack": {"portal_label": "Music Student Portal", "register_intro": "Tell us about the student and their music goals."},
        "register_intro_zh": "告诉我们乐器、当前水平和希望达成的音乐目标。",
        "theme": {"background_color": "#F7F5FF", "panel_color": "#FFFFFF", "text_color": "#201A35", "accent_color": "#5B3FA8", "secondary_accent_color": "#1F2A44", "button_style": "soft", "font_mood": "classic"},
        "fields": [
            _field("instrument", "Instrument", "乐器或声乐", "Piano, guitar, violin, voice", "钢琴、吉他、小提琴、声乐等"),
            _field("level", "Current level", "当前水平", "Beginner, AMEB Grade 2, self-taught", "零基础、考级程度、自学经验"),
            _field("goals", "Music goals", "音乐目标", "Exam prep, performance, confidence", "考级、演出、兴趣或自信表达"),
        ],
    },
    "math": {
        "label": "Math", "label_zh": "数学", "layout": "structured",
        "slogan": "Understand the method. Build lasting confidence.",
        "hero": {"title": {"zh": "理解方法，建立信心，稳步进阶。", "en": "Understand the method. Build lasting confidence."}, "subtitle": {"zh": "找准知识缺口，用清晰方法建立可持续的学习能力。", "en": "Find the gaps, learn a clear method, and build skills that last."}},
        "registration_title": "Learning Focus", "registration_title_zh": "告诉我们目前的学习阶段与难点",
        "copy_pack": {"portal_label": "Math Learning Portal", "register_intro": "Tell us about the learner and the topics they need help with."},
        "register_intro_zh": "告诉我们年级、当前难点与希望提升的方向。",
        "theme": {"background_color": "#F3F7FF", "panel_color": "#FFFFFF", "text_color": "#172033", "accent_color": "#1D4ED8", "secondary_accent_color": "#0F766E", "button_style": "sharp", "font_mood": "modern"},
        "fields": [
            _field("yearLevel", "Year level", "年级", "Year 5, Year 9, VCE", "五年级、九年级、VCE 等"),
            _field("topics", "Topic focus", "重点内容", "Algebra, fractions, problem solving", "代数、分数、应用题等"),
            _field("goals", "Learning goals", "学习目标", "Catch up, extension, exam confidence", "补基础、拓展、考试信心"),
        ],
    },
    "dance": {
        "label": "Dance", "label_zh": "舞蹈", "layout": "expressive",
        "slogan": "Move with confidence. Grow through practice.",
        "hero": {"title": {"zh": "在节奏中表达，在训练中成长。", "en": "Move with confidence. Grow through practice."}, "subtitle": {"zh": "兼顾技术、体态与舞台表达，让每一步更自信。", "en": "Build technique, presence, and confidence in every movement."}},
        "registration_title": "Dance Preferences", "registration_title_zh": "告诉我们舞者的年龄、经验与目标",
        "copy_pack": {"portal_label": "Dance Student Portal", "register_intro": "Tell us about the dancer and their goals."},
        "register_intro_zh": "告诉我们喜欢的舞种、当前水平与训练目标。",
        "theme": {"background_color": "#FFF4F8", "panel_color": "#FFFFFF", "text_color": "#2D1723", "accent_color": "#B4236E", "secondary_accent_color": "#6D315E", "button_style": "rounded", "font_mood": "classic"},
        "fields": [
            _field("danceStyle", "Dance style", "喜欢的舞种", "Ballet, jazz, hip hop, contemporary", "芭蕾、爵士、街舞、现代舞等"),
            _field("level", "Current level", "当前水平", "Beginner, intermediate, exam stream", "零基础、中级、考级方向"),
            _field("goals", "Dance goals", "舞蹈目标", "Fitness, performance, technique", "体能、表演、技术提升"),
        ],
    },
    "language": {
        "label": "Language", "label_zh": "语言", "layout": "friendly",
        "slogan": "Find your voice. Connect with the world.",
        "hero": {"title": {"zh": "开口表达，连接更大的世界。", "en": "Find your voice. Connect with the world."}, "subtitle": {"zh": "从真实沟通出发，建立能够长期使用的语言能力。", "en": "Build practical language skills through real communication."}},
        "registration_title": "Language Goals", "registration_title_zh": "告诉我们学习语言与当前水平",
        "copy_pack": {"portal_label": "Language Student Portal", "register_intro": "Tell us about the learner and their language goals."},
        "register_intro_zh": "告诉我们目标语言、当前水平与使用场景。",
        "theme": {"background_color": "#F2FBFC", "panel_color": "#FFFFFF", "text_color": "#163036", "accent_color": "#0E7490", "secondary_accent_color": "#7C3AED", "button_style": "rounded", "font_mood": "modern"},
        "fields": [
            _field("language", "Language", "目标语言", "English, Mandarin, Japanese, French", "英语、中文、日语、法语等"),
            _field("level", "Current level", "当前水平", "Beginner, conversational, exam prep", "零基础、日常交流、考试准备"),
            _field("goals", "Language goals", "语言目标", "Speaking, school support, travel", "口语、学校辅导、旅行或工作"),
        ],
    },
    "sports": {
        "label": "Sports", "label_zh": "运动", "layout": "energetic",
        "slogan": "Train with purpose. Grow stronger every session.",
        "hero": {"title": {"zh": "有目标地训练，一次比一次更强。", "en": "Train with purpose. Grow stronger every session."}, "subtitle": {"zh": "科学训练、清晰反馈与持续进步。", "en": "Purposeful coaching, clear feedback, and steady progress."}},
        "registration_title": "Training Goals", "registration_title_zh": "告诉我们运动项目、水平与训练目标",
        "copy_pack": {"portal_label": "Sports Student Portal", "register_intro": "Tell us about the athlete and their training goals."},
        "register_intro_zh": "告诉我们运动项目、当前水平与训练目标。",
        "theme": {"background_color": "#F4FAF5", "panel_color": "#FFFFFF", "text_color": "#17251A", "accent_color": "#166534", "secondary_accent_color": "#B45309", "button_style": "sharp", "font_mood": "modern"},
        "fields": [
            _field("sport", "Sport", "运动项目", "Tennis, swimming, basketball, soccer", "网球、游泳、篮球、足球等"),
            _field("level", "Current level", "当前水平", "Beginner, club, competition", "零基础、俱乐部、比赛级别"),
            _field("goals", "Training goals", "训练目标", "Fitness, technique, competition prep", "体能、技术、比赛准备"),
        ],
    },
    "game": {
        "label": "Game", "label_zh": "游戏与编程", "layout": "digital",
        "slogan": "Play, think, create, and level up.",
        "hero": {"title": {"zh": "在游戏中思考、创造与协作。", "en": "Play, think, create, and level up."}, "subtitle": {"zh": "把兴趣转化为策略、编程、创造力与团队能力。", "en": "Turn play into strategy, coding, creativity, and teamwork."}},
        "registration_title": "Game Learning Goals", "registration_title_zh": "告诉我们感兴趣的游戏、编程或策略方向",
        "copy_pack": {"portal_label": "Game Student Portal", "register_intro": "Tell us about the player and their learning goals."},
        "register_intro_zh": "告诉我们感兴趣的方向、当前经验与学习目标。",
        "theme": {"background_color": "#F6F4FF", "panel_color": "#FFFFFF", "text_color": "#1F1735", "accent_color": "#5B21B6", "secondary_accent_color": "#0F766E", "button_style": "rounded", "font_mood": "modern"},
        "fields": [
            _field("gameType", "Game or activity", "游戏或活动方向", "Roblox, Minecraft, chess, coding games", "Roblox、Minecraft、国际象棋、编程游戏"),
            _field("level", "Current level", "当前经验", "Beginner, casual, competitive", "零基础、兴趣玩家、竞赛方向"),
            _field("goals", "Learning goals", "学习目标", "Strategy, coding, teamwork, confidence", "策略、编程、团队合作、自信"),
        ],
    },
    "general": {
        "label": "General", "label_zh": "通用", "layout": "neutral",
        "slogan": "A learning path that fits every student.",
        "hero": {"title": {"zh": "适合每个学员的成长路径。", "en": "A learning path that fits every student."}, "subtitle": {"zh": "从兴趣和目标出发，在适合的节奏中稳步成长。", "en": "Start with the learner's interests and goals, then grow at the right pace."}},
        "registration_title": "Student Preferences", "registration_title_zh": "告诉我们学员的兴趣与学习目标",
        "copy_pack": {"portal_label": "Student Portal", "register_intro": "Tell us about the student and their goals."},
        "register_intro_zh": "告诉我们学员的兴趣、经验与希望达成的目标。",
        "theme": {"background_color": "#F8FAFC", "panel_color": "#FFFFFF", "text_color": "#1E293B", "accent_color": "#1E40AF", "secondary_accent_color": "#0F766E", "button_style": "soft", "font_mood": "modern"},
        "fields": [
            _field("interests", "Interests", "兴趣方向", "What does the student enjoy?", "学员平时喜欢什么？"),
            _field("experience", "Experience", "当前经验", "Beginner, some experience, advanced", "零基础、有一定经验、进阶"),
            _field("goals", "Goals", "学习目标", "Confidence, skills, exam prep, fun", "自信、技能、考试准备或兴趣"),
        ],
    },
}


def public_industry_presets() -> dict[str, dict]:
    """Return the client-safe preset shape used by both admin surfaces."""

    result: dict[str, dict] = {}
    for key, preset in INDUSTRY_PRESETS.items():
        result[key] = {
            "label": preset["label"],
            "labelZh": preset["label_zh"],
            "layout": preset["layout"],
            "slogan": preset["slogan"],
            "portalLabel": preset["copy_pack"]["portal_label"],
            "registerIntro": preset["copy_pack"]["register_intro"],
            "registerIntroZh": preset["register_intro_zh"],
            "registrationTitle": preset["registration_title"],
            "registrationTitleZh": preset["registration_title_zh"],
            "localizedCopy": {
                "hero_title": preset["hero"]["title"],
                "hero_subtitle": preset["hero"]["subtitle"],
                "primary_cta": {"zh": "预约体验", "en": "Book a Trial"},
                "secondary_cta": {"zh": "查看课程", "en": "Explore Programs"},
                "registration_title": {"zh": preset["registration_title_zh"], "en": preset["registration_title"]},
                "registration_intro": {"zh": preset["register_intro_zh"], "en": preset["copy_pack"]["register_intro"]},
            },
            "visualTheme": dict(preset["theme"]),
            "registrationProfile": {"title": preset["registration_title"], "fields": [dict(field) for field in preset["fields"]]},
        }
    return result

"""Single source of truth for industry onboarding and public-site presets."""

from __future__ import annotations


# ── Visual style presets ─────────────────────────────────────────────────────
#
# Eight themes, each shipping a matched light and dark variant (except
# arcade-lime, see below). Every value was solved for a measured WCAG contrast
# target by docs/design/palette_gen.py rather than picked by eye; the generator
# asserts 35 pairs per theme-mode, 525 in total. Re-run it before editing any
# hex by hand:
#
#     python3 docs/design/palette_gen.py            # verify
#     python3 docs/design/palette_gen.py --table    # inspect
#
# What the previous seven presets got wrong, and what changed:
#
#   A1  border_color measured 1.26-1.87:1 against the page on all seven,
#       failing WCAG 1.4.11 for the input borders that used it. The token is
#       split: border_color stays soft for dividers, border_strong_color
#       carries interactive boundaries at >=3:1.
#   A2  success/warning/danger had 4/2/5 unrelated values across the set with
#       no system. They now share hue anchors (152/36/6) nudged 4% toward the
#       theme, with saturation pulled 60% toward that theme's own accent and
#       lightness re-solved against every surface the role lands on — page,
#       alt band, panel, its own solid fill, and the accent it must not be
#       confused with. Semantic values therefore DIFFER per theme; a theme
#       picker must show them alongside the themed swatches, not as a shared
#       row.
#   A3  five of seven accent/secondary pairs sat 140-175 degrees apart -
#       near-complementary, the highest-tension relationship. The set now spans
#       split-complementary, analogous, triadic and monochrome.
#   A4  themes are designed as light/dark pairs rather than six light plus one
#       dark, and each carries hover/pressed/disabled/focus/scrim so
#       interaction states exist in both modes.
#
# arcade-lime is dark-only on purpose: a neon-lime accent cannot reach 4.5:1 on
# a light page without turning olive, which would betray the theme's reason for
# existing.
#
# studio-ink keeps a near-black accent - its authority comes from ink on paper -
# but carries one very low-chroma slate note as its secondary, so links and
# selected states are not left to font-weight alone.

VISUAL_STYLE_PRESETS: dict[str, dict] = {
    "atelier-clay": {
        "label": "Atelier Clay", "label_zh": "陶土工坊",
        "description": "Warm clay on a paper surface, the way a gallery wall behaves — for studios where the work should lead.",
        "description_zh": "陶土的暖调落在纸质表面，像画廊的墙。适合让作品自己说话的工作室。",
        "mood": "warm, tactile, gallery",
        "harmony": "split-complementary",
        "modes": ['light', 'dark'],
        "themes": {
            "light": {
                "color_scheme": "light", "background_color": "#F3ECEA", "background_alt_color": "#EADFDB",
                "panel_color": "#FDFDFD", "text_color": "#211B19", "text_soft_color": "#473D3A",
                "muted_text_color": "#6E605C", "border_color": "#DFD8D5", "border_strong_color": "#917A72",
                "accent_color": "#955037", "accent_text_color": "#FFFFFF", "accent_hover_color": "#7F442F",
                "accent_pressed_color": "#683826", "secondary_accent_color": "#3F6B61", "secondary_text_color": "#FFFFFF",
                "success_color": "#2D784E", "warning_color": "#5A411D", "danger_color": "#753129",
                "focus_ring_color": "#BA6445", "disabled_surface_color": "#E6D9D5", "disabled_text_color": "#867A76",
                "scrim_color": "rgba(0,0,0,0.5)",
            },
            "dark": {
                "color_scheme": "dark", "background_color": "#150F0D", "background_alt_color": "#3A2D28",
                "panel_color": "#281E1B", "text_color": "#ECEAE9", "text_soft_color": "#CEC8C6",
                "muted_text_color": "#A19693", "border_color": "#4A3D38", "border_strong_color": "#8A756D",
                "accent_color": "#CE9985", "accent_text_color": "#14110F", "accent_hover_color": "#D8AE9E",
                "accent_pressed_color": "#E2C4B8", "secondary_accent_color": "#75AB9E", "secondary_text_color": "#14110F",
                "success_color": "#388D5E", "warning_color": "#A07537", "danger_color": "#C16155",
                "focus_ring_color": "#BB6646", "disabled_surface_color": "#43342E", "disabled_text_color": "#897E79",
                "scrim_color": "rgba(0,0,0,0.66)",
            },
        },
    },
    "vintage-press": {
        "label": "Vintage Press", "label_zh": "复古印刷",
        "description": "The ink-and-paper restraint of an old print shop, for studios whose credibility rests on words and experience.",
        "description_zh": "老式印刷的墨与纸，克制的暖棕。适合靠文字与经验建立信任的工作室。",
        "mood": "editorial, cultured",
        "harmony": "split-complementary",
        "modes": ['light', 'dark'],
        "themes": {
            "light": {
                "color_scheme": "light", "background_color": "#F3EFEA", "background_alt_color": "#EAE3DB",
                "panel_color": "#FDFDFD", "text_color": "#221E1A", "text_soft_color": "#46403A",
                "muted_text_color": "#6C635A", "border_color": "#DFDAD5", "border_strong_color": "#8D7F70",
                "accent_color": "#835D33", "accent_text_color": "#FFFFFF", "accent_hover_color": "#6D4D2A",
                "accent_pressed_color": "#573E22", "secondary_accent_color": "#4C6877", "secondary_text_color": "#FFFFFF",
                "success_color": "#2F7951", "warning_color": "#5B421F", "danger_color": "#76332A",
                "focus_ring_color": "#A3743F", "disabled_surface_color": "#E6DED5", "disabled_text_color": "#857E76",
                "scrim_color": "rgba(0,0,0,0.5)",
            },
            "dark": {
                "color_scheme": "dark", "background_color": "#15120D", "background_alt_color": "#3A3228",
                "panel_color": "#28221B", "text_color": "#F1F0EE", "text_soft_color": "#D1CECA",
                "muted_text_color": "#A29C94", "border_color": "#4A4238", "border_strong_color": "#887B6C",
                "accent_color": "#C49F74", "accent_text_color": "#14120F", "accent_hover_color": "#CFB08D",
                "accent_pressed_color": "#D9C2A6", "secondary_accent_color": "#8AA5B2", "secondary_text_color": "#14120F",
                "success_color": "#3A8E60", "warning_color": "#A07739", "danger_color": "#C06559",
                "focus_ring_color": "#A67740", "disabled_surface_color": "#433A2E", "disabled_text_color": "#8B847B",
                "scrim_color": "rgba(0,0,0,0.66)",
            },
        },
    },
    "studio-ink": {
        "label": "Studio Ink", "label_zh": "黑白纸墨",
        "description": "Near-monochrome ink on paper, with a single slate-blue note marking what can be clicked.",
        "description_zh": "近乎黑白的纸与墨，只用一抹石板蓝标出可点击之处，内容始终是主角。",
        "mood": "timeless, content-led",
        "harmony": "neutral / monochrome",
        "modes": ['light', 'dark'],
        "themes": {
            "light": {
                "color_scheme": "light", "background_color": "#EFEEEE", "background_alt_color": "#E3E2E2",
                "panel_color": "#FDFDFD", "text_color": "#1E1D1D", "text_soft_color": "#404040",
                "muted_text_color": "#646363", "border_color": "#DADADA", "border_strong_color": "#80807F",
                "accent_color": "#2C2A29", "accent_text_color": "#FFFFFF", "accent_hover_color": "#1C1B1A",
                "accent_pressed_color": "#0C0C0B", "secondary_accent_color": "#545F6F", "secondary_text_color": "#FFFFFF",
                "success_color": "#3D7657", "warning_color": "#806742", "danger_color": "#9B5950",
                "focus_ring_color": "#7F7C7A", "disabled_surface_color": "#DEDDDD", "disabled_text_color": "#7E7D7D",
                "scrim_color": "rgba(0,0,0,0.5)",
            },
            "dark": {
                "color_scheme": "dark", "background_color": "#121111", "background_alt_color": "#313131",
                "panel_color": "#222221", "text_color": "#ECECEB", "text_soft_color": "#CBCBCA",
                "muted_text_color": "#9A9A99", "border_color": "#414141", "border_strong_color": "#7B7B7A",
                "accent_color": "#B8B3AE", "accent_text_color": "#121212", "accent_hover_color": "#C9C5C1",
                "accent_pressed_color": "#D9D7D4", "secondary_accent_color": "#8F9BAB", "secondary_text_color": "#121212",
                "success_color": "#478B66", "warning_color": "#987A4E", "danger_color": "#AF6C63",
                "focus_ring_color": "#807E7B", "disabled_surface_color": "#393939", "disabled_text_color": "#828281",
                "scrim_color": "rgba(0,0,0,0.66)",
            },
        },
    },
    "harbour-calm": {
        "label": "Harbour Calm", "label_zh": "静谧海港",
        "description": "Still-water blues in adjacent hues — clear, trustworthy, and quiet enough to read all day.",
        "description_zh": "静水一般的蓝，色相彼此相邻。清楚、可信，长时间阅读也不吵。",
        "mood": "clear, trustworthy",
        "harmony": "analogous",
        "modes": ['light', 'dark'],
        "themes": {
            "light": {
                "color_scheme": "light", "background_color": "#E9EFF3", "background_alt_color": "#DAE4EB",
                "panel_color": "#FDFDFD", "text_color": "#191E22", "text_soft_color": "#394148",
                "muted_text_color": "#59656E", "border_color": "#D5DBDF", "border_strong_color": "#6F8391",
                "accent_color": "#2E6892", "accent_text_color": "#FFFFFF", "accent_hover_color": "#27577B",
                "accent_pressed_color": "#1F4763", "secondary_accent_color": "#2B6E64", "secondary_text_color": "#FFFFFF",
                "success_color": "#297856", "warning_color": "#826726", "danger_color": "#BF3C3D",
                "focus_ring_color": "#3A82B7", "disabled_surface_color": "#D3DFE7", "disabled_text_color": "#757F87",
                "scrim_color": "rgba(0,0,0,0.5)",
            },
            "dark": {
                "color_scheme": "dark", "background_color": "#0D1216", "background_alt_color": "#27333B",
                "panel_color": "#1A2329", "text_color": "#EBEDEE", "text_soft_color": "#C8CCD0",
                "muted_text_color": "#929CA2", "border_color": "#37434B", "border_strong_color": "#6A7E8B",
                "accent_color": "#77ABCF", "accent_text_color": "#0F1215", "accent_hover_color": "#91BBD8",
                "accent_pressed_color": "#ACCCE2", "secondary_accent_color": "#4BB1A1", "secondary_text_color": "#0F1215",
                "success_color": "#348D67", "warning_color": "#997B30", "danger_color": "#C85C5D",
                "focus_ring_color": "#3B85B9", "disabled_surface_color": "#2D3B44", "disabled_text_color": "#79848B",
                "scrim_color": "rgba(0,0,0,0.66)",
            },
        },
    },
    "cedar-grove": {
        "label": "Cedar Grove", "label_zh": "雪松林",
        "description": "Cedar green against ochre in a triadic balance — the palette of the outdoors and the training ground.",
        "description_zh": "雪松绿配赭石黄，三分色的平衡。属于户外与训练场的配色。",
        "mood": "grounded, healthy, active",
        "harmony": "triadic",
        "modes": ['light', 'dark'],
        "themes": {
            "light": {
                "color_scheme": "light", "background_color": "#EBF2EE", "background_alt_color": "#DDE8E2",
                "panel_color": "#FDFDFD", "text_color": "#1B211E", "text_soft_color": "#3B443F",
                "muted_text_color": "#5B6861", "border_color": "#D7DEDA", "border_strong_color": "#71877C",
                "accent_color": "#377052", "accent_text_color": "#FFFFFF", "accent_hover_color": "#2D5B43",
                "accent_pressed_color": "#234734", "secondary_accent_color": "#885C30", "secondary_text_color": "#FFFFFF",
                "success_color": "#25513C", "warning_color": "#826833", "danger_color": "#A35644",
                "focus_ring_color": "#458C66", "disabled_surface_color": "#D7E4DD", "disabled_text_color": "#78837D",
                "scrim_color": "rgba(0,0,0,0.5)",
            },
            "dark": {
                "color_scheme": "dark", "background_color": "#0E1411", "background_alt_color": "#2A3831",
                "panel_color": "#1D2721", "text_color": "#F1F3F2", "text_soft_color": "#CCD2CF",
                "muted_text_color": "#96A19B", "border_color": "#3A4841", "border_strong_color": "#6E8478",
                "accent_color": "#6FB48F", "accent_text_color": "#101412", "accent_hover_color": "#86C0A1",
                "accent_pressed_color": "#9ECCB4", "secondary_accent_color": "#C6996B", "secondary_text_color": "#101412",
                "success_color": "#418D69", "warning_color": "#987B3E", "danger_color": "#B76B58",
                "focus_ring_color": "#479169", "disabled_surface_color": "#314139", "disabled_text_color": "#7E8A83",
                "scrim_color": "rgba(0,0,0,0.66)",
            },
        },
    },
    "recital-plum": {
        "label": "Recital Plum", "label_zh": "独奏紫",
        "description": "Stage-curtain plum with a neighbouring violet, for recitals, graded exams and performance.",
        "description_zh": "舞台幕布般的紫，衬以邻近的蓝紫。适合演出、考级与表演路线。",
        "mood": "refined, performative",
        "harmony": "analogous",
        "modes": ['light', 'dark'],
        "themes": {
            "light": {
                "color_scheme": "light", "background_color": "#F0EBF2", "background_alt_color": "#E6DCE9",
                "panel_color": "#FDFDFD", "text_color": "#1D191F", "text_soft_color": "#443B46",
                "muted_text_color": "#695E6D", "border_color": "#DCD6DE", "border_strong_color": "#8A7890",
                "accent_color": "#89469D", "accent_text_color": "#FFFFFF", "accent_hover_color": "#773D88",
                "accent_pressed_color": "#643373", "secondary_accent_color": "#5656B7", "secondary_text_color": "#FFFFFF",
                "success_color": "#32765C", "warning_color": "#8B6133", "danger_color": "#AE4944",
                "focus_ring_color": "#A360B8", "disabled_surface_color": "#E2D6E5", "disabled_text_color": "#827886",
                "scrim_color": "rgba(0,0,0,0.5)",
            },
            "dark": {
                "color_scheme": "dark", "background_color": "#130E15", "background_alt_color": "#352A38",
                "panel_color": "#251C27", "text_color": "#E9E6E9", "text_soft_color": "#CAC5CB",
                "muted_text_color": "#9C939F", "border_color": "#453A48", "border_strong_color": "#847189",
                "accent_color": "#C096CC", "accent_text_color": "#131014", "accent_hover_color": "#CEAED8",
                "accent_pressed_color": "#DDC6E3", "secondary_accent_color": "#9C9CD1", "secondary_text_color": "#131014",
                "success_color": "#3E8B6E", "warning_color": "#A47440", "danger_color": "#BD635E",
                "focus_ring_color": "#A361B8", "disabled_surface_color": "#3D3141", "disabled_text_color": "#857B88",
                "scrim_color": "rgba(0,0,0,0.66)",
            },
        },
    },
    "rehearsal-rose": {
        "label": "Rehearsal Rose", "label_zh": "排练玫瑰",
        "description": "Rehearsal-room rose against a moss green: kinetic without shouting.",
        "description_zh": "排练厅的玫红，配一抹苔绿。有动势，但不刺眼。",
        "mood": "expressive, warm, kinetic",
        "harmony": "split-complementary",
        "modes": ['light', 'dark'],
        "themes": {
            "light": {
                "color_scheme": "light", "background_color": "#F3EAED", "background_alt_color": "#EADBDF",
                "panel_color": "#FDFDFD", "text_color": "#20181A", "text_soft_color": "#473A3E",
                "muted_text_color": "#6E5D62", "border_color": "#DFD5D8", "border_strong_color": "#93767F",
                "accent_color": "#A23F5D", "accent_text_color": "#FFFFFF", "accent_hover_color": "#8C3650",
                "accent_pressed_color": "#762E44", "secondary_accent_color": "#336D44", "secondary_text_color": "#FFFFFF",
                "success_color": "#2E774D", "warning_color": "#8A622F", "danger_color": "#722F29",
                "focus_ring_color": "#BE5978", "disabled_surface_color": "#E6D5D9", "disabled_text_color": "#87777C",
                "scrim_color": "rgba(0,0,0,0.5)",
            },
            "dark": {
                "color_scheme": "dark", "background_color": "#150D10", "background_alt_color": "#3A282E",
                "panel_color": "#281B1F", "text_color": "#E8E5E6", "text_soft_color": "#CBC4C6",
                "muted_text_color": "#A09296", "border_color": "#4A383E", "border_strong_color": "#8C6F77",
                "accent_color": "#D193A5", "accent_text_color": "#140F11", "accent_hover_color": "#DCACBA",
                "accent_pressed_color": "#E6C5CF", "secondary_accent_color": "#61B077", "secondary_text_color": "#140F11",
                "success_color": "#398C5C", "warning_color": "#A2743A", "danger_color": "#C06158",
                "focus_ring_color": "#BE5977", "disabled_surface_color": "#432E35", "disabled_text_color": "#88797D",
                "scrim_color": "rgba(0,0,0,0.66)",
            },
        },
    },
    "arcade-lime": {
        "label": "Arcade Lime", "label_zh": "街机青柠",
        "description": "Arcade-screen lime, dark only: on a light page it turns olive and loses the reason it exists.",
        "description_zh": "街机屏幕上的荧光青柠，只做暗色——放到浅色底上会变成橄榄绿，失去存在的理由。",
        "mood": "digital, high energy",
        "harmony": "split-complementary",
        "modes": ['dark'],
        "themes": {
            "dark": {
                "color_scheme": "dark", "background_color": "#12180B", "background_alt_color": "#323F23",
                "panel_color": "#222C17", "text_color": "#FCFDFC", "text_soft_color": "#D7DBD4",
                "muted_text_color": "#A0A996", "border_color": "#424F33", "border_strong_color": "#788C60",
                "accent_color": "#75B926", "accent_text_color": "#12160E", "accent_hover_color": "#88D42F",
                "accent_pressed_color": "#99DA4C", "secondary_accent_color": "#AD97E2", "secondary_text_color": "#12160E",
                "success_color": "#29965F", "warning_color": "#AD7C28", "danger_color": "#D3624E",
                "focus_ring_color": "#5E991B", "disabled_surface_color": "#3A4928", "disabled_text_color": "#88937B",
                "scrim_color": "rgba(0,0,0,0.66)",
            },
        },
    },
}


# Every industry now points at a theme designed for it rather than borrowing
# one. Music no longer inherits the warm-brown editorial palette, and language
# gets its own analogous set instead of sharing dance's.
INDUSTRY_STYLE_RECOMMENDATIONS = {
    "art": "atelier-clay", "music": "recital-plum", "math": "harbour-calm",
    "dance": "rehearsal-rose", "language": "harbour-calm", "sports": "cedar-grove",
    "game": "arcade-lime", "general": "vintage-press",
}

# Shape is a presentation choice, not a palette choice, so it lives beside the
# theme rather than inside it — a studio can pick sharp buttons on any palette.
STYLE_SHAPE = {
    "atelier-clay":   {"button_style": "soft",    "font_mood": "serif"},
    "vintage-press":  {"button_style": "soft",    "font_mood": "serif"},
    "studio-ink":     {"button_style": "sharp",   "font_mood": "modern"},
    "harbour-calm":   {"button_style": "soft",    "font_mood": "modern"},
    "cedar-grove":    {"button_style": "soft",    "font_mood": "modern"},
    "recital-plum":   {"button_style": "rounded", "font_mood": "classic"},
    "rehearsal-rose": {"button_style": "rounded", "font_mood": "classic"},
    "arcade-lime":    {"button_style": "sharp",   "font_mood": "modern"},
}

DEFAULT_STYLE_ID = "vintage-press"

# 4-3: the API already reported which colour relationship a theme is built on,
# and nothing showed it. It is the single most useful fact for an owner choosing
# between eight palettes, so it needs a name a human reads rather than the
# generator's slug.
HARMONY_LABELS: dict[str, dict[str, str]] = {
    "split-complementary": {"zh": "分裂互补", "en": "Split-complementary"},
    "analogous": {"zh": "邻近色", "en": "Analogous"},
    "triadic": {"zh": "三分色", "en": "Triadic"},
    "neutral / monochrome": {"zh": "单色中性", "en": "Neutral / monochrome"},
}


def harmony_label(harmony: str) -> dict[str, str]:
    """Return the human-readable name of a colour relationship."""

    return dict(HARMONY_LABELS.get(harmony, {"zh": harmony, "en": harmony}))


def style_theme(style_id: str, scheme: str = "light") -> dict:
    """Return one style's flat token map for a given light/dark scheme.

    Falls back to the style's only available mode when the requested one does
    not exist (arcade-lime ships dark-only), and to the default style when the
    id is unknown, so a stale tenant setting can never render an empty theme.
    """

    preset = VISUAL_STYLE_PRESETS.get(style_id) or VISUAL_STYLE_PRESETS[DEFAULT_STYLE_ID]
    resolved_id = style_id if style_id in VISUAL_STYLE_PRESETS else DEFAULT_STYLE_ID
    themes = preset["themes"]
    mode = scheme if scheme in themes else preset["modes"][0]
    return {
        "style_id": resolved_id,
        "theme_mode": "preset",
        **STYLE_SHAPE.get(resolved_id, STYLE_SHAPE[DEFAULT_STYLE_ID]),
        **themes[mode],
    }


# B1: per-industry section copy. The template shipped one set of headings
# to every tenant, so five live studios all said 「总有一种，适合此刻的你」.
# A parent comparing two of them saw the same sentence twice.
INDUSTRY_SECTION_COPY: dict[str, dict] = {
    "art": {
        "courses_title": {"zh": "总有一种画法，适合此刻的你", "en": "There is a way of making that fits you now"},
        "courses_lead": {"zh": "从第一笔到完整作品，按你的节奏推进。", "en": "From a first mark to a finished piece, at your own pace."},
        "gallery_title": {"zh": "他们画出来的东西", "en": "What our students have made"},
        "gallery_lead": {"zh": "学员在这里完成的作品，经本人同意后展出。", "en": "Made here, shared with each student's consent."},
        "faq_title": {"zh": "动笔之前，先了解这些", "en": "Worth knowing before you start"},
    },
    "music": {
        "courses_title": {"zh": "总有一种节奏，适合此刻的你", "en": "There is a tempo that fits you now"},
        "courses_lead": {"zh": "从识谱到完整曲目，按你的节奏推进。", "en": "From reading notes to a finished piece, at your own pace."},
        "gallery_title": {"zh": "他们弹出来的声音", "en": "What our students have played"},
        "gallery_lead": {"zh": "学员的演奏与曲目记录，经本人同意后展出。", "en": "Recordings and repertoire, shared with each student's consent."},
        "faq_title": {"zh": "坐上琴凳之前，先了解这些", "en": "Worth knowing before the first lesson"},
    },
    "dance": {
        "courses_title": {"zh": "总有一支舞，适合此刻的你", "en": "There is a style that fits you now"},
        "courses_lead": {"zh": "从基本功到成套编排，按你的节奏推进。", "en": "From fundamentals to full choreography, at your own pace."},
        "gallery_title": {"zh": "他们跳出来的样子", "en": "What our dancers have performed"},
        "gallery_lead": {"zh": "课堂与演出的录像，经本人同意后展出。", "en": "Class and stage recordings, shared with each dancer's consent."},
        "faq_title": {"zh": "换上舞鞋之前，先了解这些", "en": "Worth knowing before the first class"},
    },
    "math": {
        "courses_title": {"zh": "总有一条路径，适合此刻的进度", "en": "There is a path that fits where you are now"},
        "courses_lead": {"zh": "先找准知识缺口，再按步骤补齐。", "en": "Find the gaps first, then close them step by step."},
        "gallery_title": {"zh": "他们的进步轨迹", "en": "How our learners have progressed"},
        "gallery_lead": {"zh": "阶段性练习与测评记录，经本人同意后展出。", "en": "Exercises and assessments, shared with each learner's consent."},
        "faq_title": {"zh": "开始补课之前，先了解这些", "en": "Worth knowing before you start"},
    },
    "language": {
        "courses_title": {"zh": "总有一种开口方式，适合此刻的你", "en": "There is a way in that fits you now"},
        "courses_lead": {"zh": "从日常表达到考试准备，按你的节奏推进。", "en": "From everyday conversation to exam prep, at your own pace."},
        "gallery_title": {"zh": "他们说出来的样子", "en": "How our learners are speaking now"},
        "gallery_lead": {"zh": "口语与作业记录，经本人同意后展出。", "en": "Speaking and coursework records, shared with each learner's consent."},
        "faq_title": {"zh": "开口之前，先了解这些", "en": "Worth knowing before you start"},
    },
    "sports": {
        "courses_title": {"zh": "总有一种训练，适合此刻的你", "en": "There is a programme that fits you now"},
        "courses_lead": {"zh": "从体能基础到比赛准备，按你的节奏推进。", "en": "From base fitness to competition, at your own pace."},
        "gallery_title": {"zh": "他们练出来的成绩", "en": "What our athletes have achieved"},
        "gallery_lead": {"zh": "训练与比赛记录，经本人同意后展出。", "en": "Training and competition records, shared with each athlete's consent."},
        "faq_title": {"zh": "开始训练之前，先了解这些", "en": "Worth knowing before your first session"},
    },
    "game": {
        "courses_title": {"zh": "总有一个方向，适合此刻的你", "en": "There is a track that fits you now"},
        "courses_lead": {"zh": "从上手到独立完成作品，按你的节奏推进。", "en": "From first build to shipping your own, at your own pace."},
        "gallery_title": {"zh": "他们做出来的东西", "en": "What our students have built"},
        "gallery_lead": {"zh": "学员完成的项目，经本人同意后展出。", "en": "Projects built here, shared with each student's consent."},
        "faq_title": {"zh": "开始之前，先了解这些", "en": "Worth knowing before you start"},
    },
    "general": {
        "courses_title": {"zh": "总有一种节奏，适合此刻的你", "en": "There is a pace that fits you now"},
        "courses_lead": {"zh": "从零基础到进阶，按你的节奏推进。", "en": "From first steps to advanced, at your own pace."},
        "gallery_title": {"zh": "他们完成的记录", "en": "What our students have made"},
        "gallery_lead": {"zh": "学员在这里完成的记录，经本人同意后展出。", "en": "Made here, shared with each student's consent."},
        "faq_title": {"zh": "开始之前，先了解这些", "en": "Worth knowing before you start"},
    },
}


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
        "slogan": "Create boldly. Grow visibly.", "slogan_zh": "大胆创作，让成长看得见。",
        "hero": {
            "title": {"zh": "让创意被看见，让成长有作品。", "en": "Create boldly. Grow visibly."},
            "subtitle": {"zh": "从兴趣启发到系统表达，记录每一次真实成长。", "en": "From first ideas to confident expression, make every stage of growth visible."},
        },
        "venue_noun": {"zh": "画室", "en": "studio"},
        "work_noun": {"zh": "作品", "en": "work", "en_plural": "works"},
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
        "slogan": "Find your rhythm. Make every practice count.", "slogan_zh": "找到自己的节奏，让每次练习都算数。",
        "hero": {"title": {"zh": "找到自己的节奏，让每次练习都有回应。", "en": "Find your rhythm. Make every practice count."}, "subtitle": {"zh": "清晰的目标、适合的节奏与看得见的音乐成长。", "en": "Clear goals, the right pace, and musical progress you can hear."}},
        "venue_noun": {"zh": "琴行", "en": "studio"},
        "work_noun": {"zh": "曲目", "en": "piece", "en_plural": "pieces"},
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
        "slogan": "Understand the method. Build lasting confidence.", "slogan_zh": "理解方法，建立长久的信心。",
        "hero": {"title": {"zh": "理解方法，建立信心，稳步进阶。", "en": "Understand the method. Build lasting confidence."}, "subtitle": {"zh": "找准知识缺口，用清晰方法建立可持续的学习能力。", "en": "Find the gaps, learn a clear method, and build skills that last."}},
        "venue_noun": {"zh": "教室", "en": "centre"},
        "work_noun": {"zh": "练习", "en": "exercise", "en_plural": "exercises"},
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
        "slogan": "Move with confidence. Grow through practice.", "slogan_zh": "自信地舞动，在训练中成长。",
        "hero": {"title": {"zh": "在节奏中表达，在训练中成长。", "en": "Move with confidence. Grow through practice."}, "subtitle": {"zh": "兼顾技术、体态与舞台表达，让每一步更自信。", "en": "Build technique, presence, and confidence in every movement."}},
        "venue_noun": {"zh": "舞蹈教室", "en": "studio"},
        "work_noun": {"zh": "舞蹈录像", "en": "recording", "en_plural": "recordings"},
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
        "slogan": "Find your voice. Connect with the world.", "slogan_zh": "开口表达，连接更大的世界。",
        "hero": {"title": {"zh": "开口表达，连接更大的世界。", "en": "Find your voice. Connect with the world."}, "subtitle": {"zh": "从真实沟通出发，建立能够长期使用的语言能力。", "en": "Build practical language skills through real communication."}},
        "venue_noun": {"zh": "教室", "en": "centre"},
        "work_noun": {"zh": "练习", "en": "exercise", "en_plural": "exercises"},
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
        "slogan": "Train with purpose. Grow stronger every session.", "slogan_zh": "有目标地训练，一次比一次更强。",
        "hero": {"title": {"zh": "有目标地训练，一次比一次更强。", "en": "Train with purpose. Grow stronger every session."}, "subtitle": {"zh": "科学训练、清晰反馈与持续进步。", "en": "Purposeful coaching, clear feedback, and steady progress."}},
        "venue_noun": {"zh": "训练中心", "en": "club"},
        "work_noun": {"zh": "训练记录", "en": "session record", "en_plural": "session records"},
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
        "slogan": "Play, think, create, and level up.", "slogan_zh": "在玩中思考、创造与升级。",
        "hero": {"title": {"zh": "在游戏中思考、创造与协作。", "en": "Play, think, create, and level up."}, "subtitle": {"zh": "把兴趣转化为策略、编程、创造力与团队能力。", "en": "Turn play into strategy, coding, creativity, and teamwork."}},
        "venue_noun": {"zh": "工作室", "en": "studio"},
        "work_noun": {"zh": "项目", "en": "project", "en_plural": "projects"},
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
        "slogan": "A learning path that fits every student.", "slogan_zh": "适合每个学员的成长路径。",
        "hero": {"title": {"zh": "适合每个学员的成长路径。", "en": "A learning path that fits every student."}, "subtitle": {"zh": "从兴趣和目标出发，在适合的节奏中稳步成长。", "en": "Start with the learner's interests and goals, then grow at the right pace."}},
        "venue_noun": {"zh": "工作室", "en": "studio"},
        "work_noun": {"zh": "作品", "en": "work", "en_plural": "works"},
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


def _operational_template(
    courses: list[tuple[str, str]],
    registration_focus: tuple[str, str],
    report_focus: tuple[str, str],
    demo_story: tuple[str, str],
) -> dict:
    """Build the client-safe operating layer for an industry preset.

    Industry presets must change the owner's starting workflow, not only colours
    and nouns. Keeping the bilingual values together also prevents one admin
    surface from drifting away from the public registration experience.
    """

    return {
        "starterCourses": [{"en": en, "zh": zh} for en, zh in courses],
        "registrationFocus": {"en": registration_focus[0], "zh": registration_focus[1]},
        "reportFocus": {"en": report_focus[0], "zh": report_focus[1]},
        "demoStory": {"en": demo_story[0], "zh": demo_story[1]},
    }


INDUSTRY_OPERATIONAL_TEMPLATES: dict[str, dict] = {
    "art": _operational_template(
        [("Foundation Art Lab", "基础艺术实验室"), ("Portfolio Studio", "作品集工作室"), ("Holiday Art Workshop", "假期艺术工作坊")],
        ("Medium, experience and creative goals", "媒介偏好、创作经验与目标"),
        ("Portfolio progress, attendance and credit runway", "作品进度、出勤与剩余课时"),
        ("Enquiry to trial, enrolment, class check-in and a parent-visible artwork", "从咨询、体验、报名、签到到家长可见作品"),
    ),
    "music": _operational_template(
        [("Piano Foundations", "钢琴基础"), ("AMEB Preparation", "AMEB 考级准备"), ("Student Recital Lab", "学员音乐会排练")],
        ("Instrument, grade and practice goals", "乐器、等级与练习目标"),
        ("Lesson continuity, repertoire and exam milestones", "连续上课、曲目与考级里程碑"),
        ("Trial lesson to recurring tuition, practice note and recital milestone", "从体验课到固定课、练习反馈与演出里程碑"),
    ),
    "math": _operational_template(
        [("Primary Foundations", "小学基础"), ("Secondary Problem Solving", "中学解题"), ("VCE Exam Clinic", "VCE 考试强化")],
        ("Year level, topic gaps and assessment dates", "年级、知识缺口与考试日期"),
        ("Attendance, topic coverage and renewal risk", "出勤、知识覆盖与续费风险"),
        ("Diagnostic enquiry to matched class, attendance and progress review", "从诊断咨询到匹配班级、出勤与阶段回顾"),
    ),
    "dance": _operational_template(
        [("Junior Ballet", "少儿芭蕾"), ("Jazz Technique", "爵士技巧"), ("Performance Company", "舞台表演团")],
        ("Age, style, level and performance goal", "年龄、舞种、水平与演出目标"),
        ("Roster capacity, attendance and performance readiness", "班级容量、出勤与演出准备度"),
        ("Trial class to troupe placement, rehearsal attendance and showcase media", "从体验课到分班、排练出勤与汇演影像"),
    ),
    "language": _operational_template(
        [("Everyday Conversation", "日常会话"), ("School Language Support", "校内语言辅导"), ("Exam Speaking Lab", "口语考试训练")],
        ("Target language, level and real-life use", "目标语言、水平与真实使用场景"),
        ("Attendance, level progression and speaking evidence", "出勤、等级进展与口语成果"),
        ("Placement enquiry to small group, speaking task and family update", "从水平咨询到小班、口语任务与家庭反馈"),
    ),
    "sports": _operational_template(
        [("Junior Skills", "少儿技能课"), ("Squad Training", "队伍训练"), ("Competition Clinic", "赛前强化")],
        ("Sport, level, health notes and competition goal", "项目、水平、健康备注与比赛目标"),
        ("Capacity, attendance and coaching milestones", "容量、出勤与训练里程碑"),
        ("Assessment to squad placement, session record and coaching feedback", "从评估到分队、训练记录与教练反馈"),
    ),
    "game": _operational_template(
        [("Minecraft Makers", "Minecraft 创造营"), ("Roblox Coding Lab", "Roblox 编程实验室"), ("Strategy Club", "策略俱乐部")],
        ("Platform, experience and learning objective", "平台、经验与学习目标"),
        ("Project completion, attendance and collaboration", "项目完成度、出勤与协作表现"),
        ("Interest enquiry to project cohort, attendance and shareable project", "从兴趣咨询到项目小组、出勤与可分享项目"),
    ),
    "general": _operational_template(
        [("Foundation Program", "基础课程"), ("Skills Development", "技能进阶"), ("Holiday Workshop", "假期工作坊")],
        ("Interests, experience and learning goals", "兴趣、经验与学习目标"),
        ("Enquiry conversion, attendance and credit runway", "咨询转化、出勤与剩余课时"),
        ("Enquiry to trial, enrolment, attendance and family progress update", "从咨询、体验、报名、出勤到家庭进度反馈"),
    ),
}

# Keep industry copy and visual design independent. The industry provides the
# recommended starting style; tenants can switch style without changing copy.
for _industry_key, _style_id in INDUSTRY_STYLE_RECOMMENDATIONS.items():
    INDUSTRY_PRESETS[_industry_key]["recommended_style_id"] = _style_id
    INDUSTRY_PRESETS[_industry_key]["theme"] = style_theme(_style_id)
    INDUSTRY_PRESETS[_industry_key]["operational_template"] = INDUSTRY_OPERATIONAL_TEMPLATES[_industry_key]


def public_industry_presets() -> dict[str, dict]:
    """Return the client-safe preset shape used by both admin surfaces."""

    result: dict[str, dict] = {}
    for key, preset in INDUSTRY_PRESETS.items():
        result[key] = {
            "label": preset["label"],
            "labelZh": preset["label_zh"],
            "layout": preset["layout"],
            "slogan": preset["slogan"],
            "sloganZh": preset["slogan_zh"],
            "recommendedStyleId": preset["recommended_style_id"],
            "portalLabel": preset["copy_pack"]["portal_label"],
            "registerIntro": preset["copy_pack"]["register_intro"],
            "registerIntroZh": preset["register_intro_zh"],
            "registrationTitle": preset["registration_title"],
            "registrationTitleZh": preset["registration_title_zh"],
            # The public pages substitute these into %VENUE% / %WORK% / %WORKS%.
            # Without them the shared template calls every tenant a 画室 with
            # 作品, which is wrong for the piano, dance and game studios.
            "venueNoun": dict(preset["venue_noun"]),
            "workNoun": dict(preset["work_noun"]),
            "localizedCopy": {
                "hero_title": preset["hero"]["title"],
                "hero_subtitle": preset["hero"]["subtitle"],
                "primary_cta": {"zh": "预约体验", "en": "Book a Trial"},
                "secondary_cta": {"zh": "查看课程", "en": "Explore Programs"},
                "registration_title": {"zh": preset["registration_title_zh"], "en": preset["registration_title"]},
                "registration_intro": {"zh": preset["register_intro_zh"], "en": preset["copy_pack"]["register_intro"]},
                **INDUSTRY_SECTION_COPY.get(key, INDUSTRY_SECTION_COPY["general"]),
            },
            "visualTheme": dict(preset["theme"]),
            "registrationProfile": {"title": preset["registration_title"], "fields": [dict(field) for field in preset["fields"]]},
            "operationalTemplate": dict(preset["operational_template"]),
        }
    return result


def public_visual_style_presets() -> dict[str, dict]:
    """Return curated, client-safe visual styles with both scheme variants."""

    result: dict[str, dict] = {}
    for key, preset in VISUAL_STYLE_PRESETS.items():
        result[key] = {
            "label": preset["label"],
            "labelZh": preset["label_zh"],
            # 2-2: both languages ship, so the panel is not left translating an
            # English sentence through the admin dictionary at render time.
            "description": preset["description"],
            "descriptionZh": preset["description_zh"],
            "mood": preset["mood"],
            "harmony": preset["harmony"],
            "harmonyLabel": harmony_label(preset["harmony"]),
            "modes": list(preset["modes"]),
            # The editor needs both variants so it can preview a scheme switch
            # without another round trip.
            "schemes": {mode: style_theme(key, mode) for mode in preset["modes"]},
            "visualTheme": style_theme(key, preset["modes"][0]),
        }
    return result

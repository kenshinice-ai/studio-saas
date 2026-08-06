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
                "panel_color": "#FDFDFD", "surface_hover_color": "#F7F6F6", "text_color": "#211B19",
                "text_soft_color": "#473D3A", "muted_text_color": "#6E605C", "border_color": "#DFD8D5",
                "border_strong_color": "#917A72", "accent_color": "#955037", "accent_text_color": "#FFFFFF",
                "accent_muted_text_color": "#E4E0DF", "accent_hover_color": "#7F442F", "accent_pressed_color": "#683826",
                "accent_soft_color": "#EEE4E1", "accent_on_soft_color": "#955037", "accent_border_color": "#D5BBB2",
                "secondary_accent_color": "#3F6B61", "secondary_text_color": "#FFFFFF", "secondary_soft_color": "#E2E8E6",
                "secondary_on_soft_color": "#3F6B61", "secondary_border_color": "#B4C4C0", "success_color": "#2D784E",
                "success_soft_color": "#DFE9E3", "success_on_soft_color": "#2C754C", "success_border_color": "#AAC8B7",
                "warning_color": "#5A411D", "warning_soft_color": "#E9E6E2", "warning_on_soft_color": "#5A411D",
                "warning_border_color": "#C8BFB4", "danger_color": "#753129", "danger_soft_color": "#EDE4E4",
                "danger_on_soft_color": "#753129", "danger_border_color": "#D2BBBA", "info_color": "#4168B0",
                "info_soft_color": "#E1E7F2", "info_on_soft_color": "#4066AD", "info_border_color": "#B2C1DF",
                "focus_ring_color": "#BA6445", "disabled_surface_color": "#E6D9D5", "disabled_text_color": "#867A76",
                "scrim_color": "rgba(0,0,0,0.5)",
            },
            "dark": {
                "color_scheme": "dark", "background_color": "#150F0D", "background_alt_color": "#201715",
                "panel_color": "#372A25", "surface_hover_color": "#3B2F2A", "text_color": "#E8E5E3",
                "text_soft_color": "#CAC4C1", "muted_text_color": "#9E938E", "border_color": "#4A3D38",
                "border_strong_color": "#87726A", "accent_color": "#CE9985", "accent_text_color": "#14110F",
                "accent_muted_text_color": "#403836", "accent_hover_color": "#D8AE9E", "accent_pressed_color": "#E2C4B8",
                "accent_soft_color": "#483730", "accent_on_soft_color": "#CE9985", "accent_border_color": "#664D43",
                "secondary_accent_color": "#75AB9E", "secondary_text_color": "#14110F", "secondary_soft_color": "#3E3A34",
                "secondary_on_soft_color": "#79AEA1", "secondary_border_color": "#4B554D", "success_color": "#388D5E",
                "success_soft_color": "#373D30", "success_on_soft_color": "#4BB87B", "success_border_color": "#375B41",
                "warning_color": "#A07537", "warning_soft_color": "#493728", "warning_on_soft_color": "#C89C5E",
                "warning_border_color": "#694D2D", "danger_color": "#C16155", "danger_soft_color": "#4F342D",
                "danger_on_soft_color": "#D5948B", "danger_border_color": "#79443C", "info_color": "#5A7EBF",
                "info_soft_color": "#3D3940", "info_on_soft_color": "#8BA5D2", "info_border_color": "#47526D",
                "focus_ring_color": "#B76344", "disabled_surface_color": "#291E1B", "disabled_text_color": "#736865",
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
                "panel_color": "#FDFDFD", "surface_hover_color": "#F7F6F6", "text_color": "#221E1A",
                "text_soft_color": "#46403A", "muted_text_color": "#6C635A", "border_color": "#DFDAD5",
                "border_strong_color": "#8D7F70", "accent_color": "#835D33", "accent_text_color": "#FFFFFF",
                "accent_muted_text_color": "#E6E4E1", "accent_hover_color": "#6D4D2A", "accent_pressed_color": "#573E22",
                "accent_soft_color": "#EBE6DF", "accent_on_soft_color": "#835D33", "accent_border_color": "#CDBFAE",
                "secondary_accent_color": "#4C6877", "secondary_text_color": "#FFFFFF", "secondary_soft_color": "#E3E7EA",
                "secondary_on_soft_color": "#4C6877", "secondary_border_color": "#B8C2C9", "success_color": "#2F7951",
                "success_soft_color": "#DFE9E4", "success_on_soft_color": "#2D744E", "success_border_color": "#AAC8B8",
                "warning_color": "#5B421F", "warning_soft_color": "#EAE6E2", "warning_on_soft_color": "#5B421F",
                "warning_border_color": "#C8C0B4", "danger_color": "#76332A", "danger_soft_color": "#EDE5E3",
                "danger_on_soft_color": "#76332A", "danger_border_color": "#D2BCB9", "info_color": "#396F95",
                "info_soft_color": "#DFE8ED", "info_on_soft_color": "#386C92", "info_border_color": "#AEC4D3",
                "focus_ring_color": "#A3743F", "disabled_surface_color": "#E6DED5", "disabled_text_color": "#857E76",
                "scrim_color": "rgba(0,0,0,0.5)",
            },
            "dark": {
                "color_scheme": "dark", "background_color": "#15120D", "background_alt_color": "#1F1A15",
                "panel_color": "#362D24", "surface_hover_color": "#3A3129", "text_color": "#E9E8E6",
                "text_soft_color": "#CAC7C3", "muted_text_color": "#9C968E", "border_color": "#4A4238",
                "border_strong_color": "#837668", "accent_color": "#C49F74", "accent_text_color": "#14120F",
                "accent_muted_text_color": "#3E3935", "accent_hover_color": "#CFB08D", "accent_pressed_color": "#D9C2A6",
                "accent_soft_color": "#463A2D", "accent_on_soft_color": "#C4A075", "accent_border_color": "#62513D",
                "secondary_accent_color": "#8AA5B2", "secondary_text_color": "#14120F", "secondary_soft_color": "#403C35",
                "secondary_on_soft_color": "#91AAB6", "secondary_border_color": "#525553", "success_color": "#3A8E60",
                "success_soft_color": "#373F2F", "success_on_soft_color": "#52B981", "success_border_color": "#385D41",
                "warning_color": "#A07739", "warning_soft_color": "#483A28", "warning_on_soft_color": "#C7A063",
                "warning_border_color": "#68502E", "danger_color": "#C06559", "danger_soft_color": "#4E372D",
                "danger_on_soft_color": "#D4978E", "danger_border_color": "#77483D", "info_color": "#4684AF",
                "info_soft_color": "#393D3D", "info_on_soft_color": "#7EACCB", "info_border_color": "#3E5768",
                "focus_ring_color": "#A0733E", "disabled_surface_color": "#28221B", "disabled_text_color": "#726C64",
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
                "panel_color": "#FDFDFD", "surface_hover_color": "#F7F6F6", "text_color": "#1E1D1D",
                "text_soft_color": "#404040", "muted_text_color": "#646363", "border_color": "#DADADA",
                "border_strong_color": "#80807F", "accent_color": "#2C2A29", "accent_text_color": "#FFFFFF",
                "accent_muted_text_color": "#939292", "accent_hover_color": "#1C1B1A", "accent_pressed_color": "#0C0C0B",
                "accent_soft_color": "#E7E6E6", "accent_on_soft_color": "#2C2A29", "accent_border_color": "#C2C0C0",
                "secondary_accent_color": "#545F6F", "secondary_text_color": "#FFFFFF", "secondary_soft_color": "#E5E6E9",
                "secondary_on_soft_color": "#545F6F", "secondary_border_color": "#BDC0C7", "success_color": "#3D7657",
                "success_soft_color": "#E0E8E4", "success_on_soft_color": "#3B7254", "success_border_color": "#AFC6B9",
                "warning_color": "#806742", "warning_soft_color": "#EAE6E1", "warning_on_soft_color": "#7C6440",
                "warning_border_color": "#CABFB1", "danger_color": "#9B5950", "danger_soft_color": "#EEE4E3",
                "danger_on_soft_color": "#96564E", "danger_border_color": "#D5BAB7", "info_color": "#506A9B",
                "info_soft_color": "#E3E6EE", "info_on_soft_color": "#4E6797", "info_border_color": "#B7C0D5",
                "focus_ring_color": "#7F7C7A", "disabled_surface_color": "#DEDDDD", "disabled_text_color": "#7E7D7D",
                "scrim_color": "rgba(0,0,0,0.5)",
            },
            "dark": {
                "color_scheme": "dark", "background_color": "#121111", "background_alt_color": "#1A1A1A",
                "panel_color": "#2E2E2D", "surface_hover_color": "#333232", "text_color": "#E8E7E7",
                "text_soft_color": "#C7C7C6", "muted_text_color": "#979696", "border_color": "#414141",
                "border_strong_color": "#787877", "accent_color": "#B8B3AE", "accent_text_color": "#121212",
                "accent_muted_text_color": "#454545", "accent_hover_color": "#C9C5C1", "accent_pressed_color": "#D9D7D4",
                "accent_soft_color": "#3C3C3A", "accent_on_soft_color": "#B8B3AE", "accent_border_color": "#545451",
                "secondary_accent_color": "#8F9BAB", "secondary_text_color": "#121212", "secondary_soft_color": "#3A3C3D",
                "secondary_on_soft_color": "#9CA6B4", "secondary_border_color": "#505459", "success_color": "#478B66",
                "success_soft_color": "#323F37", "success_on_soft_color": "#6DB48D", "success_border_color": "#3A5B48",
                "warning_color": "#987A4E", "warning_soft_color": "#403B32", "warning_on_soft_color": "#BBA27B",
                "warning_border_color": "#5F523C", "danger_color": "#AF6C63", "danger_soft_color": "#453936",
                "danger_on_soft_color": "#C89B94", "danger_border_color": "#6B4C46", "info_color": "#637EAF",
                "info_soft_color": "#373C43", "info_on_soft_color": "#93A6C7", "info_border_color": "#47546A",
                "focus_ring_color": "#7D7B78", "disabled_surface_color": "#222222", "disabled_text_color": "#6C6C6B",
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
                "panel_color": "#FDFDFD", "surface_hover_color": "#F6F6F7", "text_color": "#191E22",
                "text_soft_color": "#394148", "muted_text_color": "#59656E", "border_color": "#D5DBDF",
                "border_strong_color": "#6F8391", "accent_color": "#2E6892", "accent_text_color": "#FFFFFF",
                "accent_muted_text_color": "#DFE3E5", "accent_hover_color": "#27577B", "accent_pressed_color": "#1F4763",
                "accent_soft_color": "#DFE8EE", "accent_on_soft_color": "#2E6892", "accent_border_color": "#AEC4D4",
                "secondary_accent_color": "#2B6E64", "secondary_text_color": "#FFFFFF", "secondary_soft_color": "#DFE8E7",
                "secondary_on_soft_color": "#2B6E64", "secondary_border_color": "#ACC5C2", "success_color": "#297856",
                "success_soft_color": "#DEE9E5", "success_on_soft_color": "#287453", "success_border_color": "#A8C8BB",
                "warning_color": "#826726", "warning_soft_color": "#EBE6DD", "warning_on_soft_color": "#7F6425",
                "warning_border_color": "#CBC0A6", "danger_color": "#BF3C3D", "danger_soft_color": "#F4E2E3",
                "danger_on_soft_color": "#B93A3B", "danger_border_color": "#E5B4B5", "info_color": "#25476E",
                "info_soft_color": "#E3E7EC", "info_on_soft_color": "#25476E", "info_border_color": "#B8C2CF",
                "focus_ring_color": "#3A82B7", "disabled_surface_color": "#D3DFE7", "disabled_text_color": "#757F87",
                "scrim_color": "rgba(0,0,0,0.5)",
            },
            "dark": {
                "color_scheme": "dark", "background_color": "#0D1216", "background_alt_color": "#141B20",
                "panel_color": "#233038", "surface_hover_color": "#28343C", "text_color": "#E6E8EA",
                "text_soft_color": "#C2C8CB", "muted_text_color": "#8E989F", "border_color": "#37434B",
                "border_strong_color": "#687B88", "accent_color": "#77ABCF", "accent_text_color": "#0F1215",
                "accent_muted_text_color": "#353B3F", "accent_hover_color": "#91BBD8", "accent_pressed_color": "#ACCCE2",
                "accent_soft_color": "#2D3E49", "accent_on_soft_color": "#78ACCF", "accent_border_color": "#3E5767",
                "secondary_accent_color": "#4BB1A1", "secondary_text_color": "#0F1215", "secondary_soft_color": "#284045",
                "secondary_on_soft_color": "#52B6A6", "secondary_border_color": "#305B5B", "success_color": "#348D67",
                "success_soft_color": "#264140", "success_on_soft_color": "#44BA88", "success_border_color": "#2B5D4E",
                "warning_color": "#997B30", "warning_soft_color": "#383E37", "warning_on_soft_color": "#C5A248",
                "warning_border_color": "#5C5534", "danger_color": "#C85C5D", "danger_soft_color": "#43393F",
                "danger_on_soft_color": "#DA9393", "danger_border_color": "#76474B", "info_color": "#4A81BE",
                "info_soft_color": "#2A3E4E", "info_on_soft_color": "#83A9D2", "info_border_color": "#365677",
                "focus_ring_color": "#3981B4", "disabled_surface_color": "#1A2329", "disabled_text_color": "#636D73",
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
                "panel_color": "#FDFDFD", "surface_hover_color": "#F6F6F6", "text_color": "#1B211E",
                "text_soft_color": "#3B443F", "muted_text_color": "#5B6861", "border_color": "#D7DEDA",
                "border_strong_color": "#71877C", "accent_color": "#377052", "accent_text_color": "#FFFFFF",
                "accent_muted_text_color": "#E2E6E4", "accent_hover_color": "#2D5B43", "accent_pressed_color": "#234734",
                "accent_soft_color": "#E0E8E4", "accent_on_soft_color": "#377052", "accent_border_color": "#AFC5BA",
                "secondary_accent_color": "#885C30", "secondary_text_color": "#FFFFFF", "secondary_soft_color": "#ECE5DF",
                "secondary_on_soft_color": "#885C30", "secondary_border_color": "#CFBDAD", "success_color": "#25513C",
                "success_soft_color": "#E2E8E5", "success_on_soft_color": "#25513C", "success_border_color": "#B6C4BD",
                "warning_color": "#826833", "warning_soft_color": "#EAE6DE", "warning_on_soft_color": "#7D6431",
                "warning_border_color": "#CAC0AA", "danger_color": "#A35644", "danger_soft_color": "#F0E4E2",
                "danger_on_soft_color": "#9D5342", "danger_border_color": "#D9BAB4", "info_color": "#436F98",
                "info_soft_color": "#E1E7EE", "info_on_soft_color": "#416B92", "info_border_color": "#B1C3D4",
                "focus_ring_color": "#458C66", "disabled_surface_color": "#D7E4DD", "disabled_text_color": "#78837D",
                "scrim_color": "rgba(0,0,0,0.5)",
            },
            "dark": {
                "color_scheme": "dark", "background_color": "#0E1411", "background_alt_color": "#161E1A",
                "panel_color": "#26342C", "surface_hover_color": "#2A3830", "text_color": "#EAEDEB",
                "text_soft_color": "#C6CCC9", "muted_text_color": "#919D96", "border_color": "#3A4841",
                "border_strong_color": "#6B7F74", "accent_color": "#6FB48F", "accent_text_color": "#101412",
                "accent_muted_text_color": "#363C39", "accent_hover_color": "#86C0A1", "accent_pressed_color": "#9ECCB4",
                "accent_soft_color": "#2E4337", "accent_on_soft_color": "#74B793", "accent_border_color": "#3D5D4B",
                "secondary_accent_color": "#C6996B", "secondary_text_color": "#101412", "secondary_soft_color": "#3A4134",
                "secondary_on_soft_color": "#CBA277", "secondary_border_color": "#5C5741", "success_color": "#418D69",
                "success_soft_color": "#2B4437", "success_on_soft_color": "#67B992", "success_border_color": "#33604A",
                "warning_color": "#987B3E", "warning_soft_color": "#3A412F", "warning_on_soft_color": "#C2A66A",
                "warning_border_color": "#5D5735", "danger_color": "#B76B58", "danger_soft_color": "#423E34",
                "danger_on_soft_color": "#CF9D90", "danger_border_color": "#6E4F41", "info_color": "#5382B0",
                "info_soft_color": "#2E4243", "info_on_soft_color": "#8DACCB", "info_border_color": "#3C5A6B",
                "focus_ring_color": "#458C66", "disabled_surface_color": "#1C2722", "disabled_text_color": "#66706A",
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
                "panel_color": "#FDFDFD", "surface_hover_color": "#F6F6F7", "text_color": "#1D191F",
                "text_soft_color": "#443B46", "muted_text_color": "#695E6D", "border_color": "#DCD6DE",
                "border_strong_color": "#8A7890", "accent_color": "#89469D", "accent_text_color": "#FFFFFF",
                "accent_muted_text_color": "#E2DEE2", "accent_hover_color": "#773D88", "accent_pressed_color": "#643373",
                "accent_soft_color": "#EDE3F0", "accent_on_soft_color": "#89469D", "accent_border_color": "#D2B8DA",
                "secondary_accent_color": "#5656B7", "secondary_text_color": "#FFFFFF", "secondary_soft_color": "#E5E5F3",
                "secondary_on_soft_color": "#5656B7", "secondary_border_color": "#BDBDE2", "success_color": "#32765C",
                "success_soft_color": "#DEE9E5", "success_on_soft_color": "#31735A", "success_border_color": "#ABC7BD",
                "warning_color": "#8B6133", "warning_soft_color": "#ECE5DF", "warning_on_soft_color": "#885F32",
                "warning_border_color": "#CFBDAC", "danger_color": "#AE4944", "danger_soft_color": "#F2E3E3",
                "danger_on_soft_color": "#AB4843", "danger_border_color": "#DFB7B6", "info_color": "#436AA2",
                "info_soft_color": "#E1E7F0", "info_on_soft_color": "#4268A0", "info_border_color": "#B3C2D9",
                "focus_ring_color": "#A360B8", "disabled_surface_color": "#E2D6E5", "disabled_text_color": "#827886",
                "scrim_color": "rgba(0,0,0,0.5)",
            },
            "dark": {
                "color_scheme": "dark", "background_color": "#130E15", "background_alt_color": "#1C151F",
                "panel_color": "#322736", "surface_hover_color": "#362C3A", "text_color": "#E4E2E5",
                "text_soft_color": "#C6C1C8", "muted_text_color": "#99909C", "border_color": "#453A48",
                "border_strong_color": "#816E87", "accent_color": "#C096CC", "accent_text_color": "#131014",
                "accent_muted_text_color": "#3E3740", "accent_hover_color": "#CEAED8", "accent_pressed_color": "#DDC6E3",
                "accent_soft_color": "#423447", "accent_on_soft_color": "#C096CC", "accent_border_color": "#5E4A64",
                "secondary_accent_color": "#9C9CD1", "secondary_text_color": "#131014", "secondary_soft_color": "#3E3548",
                "secondary_on_soft_color": "#9D9DD1", "secondary_border_color": "#534D67", "success_color": "#3E8B6E",
                "success_soft_color": "#343940", "success_on_soft_color": "#53B28E", "success_border_color": "#385651",
                "warning_color": "#A47440", "warning_soft_color": "#463438", "warning_on_soft_color": "#C59A6A",
                "warning_border_color": "#674B3B", "danger_color": "#BD635E", "danger_soft_color": "#4A323D",
                "danger_on_soft_color": "#D1928E", "danger_border_color": "#734449", "info_color": "#577FB6",
                "info_soft_color": "#39364C", "info_on_soft_color": "#87A3CB", "info_border_color": "#435071",
                "focus_ring_color": "#A15DB6", "disabled_surface_color": "#241B28", "disabled_text_color": "#6E6671",
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
                "panel_color": "#FDFDFD", "surface_hover_color": "#F7F6F6", "text_color": "#20181A",
                "text_soft_color": "#473A3E", "muted_text_color": "#6E5D62", "border_color": "#DFD5D8",
                "border_strong_color": "#93767F", "accent_color": "#A23F5D", "accent_text_color": "#FFFFFF",
                "accent_muted_text_color": "#E2DEDF", "accent_hover_color": "#8C3650", "accent_pressed_color": "#762E44",
                "accent_soft_color": "#F1E3E8", "accent_on_soft_color": "#A23F5D", "accent_border_color": "#DCB7C3",
                "secondary_accent_color": "#336D44", "secondary_text_color": "#FFFFFF", "secondary_soft_color": "#E0E8E3",
                "secondary_on_soft_color": "#336D44", "secondary_border_color": "#B0C6B6", "success_color": "#2E774D",
                "success_soft_color": "#DFE9E3", "success_on_soft_color": "#2D744B", "success_border_color": "#ABC7B7",
                "warning_color": "#8A622F", "warning_soft_color": "#ECE5DE", "warning_on_soft_color": "#86602E",
                "warning_border_color": "#CFBEAA", "danger_color": "#722F29", "danger_soft_color": "#ECE5E4",
                "danger_on_soft_color": "#722F29", "danger_border_color": "#D1BCBA", "info_color": "#4169AB",
                "info_soft_color": "#E1E7F1", "info_on_soft_color": "#4067A9", "info_border_color": "#B2C2DD",
                "focus_ring_color": "#BE5978", "disabled_surface_color": "#E6D5D9", "disabled_text_color": "#87777C",
                "scrim_color": "rgba(0,0,0,0.5)",
            },
            "dark": {
                "color_scheme": "dark", "background_color": "#150D10", "background_alt_color": "#1F1518",
                "panel_color": "#38262B", "surface_hover_color": "#3C2B2F", "text_color": "#E6E2E3",
                "text_soft_color": "#C9C1C3", "muted_text_color": "#9E8F94", "border_color": "#4A383E",
                "border_strong_color": "#8A6D76", "accent_color": "#D193A5", "accent_text_color": "#140F11",
                "accent_muted_text_color": "#40373A", "accent_hover_color": "#DCACBA", "accent_pressed_color": "#E6C5CF",
                "accent_soft_color": "#4A3239", "accent_on_soft_color": "#D193A5", "accent_border_color": "#684851",
                "secondary_accent_color": "#61B077", "secondary_text_color": "#140F11", "secondary_soft_color": "#3D3835",
                "secondary_on_soft_color": "#64B27A", "secondary_border_color": "#465545", "success_color": "#398C5C",
                "success_soft_color": "#383A34", "success_on_soft_color": "#4AB678", "success_border_color": "#385843",
                "warning_color": "#A2743A", "warning_soft_color": "#4A342E", "warning_on_soft_color": "#C79A61",
                "warning_border_color": "#694B32", "danger_color": "#C06158", "danger_soft_color": "#503033",
                "danger_on_soft_color": "#D3918A", "danger_border_color": "#784140", "info_color": "#587EBC",
                "info_soft_color": "#3E3645", "info_on_soft_color": "#88A3CF", "info_border_color": "#47506F",
                "focus_ring_color": "#BD5675", "disabled_surface_color": "#281B1F", "disabled_text_color": "#736669",
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
                "color_scheme": "dark", "background_color": "#12180B", "background_alt_color": "#1B2311",
                "panel_color": "#2C391D", "surface_hover_color": "#303D21", "text_color": "#F1F3F0",
                "text_soft_color": "#CED2C9", "muted_text_color": "#98A28D", "border_color": "#424F33",
                "border_strong_color": "#72855B", "accent_color": "#75B926", "accent_text_color": "#12160E",
                "accent_muted_text_color": "#373E30", "accent_hover_color": "#88D42F", "accent_pressed_color": "#99DA4C",
                "accent_soft_color": "#34481E", "accent_on_soft_color": "#7AC128", "accent_border_color": "#436320",
                "secondary_accent_color": "#AD97E2", "secondary_text_color": "#12160E", "secondary_soft_color": "#3C4535",
                "secondary_on_soft_color": "#B7A4E5", "secondary_border_color": "#585A60", "success_color": "#28925C",
                "success_soft_color": "#2B4928", "success_on_soft_color": "#36C57C", "success_border_color": "#2A663C",
                "warning_color": "#A77826", "warning_soft_color": "#42451F", "warning_on_soft_color": "#D7A651",
                "warning_border_color": "#695922", "danger_color": "#D25D47", "danger_soft_color": "#4F4026",
                "danger_on_soft_color": "#E49C8F", "danger_border_color": "#834C33", "info_color": "#3687C9",
                "info_soft_color": "#2E483D", "info_on_soft_color": "#81B4DD", "info_border_color": "#316173",
                "focus_ring_color": "#59911A", "disabled_surface_color": "#232D16", "disabled_text_color": "#6C7660",
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
        # `title` is filled in below from the slogan — do not write it here.
        "hero": {
            "subtitle": {"zh": "从兴趣启发到系统表达，记录每一次真实成长。", "en": "From first ideas to confident expression, make every stage of growth visible."},
        },
        "venue_noun": {"zh": "画室", "en": "studio"},
        "work_noun": {"zh": "作品", "en": "work", "en_plural": "works"},
        "registration_title": "Tell us how they like to create",
        "registration_title_zh": "告诉我们学员喜欢怎样创作",
        "copy_pack": {"portal_label": "Art Student Portal", "register_intro": "Three questions about style, experience and goals, then the studio will suggest a class and a time."},
        "register_intro_zh": "三个关于创作形式、经验与目标的问题，之后画室会推荐合适的课程与时间。",
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
        "hero": {"subtitle": {"zh": "清晰的目标、适合的节奏与看得见的音乐成长。", "en": "Clear goals, the right pace, and musical progress you can hear."}},
        "venue_noun": {"zh": "琴行", "en": "studio"},
        "work_noun": {"zh": "曲目", "en": "piece", "en_plural": "pieces"},
        "registration_title": "Tell us what they want to play", "registration_title_zh": "告诉我们学员想学什么乐器",
        "copy_pack": {"portal_label": "Music Student Portal", "register_intro": "The instrument, the current level and the goal, then the studio will match a teacher and a lesson time."},
        "register_intro_zh": "乐器、当前水平与音乐目标，之后琴行会匹配合适的老师与上课时间。",
        "theme": {"background_color": "#F7F5FF", "panel_color": "#FFFFFF", "text_color": "#201A35", "accent_color": "#5B3FA8", "secondary_accent_color": "#1F2A44", "button_style": "soft", "font_mood": "classic"},
        "fields": [
            _field("instrument", "Instrument", "乐器或声乐", "Piano, guitar, violin, voice", "钢琴、吉他、小提琴、声乐等"),
            _field("level", "Current level", "当前水平", "Beginner, AMEB Grade 2, self-taught", "零基础、考级程度、自学经验"),
            _field("goals", "Music goals", "音乐目标", "Exam prep, performance, confidence", "考级、演出、兴趣或自信表达"),
        ],
    },
    "math": {
        # `label` is display only — the category key stays "math". Australian
        # spelling, like the rest of the product's copy.
        "label": "Maths", "label_zh": "数学", "layout": "structured",
        "slogan": "Understand the method. Build lasting confidence.", "slogan_zh": "理解方法，建立长久的信心。",
        "hero": {"subtitle": {"zh": "找准知识缺口，用清晰方法建立可持续的学习能力。", "en": "Find the gaps, learn a clear method, and build skills that last."}},
        "venue_noun": {"zh": "教室", "en": "centre"},
        "work_noun": {"zh": "练习", "en": "exercise", "en_plural": "exercises"},
        "registration_title": "Tell us where they are and what is hard", "registration_title_zh": "告诉我们目前的学习阶段与难点",
        "copy_pack": {"portal_label": "Maths Student Portal", "register_intro": "Year level, the topics that are hard, and what you want to reach — the centre replies with a plan."},
        "register_intro_zh": "年级、当前难点与希望达到的目标，教室会给出对应的学习方案。",
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
        "hero": {"subtitle": {"zh": "兼顾技术、体态与舞台表达，让每一步更自信。", "en": "Build technique, presence, and confidence in every movement."}},
        "venue_noun": {"zh": "舞蹈教室", "en": "studio"},
        "work_noun": {"zh": "舞蹈录像", "en": "recording", "en_plural": "recordings"},
        "registration_title": "Tell us about the dancer", "registration_title_zh": "告诉我们舞者的经验与目标",
        "copy_pack": {"portal_label": "Dance Student Portal", "register_intro": "The style, the level and the goal, then the studio will suggest a class and a trial time."},
        "register_intro_zh": "舞种、当前水平与训练目标，之后舞蹈教室会安排合适的班级与试课时间。",
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
        "hero": {"subtitle": {"zh": "从真实沟通出发，建立能够长期使用的语言能力。", "en": "Build practical language skills through real communication."}},
        "venue_noun": {"zh": "教室", "en": "centre"},
        "work_noun": {"zh": "练习", "en": "exercise", "en_plural": "exercises"},
        "registration_title": "Tell us which language and what level", "registration_title_zh": "告诉我们学习语言与当前水平",
        "copy_pack": {"portal_label": "Language Student Portal", "register_intro": "Which language, what level, and where you will use it — the centre replies with a class and a time."},
        "register_intro_zh": "目标语言、当前水平与使用场景，教室会推荐合适的课程与上课时间。",
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
        "hero": {"subtitle": {"zh": "科学训练、清晰反馈与持续进步。", "en": "Purposeful coaching, clear feedback, and steady progress."}},
        "venue_noun": {"zh": "训练中心", "en": "club"},
        "work_noun": {"zh": "训练记录", "en": "session record", "en_plural": "session records"},
        "registration_title": "Tell us the sport and the goal", "registration_title_zh": "告诉我们运动项目与训练目标",
        "copy_pack": {"portal_label": "Sports Student Portal", "register_intro": "The sport, the current level and the goal, then the club will suggest a squad and a session time."},
        "register_intro_zh": "运动项目、当前水平与训练目标，之后训练中心会推荐合适的组别与训练时间。",
        "theme": {"background_color": "#F4FAF5", "panel_color": "#FFFFFF", "text_color": "#17251A", "accent_color": "#166534", "secondary_accent_color": "#B45309", "button_style": "sharp", "font_mood": "modern"},
        "fields": [
            _field("sport", "Sport", "运动项目", "Tennis, swimming, basketball, soccer", "网球、游泳、篮球、足球等"),
            _field("level", "Current level", "当前水平", "Beginner, club, competition", "零基础、俱乐部、比赛级别"),
            _field("goals", "Training goals", "训练目标", "Fitness, technique, competition prep", "体能、技术、比赛准备"),
        ],
    },
    "game": {
        # "Game" dropped the half of the offer the Chinese label keeps: 编程.
        "label": "Games & Coding", "label_zh": "游戏与编程", "layout": "digital",
        "slogan": "Play, think, create, and level up.", "slogan_zh": "在玩中思考、创造与升级。",
        "hero": {"subtitle": {"zh": "把兴趣转化为策略、编程、创造力与团队能力。", "en": "Turn play into strategy, coding, creativity, and teamwork."}},
        "venue_noun": {"zh": "工作室", "en": "studio"},
        "work_noun": {"zh": "项目", "en": "project", "en_plural": "projects"},
        "registration_title": "Tell us what they want to build or play", "registration_title_zh": "告诉我们感兴趣的游戏或编程方向",
        "copy_pack": {"portal_label": "Games & Coding Portal", "register_intro": "What they want to build or play, how much they have done, and what they want to learn — the studio replies with a project and a start date."},
        "register_intro_zh": "想做什么或想玩什么、目前的经验与学习目标，之后工作室会推荐合适的项目与开课时间。",
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
        "hero": {"subtitle": {"zh": "从兴趣和目标出发，在适合的节奏中稳步成长。", "en": "Start with the learner's interests and goals, then grow at the right pace."}},
        "venue_noun": {"zh": "工作室", "en": "studio"},
        "work_noun": {"zh": "作品", "en": "work", "en_plural": "works"},
        "registration_title": "Tell us about the student", "registration_title_zh": "告诉我们学员的兴趣与学习目标",
        "copy_pack": {"portal_label": "Student Portal", "register_intro": "Interests, experience and goals, then the studio will suggest a class and a time."},
        "register_intro_zh": "兴趣方向、当前经验与学习目标，之后工作室会推荐合适的课程与时间。",
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

# The industry card in Studio Admin shows `slogan`; the site it publishes shows
# `hero.title`. Those were two hand-written strings, and in Chinese five of the
# eight had drifted apart — an owner picked 艺术 because the card promised
# 「大胆创作，让成长看得见。」 and the site went live saying
# 「让创意被看见，让成长有作品。」. In English they happened to be identical, so
# the fork was invisible to anyone reading the source in English.
#
# The hero title is now derived rather than written, so a card and the page it
# describes cannot disagree again. The subtitle stays hand-written: it is a
# different sentence doing a different job.
for _preset in INDUSTRY_PRESETS.values():
    _preset["hero"]["title"] = {"zh": _preset["slogan_zh"], "en": _preset["slogan"]}


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

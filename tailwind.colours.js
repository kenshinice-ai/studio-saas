/* CMS 的 Tailwind 色板：把工具类重新指向语义令牌。
 *
 * 这一段是从 legacy-root/index.html 的运行时配置里**原样搬过来**的，一个字符
 * 都没有重写。v10.16.0 之前它由浏览器里的 Tailwind Play 构建在运行时读取
 * （441KB 的 JIT 编译器，同步加载，排在 React 前面）；现在由构建期的
 * tailwind.config.js 读取，产出一份静态 CSS。
 *
 * **搬运本身是这个改动的全部风险。** 所以它是一次机械抽取而不是一次誊写，
 * 而且 backend/tests/test_tailwind_build.py 会比对：这份文件里定义的每一个
 * 颜色族，都必须在编译产物里真的解析成同一个 var()。
 *
 * 值全部是 CSS 变量或 color-mix()，所以主题切换仍然在运行时发生——编译期
 * 固化的是「哪个工具类指向哪个令牌」，不是颜色本身。
 */
const mix = (token, weight, base) =>
  'color-mix(in srgb, var(' + token + ') ' + weight + '%, var(' + base + '))';

/* Neutral: the page at one end, the ink at the other. */
const neutral = {
  50:  'var(--bg2)',
  100: 'var(--surface-hover)',
  200: 'var(--line)',
  300: 'var(--line-strong)',
  400: 'var(--disabled-text)',
  500: 'var(--muted)',
  600: 'var(--muted)',
  700: 'var(--ink2)',
  800: 'var(--ink)',
  900: 'var(--ink)',
  950: 'var(--ink)',
};

/* A role: quiet tint, its border, the solid fill, then hover and pressed
   — which the generator already moves in the mode-correct direction, so a
   filled button stays a filled button in dark. */
const role = (base) => ({
  50:  'var(--' + base + '-soft)',
  100: 'var(--' + base + '-soft)',
  200: 'var(--' + base + '-border)',
  300: 'var(--' + base + '-border)',
  400: mix('--' + base, 70, '--' + base + '-soft'),
  500: 'var(--' + base + ')',
  600: 'var(--' + base + ')',
  700: 'var(--' + base + ')',
  800: 'var(--' + base + '-hover, var(--' + base + '))',
  900: 'var(--' + base + '-pressed, var(--' + base + '))',
  950: 'var(--' + base + '-pressed, var(--' + base + '))',
});

/* Twelve Tailwind families, six roles. Read off what each is used FOR in
   the source rather than by hue: purple marks media and permissions
   (info), pink and rose mark birthdays (the support colour), orange marks
   churn risk and top-ups (warning). */
const accent = role('accent');
const colours = {
  /* A card, and the label on a filled button. --panel clears 4.5:1 on
     every accent across all 16 theme-modes (worst 5.10, arcade-lime
     dark), so one value serves both and 183 -white utilities need no
     source change. */
  white: 'var(--panel)',
  black: 'var(--ink)',
  gray: neutral, slate: neutral, zinc: neutral,
  neutral: neutral, stone: neutral,
  indigo: accent, violet: accent, fuchsia: accent,
  red: role('danger'),
  rose: role('accent-2'), pink: role('accent-2'),
  amber: role('warning'), orange: role('warning'), yellow: role('warning'),
  green: role('success'), emerald: role('success'),
  teal: role('success'), lime: role('success'),
  blue: role('info'), sky: role('info'), cyan: role('info'),
  purple: role('info'),
};

/* 让 `/50` 这样的透明度修饰符真的生效。
 *
 * 上面每一个值都是 `var(--token)` 或 `color-mix()`。Tailwind 无法给这样的值
 * 加 alpha —— 它需要一个 `<alpha-value>` 占位符或分离的通道 —— 所以凡是带
 * 修饰符的工具类，**整条规则会被静默丢弃**。
 *
 * 实测（浏览器，运行时编译器与编译产物结果一致）：
 *
 *     bg-black/50   → rgba(0, 0, 0, 0)      完全透明
 *     bg-white/10   → rgba(0, 0, 0, 0)
 *     bg-gray-50/95 → rgba(0, 0, 0, 0)
 *
 * `bg-black/50` 是 CMS 里每一个模态对话框的遮罩层（components.jsx 的
 * ConfirmDialog、课程编辑器、学员档案弹窗……），也就是说自 v8.4.2 这份映射
 * 引入以来，**这个后台的所有对话框都没有遮罩**。这不是构建期编译带来的回归
 * ——运行时编译器同样丢弃它们；这是把这几十个工具类逐个量了一遍才看见的。
 *
 * 修法是把每个值包成 Tailwind 的函数形式：没有修饰符时原样返回 var()，
 * 有修饰符时用 color-mix 兑出来。color-mix 本来就是这份映射自己在用的
 * （见上面的 role() 400 档），所以不引入新的浏览器要求。
 */
const alphaAware = (value) => ({ opacityValue }) => {
  /* Tailwind 对**不带**修饰符的工具类传的是 `var(--tw-bg-opacity)`，不是 1。
     第一版把它交给 Number() 得到 NaN，于是 `color-mix(… NaN%, …)` 无效，
     bg-white 和 bg-indigo-600 一起变成了透明——比原来的缺陷严重得多。
     所以只有拿到一个真正的数字时才兑，其余情况原样返回。 */
  const numeric = typeof opacityValue === 'number'
    ? opacityValue
    : (typeof opacityValue === 'string' && /^[0-9.]+$/.test(opacityValue)
        ? Number(opacityValue) : null);
  if (numeric === null || numeric >= 1) return value;
  return `color-mix(in srgb, ${value} ${numeric * 100}%, transparent)`;
};

const withAlpha = (input) => {
  if (typeof input === 'string') return alphaAware(input);
  const out = {};
  for (const [step, value] of Object.entries(input)) out[step] = alphaAware(value);
  return out;
};

const alphaColours = {};
for (const [family, value] of Object.entries(colours)) alphaColours[family] = withAlpha(value);

module.exports = { colours: alphaColours, rawColours: colours };

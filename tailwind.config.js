/* 构建期的 Tailwind，取代浏览器里的 441KB JIT 编译器。
 *
 * 在 v10.16.0 之前，CMS 装的是 Tailwind Play CDN —— 那个「在浏览器里现场编译
 * CSS」的开发用构建。它在 legacy-root/index.html 同步加载，排在 React 前面：
 * 老师在教室的 4G 下打开 CMS 点名，要先下 441KB，再等浏览器把类名编译成 CSS，
 * 然后 React 才开始挂载。
 *
 * `content` 三处一个都不能少：漏掉一处不会报错，只会静默丢掉那一处用到的类。
 * 这正是这个改动最危险的失败方式，也是 backend/tests/test_tailwind_build.py
 * 存在的理由——它把源码里出现过的每一个类名，拿去编译产物里找。
 *
 * `legacy-root/register.html` 刻意不在这里，但**不再**是因为它还在用 vendored
 * 脚本——v10.17.0 已经把它也搬到构建期了。它从不配置这份色板，用的是原版色阶
 * 加自己的 :root，套上去会改变一个公开转化页的外观。所以它有自己的一份配置：
 * tailwind.register.config.js，同一个构建脚本，原版色板。
 */
const { colours } = require('./tailwind.colours.js');

module.exports = {
  content: [
    './legacy-root/src/**/*.jsx',
    './legacy-root/index.html',
  ],
  theme: {
    extend: {
      colors: colours,
    },
  },
};

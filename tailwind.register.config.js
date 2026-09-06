/* 学员注册页的构建期 Tailwind——**故意**用原版色阶，不套 CMS 的色板。
 *
 * `legacy-root/register.html` 是 v10.16.0 之后最后一个还在加载
 * `/vendor/tailwindcss.js` 的页面：451KB 的浏览器内 JIT 编译器，同步加载。
 * 线上实测（2026-09-07）：
 *
 *     GET /_legacy/register        200,  48,930 bytes
 *     GET /vendor/tailwindcss.js   200, 451,131 bytes
 *
 * 这份配置产出 16,942 字节的静态表，把那 451KB 从这条公开路由上拿掉。
 *
 * ## 为什么不复用 tailwind.config.js
 *
 * CMS 那份把每个 Tailwind 色族重新指向语义令牌（indigo→--accent，green→--success
 * ……）。这个页面从来没有配过那份色板：它用原版 indigo/purple 色阶，再用自己
 * `<style>` 里的 `[class*="bg-indigo-600"]{...!important}` 一族改写成租户色。
 * 套上 CMS 色板会让一个公开页面**换一种颜色**——那是产品决定，不是这次改动。
 *
 * 所以这里 theme 一个字都不改：编译出来的每条规则与浏览器里那个编译器产出的
 * 逐条对应。实测方式是把运行时编译器生成的 180 条规则全部读出来，逐个到编译
 * 产物里找：142 条带类名的选择器，缺 0 条（含 JS 注入的
 * `focus:ring-indigo-400`、`min-h-[44px]`、`active:bg-white/30`）。
 *
 * ## content 只有一处，而且够
 *
 * 这个页面只加载 `/assets/ui-common.js`，那个文件一个 class 都不产出（grep 计数
 * 为 0）。页面自己在 JS 模板字符串里拼的类名是字面量，扫描看得见。
 * backend/tests/test_register_tailwind_build.py 是这条前提的守卫。
 */
module.exports = {
  content: [
    './legacy-root/register.html',
  ],
};

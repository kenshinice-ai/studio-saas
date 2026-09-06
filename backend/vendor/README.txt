Pinned local vendor bundles (no CDN at runtime):
  react.production.min.js       react@18.3.1 UMD
  react-dom.production.min.js   react-dom@18.3.1 UMD

tailwindcss.js was removed in v10.17.0 — nothing loads it any more. Both
consumers now ship a stylesheet compiled at build time by build_cms.sh:
  the CMS               tailwind.config.js          -> assets/cms-tailwind.css   (40KB)
  the registration page tailwind.register.config.js -> assets/register-tailwind.css (17KB)
The second config deliberately keeps STOCK Tailwind colours; the CMS colour map
would have repainted a public page. Verified byte-identical rendering: 166
elements x 21 computed properties, zero differences.

babel.min.js was removed — the CMS JSX is precompiled at build time
(backend/scripts/build_cms.sh). CDN <script document.write> fallbacks in
legacy pages remain as a safety net only.

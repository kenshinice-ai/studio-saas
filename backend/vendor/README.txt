Pinned local vendor bundles (no CDN at runtime):
  react.production.min.js       react@18.3.1 UMD
  react-dom.production.min.js   react-dom@18.3.1 UMD
  tailwindcss.js                tailwind play build 3.4.16

babel.min.js was removed — the CMS JSX is precompiled at build time
(backend/scripts/build_cms.sh). CDN <script document.write> fallbacks in
legacy pages remain as a safety net only.

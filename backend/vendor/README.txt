Pinned local vendor bundles (no CDN at runtime):
  react.production.min.js       react@18.3.1 UMD
  react-dom.production.min.js   react-dom@18.3.1 UMD
  tailwindcss.js                tailwind play build 3.4.16
                                Since v10.16.0 the CMS no longer loads this: its
                                stylesheet is compiled at build time
                                (tailwind.config.js -> build_cms.sh ->
                                backend/frontend/assets/cms-tailwind.css,
                                451KB -> ~40KB, and the browser no longer runs a
                                CSS compiler ahead of React).
                                legacy-root/register.html still loads it: that
                                page uses stock Tailwind colours and never
                                carried the CMS colour map, so moving it is a
                                separate change to a public conversion page.

babel.min.js was removed — the CMS JSX is precompiled at build time
(backend/scripts/build_cms.sh). CDN <script document.write> fallbacks in
legacy pages remain as a safety net only.

/* The served pages under /customer-resources/ and /zh/customer-resources/.
 *
 * There is no language toggle here any more. Each language is a document at
 * its own address, filtered server-side before it is sent, so the switch in
 * the top line is an ordinary link and the DOM that arrives holds exactly one
 * language. The toggle this file used to carry set `root.lang` from
 * localStorage, which after the split would overwrite the `lang` the server
 * declares — and the declared one is the true one, because it describes the
 * bytes that actually arrived.
 *
 * What is left is the copyright year, which is the one thing on these pages
 * that belongs to the reader's clock rather than to the release.
 */
(() => {
  'use strict';

  const year = document.getElementById('year');
  if (year) {
    year.textContent = String(new Date().getFullYear());
  }
})();

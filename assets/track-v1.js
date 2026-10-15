/* Anonymous click beacon for store and demo links: no cookies, no IDs, never delays navigation. */
(function () {
  var TARGETS = [
    ["https://apps.odoo.com/apps/modules/19.0/gh_dental_clinic_account", "store_account"],
    ["https://apps.odoo.com/apps/modules/19.0/gh_dental_clinic", "store_clinic"],
    ["https://dental-demo.giulianoh.dev/demo", "demo"]
  ];
  var ENDPOINT = "https://dental-demo.giulianoh.dev/track/click";

  function report(event) {
    try {
      var a = event.target && event.target.closest && event.target.closest("a[href]");
      if (!a) return;
      var href = a.href || "";
      for (var i = 0; i < TARGETS.length; i++) {
        if (href.indexOf(TARGETS[i][0]) === 0) {
          var body = JSON.stringify({ target: TARGETS[i][1], page: location.pathname });
          navigator.sendBeacon(ENDPOINT, new Blob([body], { type: "text/plain" }));
          return;
        }
      }
    } catch (e) { /* tracking must never break the page */ }
  }

  document.addEventListener("click", report, true);
  document.addEventListener("auxclick", report, true);
})();

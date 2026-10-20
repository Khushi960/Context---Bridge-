/* Context Bridge login guard. Loaded before the app (plain script, no build step needed).
 * - If nobody is logged in, go to /login.html.
 * - If the session ends while working (logged out elsewhere, expired), go to /login.html.
 * - Shows "Signed in as ..." and a Log out button at the bottom of the sidebar.
 */
(function () {
  var realFetch = window.fetch.bind(window);
  var toLogin = function () {
    if (location.pathname !== "/login.html") location.replace("/login.html");
  };

  window.fetch = function (input, init) {
    return realFetch(input, init).then(function (res) {
      var url = typeof input === "string" ? input : (input && input.url) || "";
      if (res.status === 401 && url.indexOf("/api/") !== -1 && url.indexOf("/api/auth/") === -1) toLogin();
      return res;
    });
  };

  function logout() {
    realFetch("/api/auth/logout", { method: "POST" }).finally(function () {
      location.replace("/login.html");
    });
  }

  function addChip(user) {
    var put = function () {
      var foot = document.querySelector(".sidebar .foot");
      if (!foot || foot.querySelector(".who")) return false;
      var row = document.createElement("div");
      row.className = "who";
      var name = document.createElement("span");
      name.textContent = "Signed in as " + user.username;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "Log out";
      btn.addEventListener("click", logout);
      row.appendChild(name);
      row.appendChild(btn);
      foot.insertBefore(row, foot.firstChild);
      return true;
    };
    if (put()) return;
    var mo = new MutationObserver(function () {
      put();
    });
    mo.observe(document.documentElement, { childList: true, subtree: true });
  }

  realFetch("/api/auth/me")
    .then(function (res) {
      if (res.status === 401) return toLogin();
      if (res.ok) return res.json().then(addChip);
    })
    .catch(function () {
      /* server down: the app shows its own "cannot reach the server" message */
    });

  var css = document.createElement("style");
  css.textContent =
    ".foot .who{display:flex;align-items:center;justify-content:space-between;gap:8px;padding-bottom:6px;margin-bottom:4px;" +
    "border-bottom:1px solid rgba(232,227,211,.15);color:var(--deep-ink,#e8e3d3);overflow:hidden}" +
    ".foot .who span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}" +
    ".foot .who button{flex:none;background:none;border:1px solid rgba(232,227,211,.35);border-radius:5px;color:inherit;padding:2px 8px;font-size:12px}" +
    ".foot .who button:hover{background:rgba(255,255,255,.08)}";
  document.head.appendChild(css);
})();

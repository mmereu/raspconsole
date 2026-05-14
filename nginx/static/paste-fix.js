window.addEventListener("load", function() {
  function attachClipboard() {
    var ta = document.querySelector(".xterm-helper-textarea");
    if (!ta) { setTimeout(attachClipboard, 500); return; }
    ta.addEventListener("keydown", function(e) {
      if (e.ctrlKey && !e.shiftKey && e.key === "v") {
        e.stopImmediatePropagation();
        var tmp = document.createElement("textarea");
        tmp.style.cssText = "position:fixed;opacity:0;top:0;left:0;width:1px;height:1px";
        document.body.appendChild(tmp);
        tmp.focus();
        tmp.addEventListener("paste", function(pe) {
          var text = pe.clipboardData.getData("text/plain");
          document.body.removeChild(tmp);
          if (text) {
            var evt = new ClipboardEvent("paste", {bubbles:true, cancelable:true});
            Object.defineProperty(evt, "clipboardData", {
              value: {getData: function(t) { return t==="text/plain" ? text : ""; }}
            });
            ta.dispatchEvent(evt);
            ta.focus();
          }
          pe.preventDefault();
        }, {once:true, capture:true});
      }
    }, true);
  }
  attachClipboard();
});

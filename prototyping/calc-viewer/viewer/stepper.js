// Stepper: "‹ 2 of 5 · label ›". Clicking the body goes to the next stop (wrapping); arrows go back/forward.
// With one stop it shows "1 of 1 · label" with no arrows; clicking it opens that stop again.
import { esc } from "./data.js";

export function makeStepper({ count, label, onGo, index = -1, visited = new Set() }) {
  const root = document.createElement("div");
  let cur = index;
  const single = count <= 1;
  root.className = "stepper" + (single ? " single" : "");
  const render = () => {
    const shown = cur < 0 ? 0 : cur;
    const text = `<span class="count">${cur < 0 && !single ? `${count} locations` : `${shown + 1} of ${count}`}</span><span class="lbl">${esc(label(shown))}</span>`;
    const dots = !single && count <= 24
      ? `<span class="visits">${Array.from({ length: count }, (_, i) => `<i class="${i === cur ? "cur" : visited.has(i) ? "v" : ""}"></i>`).join("")}</span>` : "";
    root.innerHTML = single
      ? `<div class="body">${text}</div>`
      : `<button class="arr prev" title="Previous">‹</button><button class="body" title="Next location">${text}${dots}</button><button class="arr next" title="Next">›</button>`;
  };
  const go = (i) => {
    cur = (i + count) % count;
    visited.add(cur);
    render();
    onGo(cur);
  };
  root.addEventListener("click", (ev) => {
    ev.stopPropagation();
    if (single) { go(0); return; } // one stop: nothing to step through, but each click still (re)opens it
    const b = ev.target.closest("button");
    if (!b) return;
    if (b.classList.contains("prev")) go(cur < 0 ? count - 1 : cur - 1);
    else go(cur < 0 ? 0 : cur + 1);
  });
  render();
  return { el: root, go, get index() { return cur; }, set(i) { cur = i; visited.add(i); render(); } };
}

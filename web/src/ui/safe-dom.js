// Null-safe selector for screens. Screens fill in parts of their page after an await (weather, saved checks, a save
// button). If the farmer has already moved to another page those parts are gone; writing to them must be a quiet
// no-op, not an uncaught error. `qs(host)` returns the element when it exists and an inert stand-in when it does not.
const sink = new Proxy(function sinkFn() {}, {
  get: (_t, key) => (key === Symbol.toPrimitive ? () => '' : sink),
  set: () => true,
  apply: () => sink,
});

/** @param {ParentNode} host @returns {(selector:string) => any} */
export const qs = (host) => (selector) => host.querySelector(selector) ?? sink;

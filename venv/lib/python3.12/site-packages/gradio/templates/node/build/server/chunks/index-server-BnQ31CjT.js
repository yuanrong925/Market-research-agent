import { s as ssr_context } from './context-CBkBucIx.js';

/** @import { SSRContext } from '#server' */
/** @import { Renderer } from './internal/server/renderer.js' */

/** @param {() => void} fn */
function onDestroy(fn) {
	/** @type {Renderer} */ (/** @type {SSRContext} */ (ssr_context).r).on_destroy(fn);
}

async function tick() {}

export { onDestroy as o, tick as t };
//# sourceMappingURL=index-server-BnQ31CjT.js.map

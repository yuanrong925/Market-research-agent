import './async-D55cHugf.js';
import { c as spread_props, b as store_get, u as unsubscribe_stores, d as bind_props, f as attr_class, g as attr_style, i as stringify, m as attributes } from './index-6p4UEISu.js';
import { t as tick } from './index-server-BnQ31CjT.js';
import { O as Os } from './2-DQcH4kU_.js';
import { k } from './BlockLabel-Cwr2q1Ma.js';
import { u } from './DownloadLink-eCzvV1uC.js';
import { w } from './IconButton-DoTLxBZ_.js';
import { p } from './Empty-cEfRNAPl.js';
import { o } from './Clear-D7Yjckqz.js';
import { l } from './Download-DcU5dONL.js';
import { i } from './Image2-vcp9_ifi.js';
import { r } from './Undo-Ce01x-M5.js';
import { y } from './IconButtonWrapper-DtthXzCF.js';
import { v } from './FullscreenButton-Ktp2P70R.js';
import { w as writable } from './index-Cg-Pg6j3.js';
import { l as loop, r as raf, i as is_date, s as ss } from './index3-CiV5UCJA.js';
import { e as ee$1 } from './Upload2-CAgMsGRX.js';
import { G as G$1 } from './Block-DFkF8ric.js';
import { k as k$1 } from './UploadText-BslqYKOD.js';
import './escaping-CBnpiEl5.js';
import './context-CBkBucIx.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './Maximize-CuHbK64j.js';
import './Upload-BbxeBrrD.js';

/*
Adapted from https://github.com/mattdesl
Distributed under MIT License https://github.com/mattdesl/eases/blob/master/LICENSE.md
*/

/**
 * @param {number} t
 * @returns {number}
 */
function linear(t) {
	return t;
}

/** @import { Task } from '../internal/client/types' */
/** @import { Tweened } from './public' */
/** @import { TweenedOptions } from './private' */

/**
 * @template T
 * @param {T} a
 * @param {T} b
 * @returns {(t: number) => T}
 */
function get_interpolator(a, b) {
	if (a === b || a !== a) return () => a;

	const type = typeof a;
	if (type !== typeof b || Array.isArray(a) !== Array.isArray(b)) {
		throw new Error('Cannot interpolate values of different type');
	}

	if (Array.isArray(a)) {
		const arr = /** @type {Array<any>} */ (b).map((bi, i) => {
			return get_interpolator(/** @type {Array<any>} */ (a)[i], bi);
		});

		// @ts-ignore
		return (t) => arr.map((fn) => fn(t));
	}

	if (type === 'object') {
		if (!a || !b) {
			throw new Error('Object cannot be null');
		}

		if (is_date(a) && is_date(b)) {
			const an = a.getTime();
			const bn = b.getTime();
			const delta = bn - an;

			// @ts-ignore
			return (t) => new Date(an + t * delta);
		}

		const keys = Object.keys(b);

		/** @type {Record<string, (t: number) => T>} */
		const interpolators = {};
		keys.forEach((key) => {
			// @ts-ignore
			interpolators[key] = get_interpolator(a[key], b[key]);
		});

		// @ts-ignore
		return (t) => {
			/** @type {Record<string, any>} */
			const result = {};
			keys.forEach((key) => {
				result[key] = interpolators[key](t);
			});
			return result;
		};
	}

	if (type === 'number') {
		const delta = /** @type {number} */ (b) - /** @type {number} */ (a);
		// @ts-ignore
		return (t) => a + t * delta;
	}

	// for non-numeric values, snap to the final value immediately
	return () => b;
}

/**
 * A tweened store in Svelte is a special type of store that provides smooth transitions between state values over time.
 *
 * @deprecated Use [`Tween`](https://svelte.dev/docs/svelte/svelte-motion#Tween) instead
 * @template T
 * @param {T} [value]
 * @param {TweenedOptions<T>} [defaults]
 * @returns {Tweened<T>}
 */
function tweened(value, defaults = {}) {
	const store = writable(value);
	/** @type {Task} */
	let task;
	let target_value = value;
	/**
	 * @param {T} new_value
	 * @param {TweenedOptions<T>} [opts]
	 */
	function set(new_value, opts) {
		target_value = new_value;

		if (value == null) {
			store.set((value = new_value));
			return Promise.resolve();
		}

		/** @type {Task | null} */
		let previous_task = task;

		let started = false;
		let {
			delay = 0,
			duration = 400,
			easing = linear,
			interpolate = get_interpolator
		} = { ...defaults, ...opts };

		if (duration === 0) {
			if (previous_task) {
				previous_task.abort();
				previous_task = null;
			}
			store.set((value = target_value));
			return Promise.resolve();
		}

		const start = raf.now() + delay;

		/** @type {(t: number) => T} */
		let fn;
		task = loop((now) => {
			if (now < start) return true;
			if (!started) {
				fn = interpolate(/** @type {any} */ (value), new_value);
				if (typeof duration === 'function')
					duration = duration(/** @type {any} */ (value), new_value);
				started = true;
			}
			if (previous_task) {
				previous_task.abort();
				previous_task = null;
			}
			const elapsed = now - start;
			if (elapsed > /** @type {number} */ (duration)) {
				store.set((value = new_value));
				return false;
			}
			// @ts-ignore
			store.set((value = fn(easing(elapsed / duration))));
			return true;
		});
		return task.promise;
	}
	return {
		set,
		update: (fn, opts) =>
			set(fn(/** @type {any} */ (target_value), /** @type {any} */ (value)), opts),
		subscribe: store.subscribe
	};
}

/* empty css                                          */var Rt={value:()=>{}};function G(t){this._=t;}function Dt(t,e){return t.trim().split(/^|\s+/).map(function(i){var n="",s=i.indexOf(".");if(s>=0&&(n=i.slice(s+1),i=i.slice(0,s)),i&&!e.hasOwnProperty(i))throw new Error("unknown type: "+i);return {type:i,name:n}})}G.prototype={constructor:G,on:function(t,e){var i=this._,n=Dt(t+"",i),s,r=-1,u=n.length;if(arguments.length<2){for(;++r<u;)if((s=(t=n[r]).type)&&(s=Lt(i[s],t.name)))return s;return}if(e!=null&&typeof e!="function")throw new Error("invalid callback: "+e);for(;++r<u;)if(s=(t=n[r]).type)i[s]=ot(i[s],t.name,e);else if(e==null)for(s in i)i[s]=ot(i[s],t.name,null);return this},copy:function(){var t={},e=this._;for(var i in e)t[i]=e[i].slice();return new G(t)},call:function(t,e){if((s=arguments.length-2)>0)for(var i=new Array(s),n=0,s,r;n<s;++n)i[n]=arguments[n+2];if(!this._.hasOwnProperty(t))throw new Error("unknown type: "+t);for(r=this._[t],n=0,s=r.length;n<s;++n)r[n].value.apply(e,i);},apply:function(t,e,i){if(!this._.hasOwnProperty(t))throw new Error("unknown type: "+t);for(var n=this._[t],s=0,r=n.length;s<r;++s)n[s].value.apply(e,i);}};function Lt(t,e){for(var i=0,n=t.length,s;i<n;++i)if((s=t[i]).name===e)return s.value}function ot(t,e,i){for(var n=0,s=t.length;n<s;++n)if(t[n].name===e){t[n]=Rt,t=t.slice(0,n).concat(t.slice(n+1));break}return i!=null&&t.push({name:e,value:i}),t}var Z="http://www.w3.org/1999/xhtml";const rt={svg:"http://www.w3.org/2000/svg",xhtml:Z,xlink:"http://www.w3.org/1999/xlink",xml:"http://www.w3.org/XML/1998/namespace",xmlns:"http://www.w3.org/2000/xmlns/"};function dt(t){var e=t+="",i=e.indexOf(":");return i>=0&&(e=t.slice(0,i))!=="xmlns"&&(t=t.slice(i+1)),rt.hasOwnProperty(e)?{space:rt[e],local:t}:t}function Ft(t){return function(){var e=this.ownerDocument,i=this.namespaceURI;return i===Z&&e.documentElement.namespaceURI===Z?e.createElement(t):e.createElementNS(i,t)}}function Ut(t){return function(){return this.ownerDocument.createElementNS(t.space,t.local)}}function _t(t){var e=dt(t);return (e.local?Ut:Ft)(e)}function Ot(){}function gt(t){return t==null?Ot:function(){return this.querySelector(t)}}function Vt(t){typeof t!="function"&&(t=gt(t));for(var e=this._groups,i=e.length,n=new Array(i),s=0;s<i;++s)for(var r=e[s],u=r.length,l=n[s]=new Array(u),o,c,f=0;f<u;++f)(o=r[f])&&(c=t.call(o,o.__data__,f,r))&&("__data__"in o&&(c.__data__=o.__data__),l[f]=c);return new M(n,this._parents)}function Xt(t){return t==null?[]:Array.isArray(t)?t:Array.from(t)}function qt(){return []}function Yt(t){return t==null?qt:function(){return this.querySelectorAll(t)}}function Ht(t){return function(){return Xt(t.apply(this,arguments))}}function Gt(t){typeof t=="function"?t=Ht(t):t=Yt(t);for(var e=this._groups,i=e.length,n=[],s=[],r=0;r<i;++r)for(var u=e[r],l=u.length,o,c=0;c<l;++c)(o=u[c])&&(n.push(t.call(o,o.__data__,c,u)),s.push(o));return new M(n,s)}function Kt(t){return function(){return this.matches(t)}}function mt(t){return function(e){return e.matches(t)}}var Wt=Array.prototype.find;function Jt(t){return function(){return Wt.call(this.children,t)}}function Qt(){return this.firstElementChild}function Zt(t){return this.select(t==null?Qt:Jt(typeof t=="function"?t:mt(t)))}var jt=Array.prototype.filter;function $t(){return Array.from(this.children)}function te(t){return function(){return jt.call(this.children,t)}}function ee(t){return this.selectAll(t==null?$t:te(typeof t=="function"?t:mt(t)))}function ne(t){typeof t!="function"&&(t=Kt(t));for(var e=this._groups,i=e.length,n=new Array(i),s=0;s<i;++s)for(var r=e[s],u=r.length,l=n[s]=[],o,c=0;c<u;++c)(o=r[c])&&t.call(o,o.__data__,c,r)&&l.push(o);return new M(n,this._parents)}function vt(t){return new Array(t.length)}function ie(){return new M(this._enter||this._groups.map(vt),this._parents)}function W(t,e){this.ownerDocument=t.ownerDocument,this.namespaceURI=t.namespaceURI,this._next=null,this._parent=t,this.__data__=e;}W.prototype={constructor:W,appendChild:function(t){return this._parent.insertBefore(t,this._next)},insertBefore:function(t,e){return this._parent.insertBefore(t,e)},querySelector:function(t){return this._parent.querySelector(t)},querySelectorAll:function(t){return this._parent.querySelectorAll(t)}};function se(t){return function(){return t}}function oe(t,e,i,n,s,r){for(var u=0,l,o=e.length,c=r.length;u<c;++u)(l=e[u])?(l.__data__=r[u],n[u]=l):i[u]=new W(t,r[u]);for(;u<o;++u)(l=e[u])&&(s[u]=l);}function re(t,e,i,n,s,r,u){var l,o,c=new Map,f=e.length,v=r.length,g=new Array(f),y;for(l=0;l<f;++l)(o=e[l])&&(g[l]=y=u.call(o,o.__data__,l,e)+"",c.has(y)?s[l]=o:c.set(y,o));for(l=0;l<v;++l)y=u.call(t,r[l],l,r)+"",(o=c.get(y))?(n[l]=o,o.__data__=r[l],c.delete(y)):i[l]=new W(t,r[l]);for(l=0;l<f;++l)(o=e[l])&&c.get(g[l])===o&&(s[l]=o);}function le(t){return t.__data__}function ae(t,e){if(!arguments.length)return Array.from(this,le);var i=e?re:oe,n=this._parents,s=this._groups;typeof t!="function"&&(t=se(t));for(var r=s.length,u=new Array(r),l=new Array(r),o=new Array(r),c=0;c<r;++c){var f=n[c],v=s[c],g=v.length,y=ue(t.call(f,f&&f.__data__,c,n)),b=y.length,P=l[c]=new Array(b),S=u[c]=new Array(b),_=o[c]=new Array(g);i(f,v,P,S,_,y,e);for(var p=0,k=0,a,h;p<b;++p)if(a=P[p]){for(p>=k&&(k=p+1);!(h=S[k])&&++k<b;);a._next=h||null;}}return u=new M(u,n),u._enter=l,u._exit=o,u}function ue(t){return typeof t=="object"&&"length"in t?t:Array.from(t)}function ce(){return new M(this._exit||this._groups.map(vt),this._parents)}function fe(t,e,i){var n=this.enter(),s=this,r=this.exit();return typeof t=="function"?(n=t(n),n&&(n=n.selection())):n=n.append(t+""),e!=null&&(s=e(s),s&&(s=s.selection())),i==null?r.remove():i(r),n&&s?n.merge(s).order():s}function he(t){for(var e=t.selection?t.selection():t,i=this._groups,n=e._groups,s=i.length,r=n.length,u=Math.min(s,r),l=new Array(s),o=0;o<u;++o)for(var c=i[o],f=n[o],v=c.length,g=l[o]=new Array(v),y,b=0;b<v;++b)(y=c[b]||f[b])&&(g[b]=y);for(;o<s;++o)l[o]=i[o];return new M(l,this._parents)}function pe(){for(var t=this._groups,e=-1,i=t.length;++e<i;)for(var n=t[e],s=n.length-1,r=n[s],u;--s>=0;)(u=n[s])&&(r&&u.compareDocumentPosition(r)^4&&r.parentNode.insertBefore(u,r),r=u);return this}function de(t){t||(t=_e);function e(v,g){return v&&g?t(v.__data__,g.__data__):!v-!g}for(var i=this._groups,n=i.length,s=new Array(n),r=0;r<n;++r){for(var u=i[r],l=u.length,o=s[r]=new Array(l),c,f=0;f<l;++f)(c=u[f])&&(o[f]=c);o.sort(e);}return new M(s,this._parents).order()}function _e(t,e){return t<e?-1:t>e?1:t>=e?0:NaN}function ge(){var t=arguments[0];return arguments[0]=this,t.apply(null,arguments),this}function me(){return Array.from(this)}function ve(){for(var t=this._groups,e=0,i=t.length;e<i;++e)for(var n=t[e],s=0,r=n.length;s<r;++s){var u=n[s];if(u)return u}return null}function we(){let t=0;for(const e of this)++t;return t}function ye(){return !this.node()}function be(t){for(var e=this._groups,i=0,n=e.length;i<n;++i)for(var s=e[i],r=0,u=s.length,l;r<u;++r)(l=s[r])&&t.call(l,l.__data__,r,s);return this}function xe(t){return function(){this.removeAttribute(t);}}function Ae(t){return function(){this.removeAttributeNS(t.space,t.local);}}function Se(t,e){return function(){this.setAttribute(t,e);}}function Ee(t,e){return function(){this.setAttributeNS(t.space,t.local,e);}}function Ce(t,e){return function(){var i=e.apply(this,arguments);i==null?this.removeAttribute(t):this.setAttribute(t,i);}}function ze(t,e){return function(){var i=e.apply(this,arguments);i==null?this.removeAttributeNS(t.space,t.local):this.setAttributeNS(t.space,t.local,i);}}function ke(t,e){var i=dt(t);if(arguments.length<2){var n=this.node();return i.local?n.getAttributeNS(i.space,i.local):n.getAttribute(i)}return this.each((e==null?i.local?Ae:xe:typeof e=="function"?i.local?ze:Ce:i.local?Ee:Se)(i,e))}function wt(t){return t.ownerDocument&&t.ownerDocument.defaultView||t.document&&t||t.defaultView}function Ie(t){return function(){this.style.removeProperty(t);}}function Ne(t,e,i){return function(){this.style.setProperty(t,e,i);}}function Pe(t,e,i){return function(){var n=e.apply(this,arguments);n==null?this.style.removeProperty(t):this.style.setProperty(t,n,i);}}function Be(t,e,i){return arguments.length>1?this.each((e==null?Ie:typeof e=="function"?Pe:Ne)(t,e,i??"")):Te(this.node(),t)}function Te(t,e){return t.style.getPropertyValue(e)||wt(t).getComputedStyle(t,null).getPropertyValue(e)}function Me(t){return function(){delete this[t];}}function Re(t,e){return function(){this[t]=e;}}function De(t,e){return function(){var i=e.apply(this,arguments);i==null?delete this[t]:this[t]=i;}}function Le(t,e){return arguments.length>1?this.each((e==null?Me:typeof e=="function"?De:Re)(t,e)):this.node()[t]}function yt(t){return t.trim().split(/^|\s+/)}function et(t){return t.classList||new bt(t)}function bt(t){this._node=t,this._names=yt(t.getAttribute("class")||"");}bt.prototype={add:function(t){var e=this._names.indexOf(t);e<0&&(this._names.push(t),this._node.setAttribute("class",this._names.join(" ")));},remove:function(t){var e=this._names.indexOf(t);e>=0&&(this._names.splice(e,1),this._node.setAttribute("class",this._names.join(" ")));},contains:function(t){return this._names.indexOf(t)>=0}};function xt(t,e){for(var i=et(t),n=-1,s=e.length;++n<s;)i.add(e[n]);}function At(t,e){for(var i=et(t),n=-1,s=e.length;++n<s;)i.remove(e[n]);}function Fe(t){return function(){xt(this,t);}}function Ue(t){return function(){At(this,t);}}function Oe(t,e){return function(){(e.apply(this,arguments)?xt:At)(this,t);}}function Ve(t,e){var i=yt(t+"");if(arguments.length<2){for(var n=et(this.node()),s=-1,r=i.length;++s<r;)if(!n.contains(i[s]))return  false;return  true}return this.each((typeof e=="function"?Oe:e?Fe:Ue)(i,e))}function Xe(){this.textContent="";}function qe(t){return function(){this.textContent=t;}}function Ye(t){return function(){var e=t.apply(this,arguments);this.textContent=e??"";}}function He(t){return arguments.length?this.each(t==null?Xe:(typeof t=="function"?Ye:qe)(t)):this.node().textContent}function Ge(){this.innerHTML="";}function Ke(t){return function(){this.innerHTML=t;}}function We(t){return function(){var e=t.apply(this,arguments);this.innerHTML=e??"";}}function Je(t){return arguments.length?this.each(t==null?Ge:(typeof t=="function"?We:Ke)(t)):this.node().innerHTML}function Qe(){this.nextSibling&&this.parentNode.appendChild(this);}function Ze(){return this.each(Qe)}function je(){this.previousSibling&&this.parentNode.insertBefore(this,this.parentNode.firstChild);}function $e(){return this.each(je)}function tn(t){var e=typeof t=="function"?t:_t(t);return this.select(function(){return this.appendChild(e.apply(this,arguments))})}function en(){return null}function nn(t,e){var i=typeof t=="function"?t:_t(t),n=e==null?en:typeof e=="function"?e:gt(e);return this.select(function(){return this.insertBefore(i.apply(this,arguments),n.apply(this,arguments)||null)})}function sn(){var t=this.parentNode;t&&t.removeChild(this);}function on(){return this.each(sn)}function rn(){var t=this.cloneNode(false),e=this.parentNode;return e?e.insertBefore(t,this.nextSibling):t}function ln(){var t=this.cloneNode(true),e=this.parentNode;return e?e.insertBefore(t,this.nextSibling):t}function an(t){return this.select(t?ln:rn)}function un(t){return arguments.length?this.property("__data__",t):this.node().__data__}function cn(t){return function(e){t.call(this,e,this.__data__);}}function fn(t){return t.trim().split(/^|\s+/).map(function(e){var i="",n=e.indexOf(".");return n>=0&&(i=e.slice(n+1),e=e.slice(0,n)),{type:e,name:i}})}function hn(t){return function(){var e=this.__on;if(e){for(var i=0,n=-1,s=e.length,r;i<s;++i)r=e[i],(!t.type||r.type===t.type)&&r.name===t.name?this.removeEventListener(r.type,r.listener,r.options):e[++n]=r;++n?e.length=n:delete this.__on;}}}function pn(t,e,i){return function(){var n=this.__on,s,r=cn(e);if(n){for(var u=0,l=n.length;u<l;++u)if((s=n[u]).type===t.type&&s.name===t.name){this.removeEventListener(s.type,s.listener,s.options),this.addEventListener(s.type,s.listener=r,s.options=i),s.value=e;return}}this.addEventListener(t.type,r,i),s={type:t.type,name:t.name,value:e,listener:r,options:i},n?n.push(s):this.__on=[s];}}function dn(t,e,i){var n=fn(t+""),s,r=n.length,u;if(arguments.length<2){var l=this.node().__on;if(l){for(var o=0,c=l.length,f;o<c;++o)for(s=0,f=l[o];s<r;++s)if((u=n[s]).type===f.type&&u.name===f.name)return f.value}return}for(l=e?pn:hn,s=0;s<r;++s)this.each(l(n[s],e,i));return this}function St(t,e,i){var n=wt(t),s=n.CustomEvent;typeof s=="function"?s=new s(e,i):(s=n.document.createEvent("Event"),i?(s.initEvent(e,i.bubbles,i.cancelable),s.detail=i.detail):s.initEvent(e,false,false)),t.dispatchEvent(s);}function _n(t,e){return function(){return St(this,t,e)}}function gn(t,e){return function(){return St(this,t,e.apply(this,arguments))}}function mn(t,e){return this.each((typeof e=="function"?gn:_n)(t,e))}function*vn(){for(var t=this._groups,e=0,i=t.length;e<i;++e)for(var n=t[e],s=0,r=n.length,u;s<r;++s)(u=n[s])&&(yield u);}function M(t,e){this._groups=t,this._parents=e;}function yn(){return this}M.prototype={constructor:M,select:Vt,selectAll:Gt,selectChild:Zt,selectChildren:ee,filter:ne,data:ae,enter:ie,exit:ce,join:fe,merge:he,selection:yn,order:pe,sort:de,call:ge,nodes:me,node:ve,size:we,empty:ye,each:be,attr:ke,style:Be,property:Le,classed:Ve,text:He,html:Je,raise:Ze,lower:$e,append:tn,insert:nn,remove:on,clone:an,datum:un,on:dn,dispatch:mn,[Symbol.iterator]:vn};function Et(t,e){t.component(i=>{let {position:s=.5,disabled:r=false,slider_color:u="var(--border-color-primary)",image_size:l={top:0,left:0,width:0,height:0},el:o=void 0,parent_el:c=void 0,children:f}=e,g=0,y=false;i.push('<div class="wrap svelte-b2bl92" role="none"><div class="content svelte-b2bl92">'),f?(i.push("<!--[-->"),f(i),i.push("<!---->")):i.push("<!--[!-->"),i.push(`<!--]--></div> <div${attr_class("outer svelte-b2bl92",void 0,{disabled:r,grab:y})} data-testid="slider" role="none"${attr_style(`transform: translateX(${stringify(g)}px)`)}><span${attr_class("icon-wrap svelte-b2bl92",void 0,{active:y,disabled:r})}><span class="icon left svelte-b2bl92">◢</span><span class="icon center svelte-b2bl92"${attr_style("",{"--color":u})}></span><span class="icon right svelte-b2bl92">◢</span></span> <div class="inner svelte-b2bl92"${attr_style("",{"--color":u})}></div></div></div>`),bind_props(e,{position:s,el:o,parent_el:c});});}function J(t,e){t.component(i=>{let{src:n=void 0,fullscreen:s=false,fixed:r=false,transform:u="translate(0px, 0px) scale(1)",img_el:l=void 0,hidden:o=false,variant:c="upload",max_height:f=500,onload:v,$$slots:g,$$events:y,...b}=e;i.push(`<img${attributes({src:n,"data-testid":"imageslider-image",...b},"svelte-j3ek2n",{fixed:r,hidden:o,preview:c==="preview",slider:c==="upload",fullscreen:s,small:!s},{transform:u,"max-height":f&&!s?`${f}px`:null})} onload="this.__e=event" onerror="this.__e=event"/>`),bind_props(e,{img_el:l});});}function Nn(t,e){t.component(i$1=>{var n;let{value:s=[null,null],label:r$1=void 0,show_download_button:u$1=true,show_label:l$1,i18n:o$1,position:c=.5,layer_images:f=true,show_single:v$1=false,slider_color:g,show_fullscreen_button:y$1=true,fullscreen:b=false,buttons:P=null,on_custom_button_click:S=null,el_width:_=0,max_height:p$1,interactive:k$1=true,onclear:a,onfullscreen:h}=e,x,d,C=tweened({x:0,y:0,z:1},{duration:75}),T,B=0,I={top:0,left:0,width:0,height:0},F=w$1(c,B,I.width,I.left,store_get(n??={},"$transform",C).x,store_get(n??={},"$transform",C).z),z=f?`clip-path: inset(0 0 0 ${F*100}%)`:"";function w$1(N,E,D,Ct,zt,kt){return (N*D+Ct-zt)/kt/E}let A=null;function R(N){I=N;}let L=true,O;function Y(N){k(N,{show_label:l$1,Icon:i,label:r$1||o$1("image.image")}),N.push("<!----> "),(s===null||s[0]===null||s[1]===null)&&!v$1?(N.push("<!--[-->"),p(N,{unpadded_box:true,size:"large",children:E=>{i(E);},$$slots:{default:true}})):(N.push("<!--[!-->"),N.push('<div class="image-container svelte-1880bc6">'),y(N,{buttons:P,on_custom_button_click:S,children:E=>{w(E,{Icon:r,label:o$1("common.undo"),disabled:store_get(n??={},"$transform",C).z===1,onclick:()=>A?.reset_zoom()}),E.push("<!----> "),y$1?(E.push("<!--[-->"),v(E,{fullscreen:b,onclick:D=>{b=D,h?.(D);}})):E.push("<!--[!-->"),E.push("<!--]--> "),u$1?(E.push("<!--[-->"),u(E,{href:s[1]?.url,download:s[1]?.orig_name||"image",children:D=>{w(D,{Icon:l,label:o$1("common.download")});},$$slots:{default:true}})):E.push("<!--[!-->"),E.push("<!--]--> "),k$1?(E.push("<!--[-->"),w(E,{Icon:o,label:"Remove Image",onclick:D=>{s=[null,null],a?.(),D.stopPropagation();}})):E.push("<!--[!-->"),E.push("<!--]-->");}}),N.push(`<!----> <div${attr_class("slider-wrap svelte-1880bc6",void 0,{limit_height:!b})}>`),Et(N,{slider_color:g,image_size:I,get position(){return c},set position(E){c=E,L=false;},get el(){return d},set el(E){d=E,L=false;},get parent_el(){return T},set parent_el(E){T=E,L=false;},children:E=>{J(E,{src:s?.[0]?.url,alt:"",loading:"lazy",variant:"preview",transform:`translate(${stringify(store_get(n??={},"$transform",C).x)}px, ${stringify(store_get(n??={},"$transform",C).y)}px) scale(${stringify(store_get(n??={},"$transform",C).z)})`,fullscreen:b,max_height:p$1,onload:R,get img_el(){return x},set img_el(D){x=D,L=false;}}),E.push("<!----> "),J(E,{variant:"preview",fixed:f,hidden:!s?.[1]?.url,src:s?.[1]?.url,alt:"",loading:"lazy",style:`${stringify(z)}; background: var(--block-background-fill);`,transform:`translate(${stringify(store_get(n??={},"$transform",C).x)}px, ${stringify(store_get(n??={},"$transform",C).y)}px) scale(${stringify(store_get(n??={},"$transform",C).z)})`,fullscreen:b,max_height:p$1,onload:R}),E.push("<!---->");},$$slots:{default:true}}),N.push("<!----></div></div>")),N.push("<!--]-->");}do L=true,O=i$1.copy(),Y(O);while(!L);i$1.subsume(O),n&&unsubscribe_stores(n),bind_props(e,{value:s,position:c,fullscreen:b,el_width:_});});}function Pn(t,e){t.component(i=>{let{onremove_image:n}=e;i.push('<div class="svelte-2ufkjh">'),w(i,{Icon:o,label:"Remove Image",onclick:s=>{n?.(),s.stopPropagation();}}),i.push("<!----></div>");});}function Bn(t,e){t.component(i$1=>{let{value:n=[null,null],label:s=void 0,show_label:r,root:u$1,position:l$1=.5,upload_count:o=2,show_download_button:c=true,slider_color:f,upload:v,stream_handler:g,max_file_size:y=null,i18n:b,max_height:P,upload_promise:S=void 0,dragging:_=false,onclear:p$1,ondrag:k$1,onupload:a,children:h}=e,x=n||[null,null],d,C=0;async function T(z,w){const A=Array.isArray(z)?z:[z],R=[n[0],n[1]];A.length>1?R[w]=A[0]:R[w]=A[w],n=R,await tick(),a?.(R);}let B=true,I;function F(z){k(z,{show_label:r,Icon:i,label:s||b("image.image")}),z.push('<!----> <div data-testid="image" class="image-container svelte-1c8zs50">'),n?.[0]?.url||n?.[1]?.url?(z.push("<!--[-->"),Pn(z,{onremove_image:()=>{l$1=.5,n=[null,null],p$1?.();}})):z.push("<!--[!-->"),z.push("<!--]--> "),n?.[1]?.url?(z.push("<!--[-->"),z.push('<div class="icon-buttons svelte-1c8zs50">'),c?(z.push("<!--[-->"),u(z,{href:n[1].url,download:n[1].orig_name||"image",children:w$1=>{w(w$1,{Icon:l});},$$slots:{default:true}})):z.push("<!--[!-->"),z.push("<!--]--></div>")):z.push("<!--[!-->"),z.push("<!--]--> "),Et(z,{disabled:o==2||!n?.[0],slider_color:f,get position(){return l$1},set position(w){l$1=w,B=false;},children:w=>{w.push(`<div${attr_class("upload-wrap svelte-1c8zs50",void 0,{"side-by-side":o===2})}${attr_style("",{display:o===2?"flex":"block"})}>`),x?.[0]?(w.push("<!--[!-->"),J(w,{variant:"upload",src:x[0]?.url,alt:"",max_height:P,get img_el(){return d},set img_el(A){d=A,B=false;}})):(w.push("<!--[-->"),w.push(`<div${attr_class("wrap svelte-1c8zs50",void 0,{"half-wrap":o===1})}>`),ee$1(w,{filetype:"image/*",onload:A=>T(A,0),disable_click:!!n?.[0],root:u$1,file_count:"multiple",upload:v,stream_handler:g,max_file_size:y,get upload_promise(){return S},set upload_promise(A){S=A,B=false;},get dragging(){return _},set dragging(A){_=A,B=false;},children:A=>{h?(A.push("<!--[-->"),h(A),A.push("<!---->")):A.push("<!--[!-->"),A.push("<!--]-->");},$$slots:{default:true}}),w.push("<!----></div>")),w.push("<!--]--> "),!x?.[1]&&o===2?(w.push("<!--[-->"),ee$1(w,{filetype:"image/*",onload:A=>T(A,1),disable_click:!!n?.[1],root:u$1,file_count:"multiple",upload:v,stream_handler:g,max_file_size:y,get upload_promise(){return S},set upload_promise(A){S=A,B=false;},get dragging(){return _},set dragging(A){_=A,B=false;},children:A=>{h?(A.push("<!--[-->"),h(A),A.push("<!---->")):A.push("<!--[!-->"),A.push("<!--]-->");},$$slots:{default:true}})):(w.push("<!--[!-->"),!x?.[1]&&o===1?(w.push("<!--[-->"),w.push(`<div${attr_class("empty-wrap fixed svelte-1c8zs50",void 0,{"white-icon":!n?.[0]?.url})}${attr_style("",{width:`${stringify(C*(1-l$1))}px`,transform:`translateX(${stringify(C*l$1)}px)`})}>`),p(w,{unpadded_box:true,size:"large",children:A=>{i(A);},$$slots:{default:true}}),w.push("<!----></div>")):(w.push("<!--[!-->"),x?.[1]?(w.push("<!--[-->"),J(w,{variant:"upload",src:x[1].url,alt:"",fixed:o===1,transform:"translate(0px, 0px) scale(1)",max_height:P})):w.push("<!--[!-->"),w.push("<!--]-->")),w.push("<!--]-->")),w.push("<!--]--></div>");},$$slots:{default:true}}),z.push("<!----></div>");}do B=true,I=i$1.copy(),F(I);while(!B);i$1.subsume(I),bind_props(e,{value:n,position:l$1,upload_promise:S,dragging:_});});}function Tn(t,e){t.component(i=>{let{value:n=[null,null],upload:s,stream_handler:r,label:u,show_label:l,i18n:o,root:c,upload_count:f=1,dragging:v=false,max_height:g,max_file_size:y=null,upload_promise:b=void 0,onclear:P,ondrag:S,onupload:_,children:p}=e,k=true,a;function h(x){Bn(x,{slider_color:"var(--border-color-primary)",position:.5,root:c,onclear:P,ondrag:d=>{v=d,S?.(d);},onupload:_,label:u,show_label:l,upload_count:f,stream_handler:r,upload:s,max_file_size:y,max_height:g,i18n:o,get upload_promise(){return b},set upload_promise(d){b=d,k=false;},get value(){return n},set value(d){n=d,k=false;},get dragging(){return v},set dragging(d){v=d,k=false;},children:d=>{p?(d.push("<!--[-->"),p(d),d.push("<!---->")):d.push("<!--[!-->"),d.push("<!--]-->");},$$slots:{default:true}});}do k=true,a=i.copy(),h(a);while(!k);i.subsume(a),bind_props(e,{value:n,dragging:v,upload_promise:b});});}function li(t,e){t.component(i=>{let n;class s extends Os{async get_data(){return n&&(await n,await tick()),await super.get_data()}}const{$$slots:r,$$events:u,...l}=e,o=new s(l);let c=false,f=false,v=o.props.value??[null,null],g=Math.max(0,Math.min(100,o.props.slider_position))/100;o.watch_for_change();let y=true,b;function P(S){!o.shared.interactive||v?.[1]&&v?.[0]?(S.push("<!--[-->"),G$1(S,{visible:o.shared.visible,variant:"solid",border_mode:f?"focus":"base",padding:false,elem_id:o.shared.elem_id,elem_classes:o.shared.elem_classes,height:o.props.height||void 0,width:o.props.width,allow_overflow:false,container:o.shared.container,scale:o.shared.scale,min_width:o.shared.min_width,get fullscreen(){return c},set fullscreen(_){c=_,y=false;},children:_=>{ss(_,spread_props([{autoscroll:o.shared.autoscroll,i18n:o.i18n},o.shared.loading_status])),_.push("<!----> "),Nn(_,{onclear:()=>{o.dispatch("clear"),o.dispatch("input");},onfullscreen:p=>{c=p;},fullscreen:c,interactive:o.shared.interactive,label:o.shared.label,show_label:o.shared.show_label,show_download_button:o.props.buttons.some(p=>typeof p=="string"&&p==="download"),i18n:o.i18n,show_fullscreen_button:o.props.buttons.some(p=>typeof p=="string"&&p==="fullscreen"),buttons:o.props.buttons,on_custom_button_click:p=>{o.dispatch("custom_button_click",{id:p});},position:g,slider_color:o.props.slider_color,max_height:o.props.max_height,get value(){return v},set value(p){v=p,y=false;}}),_.push("<!---->");},$$slots:{default:true}})):(S.push("<!--[!-->"),G$1(S,{visible:o.shared.visible,variant:v?.[0]||v?.[1]?"solid":"dashed",border_mode:f?"focus":"base",padding:false,elem_id:o.shared.elem_id,elem_classes:o.shared.elem_classes,height:o.props.height||void 0,width:o.props.width,allow_overflow:false,container:o.shared.container,scale:o.shared.scale,min_width:o.shared.min_width,children:_=>{ss(_,spread_props([{autoscroll:o.shared.autoscroll,i18n:o.i18n},o.shared.loading_status,{on_clear_status:()=>o.dispatch("clear_status",o.shared.loading_status)}])),_.push("<!----> "),Tn(_,{root:o.shared.root,onclear:()=>{o.dispatch("clear"),o.dispatch("input");},ondrag:p=>f=p,onupload:()=>{o.dispatch("upload"),o.dispatch("input");},label:o.shared.label,show_label:o.shared.show_label,upload_count:o.props.upload_count,max_file_size:o.shared.max_file_size,i18n:o.i18n,upload:(...p)=>o.shared.client.upload(...p),stream_handler:o.shared.client?.stream,max_height:o.props.max_height,get upload_promise(){return n},set upload_promise(p){n=p,y=false;},get value(){return v},set value(p){v=p,y=false;},get dragging(){return f},set dragging(p){f=p,y=false;},children:p=>{p.push("<!--[-->"),k$1(p,{i18n:o.i18n,type:"image",placeholder:o.props.placeholder}),p.push("<!--]-->");},$$slots:{default:true}}),_.push("<!---->");},$$slots:{default:true}})),S.push("<!--]-->");}do y=true,b=i.copy(),P(b);while(!y);i.subsume(b);});}

export { li as default };
//# sourceMappingURL=Index57-BisCGOoi.js.map

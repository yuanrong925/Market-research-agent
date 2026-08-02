import './async-D55cHugf.js';
import { c as spread_props, f as attr_class, a as attr, g as attr_style, i as stringify, s as slot, d as bind_props } from './index-6p4UEISu.js';
import { O as Os } from './2-DQcH4kU_.js';
import { s as ss } from './index3-CiV5UCJA.js';
import { y } from './Index.svelte_svelte_type_style_lang-DPqoVNph.js';
import './escaping-CBnpiEl5.js';
import './context-CBkBucIx.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './index-Cg-Pg6j3.js';
import './IconButton-DoTLxBZ_.js';
import './Clear-D7Yjckqz.js';

function B(h,n){h.component(i=>{let {open:_=true,width:d,position:a="left",elem_classes:e=[],elem_id:l="",onexpand:u=()=>{},oncollapse:b=()=>{}}=n,o=false,g=typeof d=="number"?`${d}px`:d,f=false;let w=e?.join(" ")||"";i.push(`<div${attr_class(`sidebar ${stringify(w)}`,"svelte-1uruprb",{open:o,right:a==="right","reduce-motion":f})}${attr("id",l)}${attr_style(`width: ${stringify(g)}; ${stringify(a)}: calc(${stringify(g)} * -1)`)}><button class="toggle-button svelte-1uruprb" aria-label="Toggle Sidebar"><div class="chevron svelte-1uruprb"><span class="chevron-left svelte-1uruprb"></span></div></button> <div class="sidebar-content svelte-1uruprb"><!--[-->`),slot(i,n,"default",{}),i.push("<!--]--></div></div>"),bind_props(n,{open:_,position:a});});}function Q(h,n){h.component(i=>{const{$$slots:_,$$events:d,...a}=n,e=new Os(a);let l=true,u;function b(o){ss(o,spread_props([{autoscroll:e.shared.autoscroll,i18n:e.i18n},e.shared.loading_status])),o.push("<!----> "),e.shared.visible?(o.push("<!--[-->"),B(o,{width:e.props.width,onexpand:()=>e.dispatch("expand"),oncollapse:()=>e.dispatch("collapse"),elem_classes:e.shared.elem_classes,elem_id:e.shared.elem_id,get open(){return e.props.open},set open(s){e.props.open=s,l=false;},get position(){return e.props.position},set position(s){e.props.position=s,l=false;},children:s=>{y(s,{children:r=>{r.push("<!--[-->"),slot(r,n,"default",{}),r.push("<!--]-->");},$$slots:{default:true}});},$$slots:{default:true}})):o.push("<!--[!-->"),o.push("<!--]-->");}do l=true,u=i.copy(),b(u);while(!l);i.subsume(u);});}

export { Q as default };
//# sourceMappingURL=Index36-Cpddis2y.js.map

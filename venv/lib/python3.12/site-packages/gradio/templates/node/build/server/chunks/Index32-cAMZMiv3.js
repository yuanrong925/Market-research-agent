import './async-D55cHugf.js';
import { c as spread_props, f as attr_class, g as attr_style, s as slot, d as bind_props } from './index-6p4UEISu.js';
import { G } from './Block-DFkF8ric.js';
import { O as Os } from './2-DQcH4kU_.js';
import { s as ss } from './index3-CiV5UCJA.js';
import { e as escape_html } from './escaping-CBnpiEl5.js';
import { y } from './Index.svelte_svelte_type_style_lang-DPqoVNph.js';
import './context-CBkBucIx.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './index-Cg-Pg6j3.js';
import './IconButton-DoTLxBZ_.js';
import './Clear-D7Yjckqz.js';

function x(p,a){p.component(l=>{let{open:i=true,label:d="",onexpand:c,oncollapse:u}=a;l.push(`<button${attr_class("label-wrap svelte-e5lyqv",void 0,{open:i})}><span class="svelte-e5lyqv">${escape_html(d)}</span> <span class="icon svelte-e5lyqv"${attr_style("",{transform:i?"rotate(0)":"rotate(90deg)"})}>▼</span></button> <div data-testid="accordion-content"${attr_style("",{display:i?"block":"none"})}><!--[-->`),slot(l,a,"default",{}),l.push("<!--]--></div>"),bind_props(a,{open:i});});}function I(p,a){p.component(l=>{let{$$slots:i,$$events:d,...c}=a;class u extends Os{set_data(e){"open"in e&&e.open!==this.props.open&&(e.open?(this.dispatch("expand"),this.dispatch("gradio_expand")):this.dispatch("collapse")),super.set_data(e),this.shared.loading_status.status="complete";}}const s=new u(c);let h=s.shared.label||"",r=[...s.shared.elem_classes||[],"gr-accordion"],m=s.shared.visible===true?true:"hidden";G(l,{elem_id:s.shared.elem_id,elem_classes:r,visible:m,children:o=>{s.shared.loading_status?(o.push("<!--[-->"),ss(o,spread_props([{autoscroll:s.shared.autoscroll,i18n:s.i18n},s.shared.loading_status]))):o.push("<!--[!-->"),o.push("<!--]--> "),x(o,{label:h,open:s.props.open,onexpand:()=>{s.dispatch("expand"),s.dispatch("gradio_expand");},oncollapse:()=>s.dispatch("collapse"),children:e=>{y(e,{children:n=>{n.push("<!--[-->"),slot(n,a,"default",{}),n.push("<!--]-->");},$$slots:{default:true}});},$$slots:{default:true}}),o.push("<!---->");},$$slots:{default:true}});});}

export { I as default };
//# sourceMappingURL=Index32-cAMZMiv3.js.map

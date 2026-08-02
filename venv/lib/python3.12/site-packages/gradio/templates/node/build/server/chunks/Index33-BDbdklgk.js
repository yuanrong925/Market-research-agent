import './async-D55cHugf.js';
import { a as attr } from './index-6p4UEISu.js';
import { e as escape_html } from './escaping-CBnpiEl5.js';
import { O as Os } from './2-DQcH4kU_.js';
import { B as B$1 } from './Button-DdHM7Ous.js';
import './context-CBkBucIx.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './index-Cg-Pg6j3.js';
import './Image-DYkfMGqQ.js';

function B(a,o){a.component(t=>{let{elem_id:d="",elem_classes:u=[],visible:n=true,variant:s="secondary",size:c="lg",value:e,icon:h,disabled:f=false,scale:_=null,min_width:v=void 0,on_click:b,children:m}=o;function w(){if(b?.(),!e?.url)return;let i;if(!e.orig_name&&e.url){const r=e.url.split("/");i=r[r.length-1],i=i.split("?")[0].split("#")[0];}else i=e.orig_name;const l=document.createElement("a");l.href=e.url,l.download=i||"file",document.body.appendChild(l),l.click(),document.body.removeChild(l);}B$1(t,{size:c,variant:s,elem_id:d,elem_classes:u,visible:n,onclick:w,scale:_,min_width:v,disabled:f,children:i=>{h?(i.push("<!--[-->"),i.push(`<img class="button-icon svelte-4ac0fl"${attr("src",h.url)}${attr("alt",`${e} icon`)}/>`)):i.push("<!--[!-->"),i.push("<!--]--> "),m?(i.push("<!--[-->"),m(i),i.push("<!---->")):i.push("<!--[!-->"),i.push("<!--]-->");}});});}function D(a,o){a.component(t=>{const{$$slots:d,$$events:u,...n}=o,s=new Os(n);s.watch_for_change(),B(t,{value:s.props.value,variant:s.props.variant,elem_id:s.shared.elem_id,elem_classes:s.shared.elem_classes,size:s.props.size,scale:s.shared.scale,icon:s.props.icon,min_width:s.shared.min_width,visible:s.shared.visible,disabled:!s.shared.interactive,on_click:()=>s.dispatch("click"),children:c=>{c.push(`<!---->${escape_html(s.shared.label??"")}`);}});});}

export { B as BaseButton, D as default };
//# sourceMappingURL=Index33-BDbdklgk.js.map

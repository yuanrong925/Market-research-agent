import './async-D55cHugf.js';
import { a as attr, f as attr_class, g as attr_style, i as stringify, b as store_get, s as slot, u as unsubscribe_stores } from './index-6p4UEISu.js';
import { O as Os } from './2-DQcH4kU_.js';
import { g as getContext } from './context-CBkBucIx.js';
import { A } from './Walkthrough.svelte_svelte_type_style_lang-BUANkEGR.js';
import { y as y$1 } from './Index.svelte_svelte_type_style_lang-DPqoVNph.js';
import './escaping-CBnpiEl5.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './index-Cg-Pg6j3.js';
import './index3-CiV5UCJA.js';
import './IconButton-DoTLxBZ_.js';
import './Clear-D7Yjckqz.js';

function y(d,l){d.component(i=>{var o;let{elem_id:r="",elem_classes:n=[],label:e,id:s,visible:c,interactive:_,order:B,scale:a,component_id:p,onselect:T}=l;const{register_tab:w,unregister_tab:I,selected_tab:b,selected_tab_index:C}=getContext(A);let u=s??p;JSON.stringify({label:e,id:u,elem_id:r,visible:c,interactive:_,scale:a,component_id:p});let f=c!==false&&c!=="hidden";i.push(`<div${attr("id",r)}${attr_class(`tabitem ${stringify(n.join(" "))}`,"svelte-dmtrd3",{"grow-children":a>=1})} role="tabpanel"${attr_style("",{display:store_get(o??={},"$selected_tab",b)===u&&f?"flex":"none","flex-grow":a})}>`),y$1(i,{scale:a>=1?a:null,children:m=>{m.push("<!--[-->"),slot(m,l,"default",{}),m.push("<!--]-->");},$$slots:{default:true}}),i.push("<!----></div>"),o&&unsubscribe_stores(o);});}function O(d,l){d.component(i=>{let{$$slots:o,$$events:r,...n}=l;const e=new Os(n);y(i,{elem_id:e.shared.elem_id,elem_classes:e.shared.elem_classes,label:e.shared.label,visible:e.shared.visible,interactive:e.shared.interactive,id:e.props.id,order:e.props.order,scale:e.props.scale,component_id:e.props.component_id,onselect:s=>e.dispatch("select",s),children:s=>{s.push("<!--[-->"),slot(s,l,"default",{}),s.push("<!--]-->");},$$slots:{default:true}});});}

export { y as BaseTabItem, O as default };
//# sourceMappingURL=Index37-CGt-zWoy.js.map

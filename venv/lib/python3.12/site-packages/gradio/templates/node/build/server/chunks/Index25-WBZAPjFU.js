import './async-D55cHugf.js';
import { c as spread_props, f as attr_class, g as attr_style } from './index-6p4UEISu.js';
import { O as Os, B as Bs, R as Rs } from './2-DQcH4kU_.js';
import D$1 from './HTML-DTmZ7ouF.js';
import { s as ss } from './index3-CiV5UCJA.js';
import { i } from './Code-CrFuQ3ob.js';
import { G } from './Block-DFkF8ric.js';
import { k } from './BlockLabel-Cwr2q1Ma.js';
import { y } from './IconButtonWrapper-DtthXzCF.js';
export { default as BaseExample } from './Example18-xlhXbNc9.js';
import './escaping-CBnpiEl5.js';
import './context-CBkBucIx.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './index-Cg-Pg6j3.js';
import 'fs';
import './IconButton-DoTLxBZ_.js';
import './Clear-D7Yjckqz.js';
import './html-CfyvkLET.js';

function D(n,h){n.component(d=>{let{$$slots:E,$$events:I,...r}=h,c=r.children;const s=new Os(r);let u={value:s.props.value??"",label:s.shared.label,visible:s.shared.visible,...s.props.props};s.props.value;let i$1=[];function _(a,e){const t=Array.isArray(a)?a:[a];i$1.push({props:t,callback:e});}function m(a){const e=new Set;for(const t of i$1)t.props.some(o=>a.includes(o))&&e.add(t);for(const t of e)try{t.callback();}catch(o){console.error("Error in watch callback:",o);}}async function f(a){try{const e=await Rs([a]),t=await s.shared.client.upload(e,s.shared.root,void 0,s.shared.max_file_size??void 0);if(t&&t[0])return {path:t[0].path,url:t[0].url};throw new Error("Upload failed")}catch(e){throw s.dispatch("error",e instanceof Error?e.message:String(e)),e}}G(d,{visible:s.shared.visible,elem_id:s.shared.elem_id,elem_classes:s.shared.elem_classes,container:s.shared.container,padding:s.props.padding!==false,overflow_behavior:"visible",children:a=>{s.shared.show_label&&s.props.buttons&&s.props.buttons.length>0?(a.push("<!--[-->"),y(a,{buttons:s.props.buttons,on_custom_button_click:e=>{s.dispatch("custom_button_click",{id:e});}})):a.push("<!--[!-->"),a.push("<!--]--> "),s.shared.show_label?(a.push("<!--[-->"),k(a,{Icon:i,show_label:s.shared.show_label,label:s.shared.label,float:true})):a.push("<!--[!-->"),a.push("<!--]--> "),ss(a,spread_props([{autoscroll:s.shared.autoscroll,i18n:s.i18n},s.shared.loading_status,{variant:"center",on_clear_status:()=>s.dispatch("clear_status",s.shared.loading_status)}])),a.push(`<!----> <div${attr_class("html-container svelte-1jts93g",void 0,{pending:s.shared.loading_status?.status==="pending"&&s.shared.loading_status?.show_progress!=="hidden","label-padding":s.shared.show_label??void 0})}${attr_style("",{"min-height":s.props.min_height&&s.shared.loading_status?.status!=="pending"?Bs(s.props.min_height):void 0,"max-height":s.props.max_height?Bs(s.props.max_height):void 0,"overflow-y":s.props.max_height?"auto":void 0})}>`),D$1(a,{props:u,html_template:s.props.html_template,css_template:s.props.css_template,js_on_load:s.props.js_on_load,elem_classes:s.shared.elem_classes,visible:s.shared.visible==="hidden"?false:s.shared.visible,autoscroll:s.shared.autoscroll,apply_default_css:s.props.apply_default_css,head:s.props.head,component_class_name:s.props.component_class_name,upload:f,server:s.shared.server,watch_fn:_,fire_watchers:m,children:e=>{c?.(e);}}),a.push("<!----></div>");},$$slots:{default:true}});});}

export { D$1 as BaseHTML, D as default };
//# sourceMappingURL=Index25-WBZAPjFU.js.map

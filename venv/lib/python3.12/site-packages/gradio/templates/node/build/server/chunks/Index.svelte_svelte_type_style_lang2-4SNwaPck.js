import './async-D55cHugf.js';
import { f as attr_class, a as attr, g as attr_style, i as stringify } from './index-6p4UEISu.js';
import { B as Bs } from './2-DQcH4kU_.js';
import { e } from './Check-C7_ZsXgh.js';
import { h } from './Copy-B8YOhH7c.js';
import { w } from './IconButton-DoTLxBZ_.js';
import { y } from './IconButtonWrapper-DtthXzCF.js';
import { t as tn } from './MarkdownCode-BqWkJWKF.js';

function J(m,r){m.component(t=>{let{elem_classes:c=[],visible:f=true,value:e$1,min_height:s=void 0,rtl:u=false,sanitize_html:d=true,line_breaks:h$1=false,latex_delimiters:_=[],header_links:g=false,height:n=void 0,show_copy_button:v=false,loading_status:y$1=void 0,theme_mode:k,onchange:z=()=>{},oncopy:b=l=>{}}=r,o=false,a;async function w$1(){"clipboard"in navigator&&(await navigator.clipboard.writeText(e$1),b({value:e$1}),C());}function C(){o=true,a&&clearTimeout(a),a=setTimeout(()=>{o=false;},1e3);}t.push(`<div${attr_class(`prose ${stringify(c?.join(" ")||"")}`,"svelte-1xjkzpp",{hide:!f})} data-testid="markdown"${attr("dir",u?"rtl":"ltr")}${attr_style(n?`max-height: ${Bs(n)}; overflow-y: auto;`:"",{"min-height":s&&y$1?.status!=="pending"?Bs(s):void 0})}>`),v?(t.push("<!--[-->"),y(t,{children:l=>{w(l,{Icon:o?e:h,onclick:w$1,label:o?"Copied conversation":"Copy conversation"});}})):t.push("<!--[!-->"),t.push("<!--]--> "),tn(t,{message:e$1,latex_delimiters:_,sanitize_html:d,line_breaks:h$1,chatbot:false,header_links:g,theme_mode:k}),t.push("<!----></div>");});}

export { J };
//# sourceMappingURL=Index.svelte_svelte_type_style_lang2-4SNwaPck.js.map

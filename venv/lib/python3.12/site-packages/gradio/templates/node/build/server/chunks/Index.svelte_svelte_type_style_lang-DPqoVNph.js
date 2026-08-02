import './async-D55cHugf.js';
import { a as attr, f as attr_class, g as attr_style, i as stringify, c as spread_props, s as slot } from './index-6p4UEISu.js';
import { s as ss } from './index3-CiV5UCJA.js';

function y(o,a){o.component(s=>{let{$$slots:h,$$events:d,...t}=a,u=t.scale??null,p=t.min_width??0,n=t.elem_id??"",m=t.elem_classes??[],c=t.visible??true,e=t.variant??"default",l=t.loading_status;t.show_progress,s.push(`<div${attr("id",n)}${attr_class(`column ${stringify(m.join(" "))}`,"svelte-siq5d6",{compact:e==="compact",panel:e==="panel",hide:!c})}${attr_style("",{"flex-grow":u,"min-width":`calc(min(${stringify(p)}px, 100%))`})}>`),l&&l.show_progress?(s.push("<!--[-->"),ss(s,spread_props([{autoscroll:t.autoscroll??false,i18n:t.i18n??(_=>_)},l,{queue_size:l.queue_size??null,status:l?l.status=="pending"?"generating":l.status:null}]))):s.push("<!--[!-->"),s.push("<!--]--> <!--[-->"),slot(s,a,"default",{}),s.push("<!--]--></div>");});}

export { y };
//# sourceMappingURL=Index.svelte_svelte_type_style_lang-DPqoVNph.js.map

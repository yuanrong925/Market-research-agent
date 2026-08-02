import './async-D55cHugf.js';
import { c as spread_props, a as attr, e as ensure_array_like, f as attr_class } from './index-6p4UEISu.js';
import { O as Os } from './2-DQcH4kU_.js';
import { G } from './Block-DFkF8ric.js';
import { c } from './BlockTitle-EFVvyUMr.js';
import { y } from './IconButtonWrapper-DtthXzCF.js';
import { s as ss } from './index3-CiV5UCJA.js';
import { e as escape_html } from './escaping-CBnpiEl5.js';
import './context-CBkBucIx.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './index-Cg-Pg6j3.js';
import './Info-ByOFUBYS.js';
import './html-CfyvkLET.js';
import './IconButton-DoTLxBZ_.js';
import './Clear-D7Yjckqz.js';

function j(p,h){p.component(u=>{let{$$slots:f,$$events:x,...n}=h,t=new Os(n),c$1=(()=>{const e=t.props.choices.map(([,a])=>a);return t.props.value.length===0?"unchecked":t.props.value.length===e.length?"checked":"indeterminate"})(),i=!t.shared.interactive;t.props.value,G(u,{visible:t.shared.visible,elem_id:t.shared.elem_id,elem_classes:t.shared.elem_classes,type:"fieldset",container:t.shared.container,scale:t.shared.scale,min_width:t.shared.min_width,children:e=>{ss(e,spread_props([{autoscroll:t.shared.autoscroll,i18n:t.i18n},t.shared.loading_status,{on_clear_status:()=>t.dispatch("clear_status",t.shared.loading_status)}])),e.push("<!----> "),t.shared.show_label&&t.props.buttons&&t.props.buttons.length>0?(e.push("<!--[-->"),y(e,{buttons:t.props.buttons,on_custom_button_click:s=>{t.dispatch("custom_button_click",{id:s});}})):e.push("<!--[!-->"),e.push("<!--]--> "),c(e,{show_label:t.shared.show_label||t.props.show_select_all&&t.shared.interactive,info:t.props.info,children:s=>{t.props.show_select_all&&t.shared.interactive?(s.push("<!--[-->"),s.push(`<div class="select-all-container svelte-yb2gcx"><label class="select-all-label svelte-yb2gcx"><input class="select-all-checkbox svelte-yb2gcx"${attr("checked",c$1==="checked",true)}${attr("indeterminate",c$1==="indeterminate",true)} type="checkbox" title="Select/Deselect All"/></label> <button type="button" class="label-text svelte-yb2gcx">${escape_html(t.shared.show_label?t.shared.label:"Select All")}</button></div>`)):(s.push("<!--[!-->"),t.shared.show_label?(s.push("<!--[-->"),s.push(`${escape_html(t.shared.label||t.i18n("checkbox.checkbox_group"))}`)):s.push("<!--[!-->"),s.push("<!--]-->")),s.push("<!--]-->");},$$slots:{default:true}}),e.push('<!----> <div class="wrap svelte-yb2gcx" data-testid="checkbox-group"><!--[-->');const a=ensure_array_like(t.props.choices);for(let s=0,r=a.length;s<r;s++){let[d,o]=a[s];e.push(`<label${attr_class("svelte-yb2gcx",void 0,{disabled:i,selected:t.props.value.includes(o)})}><input${attr("disabled",i,true)}${attr("checked",t.props.value.includes(o),true)} type="checkbox"${attr("name",o?.toString())}${attr("title",o?.toString())} class="svelte-yb2gcx"/> <span class="ml-2 svelte-yb2gcx">${escape_html(t.live_i18n(d))}</span></label>`);}e.push("<!--]--></div>");},$$slots:{default:true}});});}

export { j as default };
//# sourceMappingURL=Index20-BJ5gQU7O.js.map

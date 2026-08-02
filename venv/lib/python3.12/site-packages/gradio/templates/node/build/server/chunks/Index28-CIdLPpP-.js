import './async-D55cHugf.js';
import { c as spread_props, f as attr_class, a as attr } from './index-6p4UEISu.js';
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

function N(l,i){l.component(e=>{const{$$slots:m,$$events:_,...r}=i,s=new Os(r);s.props.value??=0,s.props.value;const p=!s.shared.interactive;G(e,{visible:s.shared.visible,elem_id:s.shared.elem_id,elem_classes:s.shared.elem_classes,padding:s.shared.container,allow_overflow:false,scale:s.shared.scale,min_width:s.shared.min_width,children:t=>{ss(t,spread_props([{autoscroll:s.shared.autoscroll,i18n:s.i18n},s.shared.loading_status,{show_validation_error:false,on_clear_status:()=>{s.dispatch("clear_status",s.shared.loading_status);}}])),t.push(`<!----> <label${attr_class("block svelte-16ty2ow",void 0,{container:s.shared.container})}>`),s.shared.show_label&&s.props.buttons&&s.props.buttons.length>0?(t.push("<!--[-->"),y(t,{buttons:s.props.buttons,on_custom_button_click:o=>{s.dispatch("custom_button_click",{id:o});}})):t.push("<!--[!-->"),t.push("<!--]--> "),c(t,{show_label:s.shared.show_label,info:s.props.info,children:o=>{o.push(`<!---->${escape_html(s.shared.label||"Number")} `),s.shared.loading_status?.validation_error?(o.push("<!--[-->"),o.push(`<div class="validation-error svelte-16ty2ow">${escape_html(s.shared.loading_status?.validation_error)}</div>`)):o.push("<!--[!-->"),o.push("<!--]-->");},$$slots:{default:true}}),t.push(`<!----> <input${attr("aria-label",s.shared.label||"Number")} type="number"${attr("value",s.props.value)}${attr("min",s.props.minimum)}${attr("max",s.props.maximum)}${attr("step",s.props.step)}${attr("placeholder",s.props.placeholder)}${attr("disabled",p,true)}${attr_class("svelte-16ty2ow",void 0,{"validation-error":s.shared.loading_status?.validation_error})}/></label>`);},$$slots:{default:true}});});}

export { N as default };
//# sourceMappingURL=Index28-CIdLPpP-.js.map

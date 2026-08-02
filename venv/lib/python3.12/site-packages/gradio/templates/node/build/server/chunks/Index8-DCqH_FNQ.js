import './async-D55cHugf.js';
import { c as spread_props } from './index-6p4UEISu.js';
import { O as Os } from './2-DQcH4kU_.js';
import { G } from './Block-DFkF8ric.js';
import { u } from './Info-ByOFUBYS.js';
import { y } from './IconButtonWrapper-DtthXzCF.js';
import { s as ss } from './index3-CiV5UCJA.js';
import { d } from './Checkbox-DHL6KkGi.js';
import './escaping-CBnpiEl5.js';
import './context-CBkBucIx.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './index-Cg-Pg6j3.js';
import './html-CfyvkLET.js';
import './IconButton-DoTLxBZ_.js';
import './Clear-D7Yjckqz.js';

function z(e,l){e.component(i=>{let{$$slots:v,$$events:g,...u$1}=l;const s=new Os(u$1);let a=true,p;function c(h){G(h,{visible:s.shared.visible,elem_id:s.shared.elem_id,elem_classes:s.shared.elem_classes,children:t=>{ss(t,spread_props([{autoscroll:s.shared.autoscroll,i18n:s.i18n},s.shared.loading_status,{on_clear_status:()=>s.dispatch("clear_status",s.shared.loading_status)}])),t.push("<!----> "),s.shared.show_label&&s.props.buttons&&s.props.buttons.length>0?(t.push("<!--[-->"),y(t,{buttons:s.props.buttons,on_custom_button_click:o=>{s.dispatch("custom_button_click",{id:o});}})):t.push("<!--[!-->"),t.push("<!--]--> "),d(t,{label:s.shared.label||s.i18n("checkbox.checkbox"),interactive:s.shared.interactive,show_label:s.shared.show_label,on_change:o=>s.dispatch("change",o),on_input:()=>s.dispatch("input"),on_select:o=>s.dispatch("select",o),get value(){return s.props.value},set value(o){s.props.value=o,a=false;}}),t.push("<!----> "),s.props.info?(t.push("<!--[-->"),u(t,{info:s.props.info})):t.push("<!--[!-->"),t.push("<!--]-->");},$$slots:{default:true}});}do a=true,p=i.copy(),c(p);while(!a);i.subsume(p);});}

export { d as BaseCheckbox, z as default };
//# sourceMappingURL=Index8-DCqH_FNQ.js.map

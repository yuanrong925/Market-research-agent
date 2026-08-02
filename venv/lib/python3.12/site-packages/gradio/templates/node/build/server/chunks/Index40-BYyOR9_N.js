import './async-D55cHugf.js';
import { a as attr, g as attr_style, d as bind_props, c as spread_props } from './index-6p4UEISu.js';
import { O as Os } from './2-DQcH4kU_.js';
import { s } from './tinycolor-DfhFic3A.js';
import { c } from './BlockTitle-EFVvyUMr.js';
import { G } from './Block-DFkF8ric.js';
import { s as ss } from './index3-CiV5UCJA.js';
export { default as BaseExample } from './Example13-CPhQG2sc.js';
import { e as escape_html } from './escaping-CBnpiEl5.js';
import './context-CBkBucIx.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './index-Cg-Pg6j3.js';
import './Info-ByOFUBYS.js';
import './html-CfyvkLET.js';
import './IconButton-DoTLxBZ_.js';
import './Clear-D7Yjckqz.js';

function w(e,a){return s(e).toHexString()}function B(e,a){e.component(s=>{let{value:i=void 0,label:u,info:p,disabled:o,show_label:c$1,on_input:r=()=>{},on_release:n=()=>{},on_submit:m=()=>{},on_blur:h=()=>{},on_focus:l=()=>{}}=a;w(i),c(s,{show_label:c$1,info:p,children:d=>{d.push(`<!---->${escape_html(u)}`);},$$slots:{default:true}}),s.push(`<!----> <button class="dialog-button svelte-nbn1m9"${attr("aria-label",u)}${attr("disabled",o,true)}${attr_style("",{background:i})}></button> `),s.push("<!--[!-->"),s.push("<!--]-->"),bind_props(a,{value:i});});}function j(e,a){e.component(s=>{let{$$slots:i,$$events:u,...p}=a;const o=new Os(p,{value:"#000000"});o.props.value;let c=o.shared.label||o.i18n("color_picker.color_picker"),r=true,n;function m(h){G(h,{visible:o.shared.visible,elem_id:o.shared.elem_id,elem_classes:o.shared.elem_classes,container:o.shared.container,scale:o.shared.scale,min_width:o.shared.min_width,children:l=>{ss(l,spread_props([{autoscroll:o.shared.autoscroll,i18n:o.i18n},o.shared.loading_status,{on_clear_status:()=>o.dispatch("clear_status",o.shared.loading_status)}])),l.push("<!----> "),B(l,{label:c,info:o.props.info,show_label:o.shared.show_label,disabled:!o.shared.interactive,on_input:()=>o.dispatch("input"),on_release:()=>o.dispatch("release",o.props.value),on_submit:()=>o.dispatch("submit"),on_blur:()=>o.dispatch("blur"),on_focus:()=>o.dispatch("focus"),get value(){return o.props.value},set value(d){o.props.value=d,r=false;}}),l.push("<!---->");},$$slots:{default:true}});}do r=true,n=s.copy(),m(n);while(!r);s.subsume(n);});}

export { B as BaseColorPicker, j as default };
//# sourceMappingURL=Index40-BYyOR9_N.js.map

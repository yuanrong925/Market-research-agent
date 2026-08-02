import './async-D55cHugf.js';
import { c as spread_props } from './index-6p4UEISu.js';
import { O as Os } from './2-DQcH4kU_.js';
import { a as g, P as b } from './Plot-B85jOqV9.js';
import { G } from './Block-DFkF8ric.js';
import { k } from './BlockLabel-Cwr2q1Ma.js';
import { y } from './IconButtonWrapper-DtthXzCF.js';
import { v } from './FullscreenButton-Ktp2P70R.js';
import { s as ss } from './index3-CiV5UCJA.js';
import './escaping-CBnpiEl5.js';
import './context-CBkBucIx.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './index-Cg-Pg6j3.js';
import './Empty-cEfRNAPl.js';
import './IconButton-DoTLxBZ_.js';
import './Maximize-CuHbK64j.js';
import './Clear-D7Yjckqz.js';

function D(i,n){i.component(p=>{let{$$slots:B,$$events:x,...c}=n;const s=new Os(c);let l=false,e=true,a;function u(h){G(h,{padding:false,elem_id:s.shared.elem_id,elem_classes:s.shared.elem_classes,visible:s.shared.visible,container:s.shared.container,scale:s.shared.scale,min_width:s.shared.min_width,allow_overflow:false,get fullscreen(){return l},set fullscreen(o){l=o,e=false;},children:o=>{k(o,{show_label:s.shared.show_label,label:s.shared.label||s.i18n("plot.plot"),Icon:b}),o.push("<!----> "),s.props.buttons&&s.props.buttons.length>0||s.props.show_fullscreen_button?(o.push("<!--[-->"),y(o,{buttons:s.props.buttons??[],on_custom_button_click:t=>{s.dispatch("custom_button_click",{id:t});},children:t=>{s.props.show_fullscreen_button?(t.push("<!--[-->"),v(t,{fullscreen:l,onclick:r=>{l=r;}})):t.push("<!--[!-->"),t.push("<!--]-->");}})):o.push("<!--[!-->"),o.push("<!--]--> "),ss(o,spread_props([{autoscroll:s.shared.autoscroll,i18n:s.i18n},s.shared.loading_status,{on_clear_status:()=>s.dispatch("clear_status",s.shared.loading_status)}])),o.push("<!----> "),g(o,{value:s.props.value,theme_mode:s.props.theme_mode,show_label:s.shared.show_label,caption:s.props.caption,bokeh_version:s.props.bokeh_version,show_actions_button:s.props.show_actions_button,_selectable:s.props._selectable,x_lim:s.props.x_lim,show_fullscreen_button:s.props.show_fullscreen_button,on_change:()=>s.dispatch("change"),onselect:t=>s.dispatch("select",t)}),o.push("<!---->");},$$slots:{default:true}});}do e=true,a=p.copy(),u(a);while(!e);p.subsume(a);});}

export { g as BasePlot, D as default };
//# sourceMappingURL=Index14-BOQhF0Mi.js.map

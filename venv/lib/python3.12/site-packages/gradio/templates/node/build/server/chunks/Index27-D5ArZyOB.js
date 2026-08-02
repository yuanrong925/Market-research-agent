import './async-D55cHugf.js';
import { c as spread_props } from './index-6p4UEISu.js';
import { O as Os } from './2-DQcH4kU_.js';
import { G } from './Block-DFkF8ric.js';
import { c } from './BlockTitle-EFVvyUMr.js';
import { w } from './IconButton-DoTLxBZ_.js';
import { p } from './Empty-cEfRNAPl.js';
import { l } from './Download-DcU5dONL.js';
import { e } from './LineChart-DIvFgn2j.js';
import { y } from './IconButtonWrapper-DtthXzCF.js';
import { v } from './FullscreenButton-Ktp2P70R.js';
import { s as ss } from './index3-CiV5UCJA.js';
import { e as escape_html } from './escaping-CBnpiEl5.js';
import './context-CBkBucIx.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './index-Cg-Pg6j3.js';
import './Info-ByOFUBYS.js';
import './html-CfyvkLET.js';
import './Maximize-CuHbK64j.js';
import './Clear-D7Yjckqz.js';

function V(d,m){d.component(c$1=>{let{$$slots:G$1,$$events:L,...h}=m;const s=new Os(h);s.watch_for_change(),(()=>{if(!s.props.color||!s.props.value||s.props.value.datatypes[s.props.color]!=="nominal")return [];const p=s.props.value.columns.indexOf(s.props.color);return p===-1?[]:Array.from(new Set(s.props.value.data.map(o=>o[p])))})();let l$1=s.props.x_lim||null,n=s.props.y_lim||null;l$1?.[0]!==null&&l$1?.[0],l$1?.[1]!==null&&l$1?.[1],n?.[0]!==null&&n?.[0],n?.[1]!==null&&n?.[1];let i=false;function _(p){if(p==="x")return "ascending";if(p==="-x")return "descending";if(p==="y")return {field:s.props.y,order:"ascending"};if(p==="-y")return {field:s.props.y,order:"descending"};if(p===null)return null;if(Array.isArray(p))return p}_(s.props.sort),s.props.value&&s.props.value.datatypes[s.props.x];const g={s:1,m:60,h:3600,d:1440*60};let u=s.props.x_bin?typeof s.props.x_bin=="string"?1e3*parseInt(s.props.x_bin.substring(0,s.props.x_bin.length-1))*g[s.props.x_bin[s.props.x_bin.length-1]]:s.props.x_bin:void 0;(()=>{if(s.props.value)if(s.props.value.mark==="point"){const p=u!==void 0;return s.props.y_aggregate||p?"sum":void 0}else return s.props.y_aggregate?s.props.y_aggregate:"sum"})(),s.props.value&&(s.props.value.mark==="point"||u!==void 0||s.props.value.datatypes[s.props.x]),s.props.value;const b=typeof window<"u";function v$1(){}JSON.stringify(s.props.color_map);let a=true,r;function x(p$1){G(p$1,{visible:s.shared.visible,elem_id:s.shared.elem_id,elem_classes:s.shared.elem_classes,scale:s.shared.scale,min_width:s.shared.min_width,allow_overflow:false,padding:true,height:s.props.height,get fullscreen(){return i},set fullscreen(o){i=o,a=false;},children:o=>{s.shared.loading_status?(o.push("<!--[-->"),ss(o,spread_props([{autoscroll:s.shared.autoscroll,i18n:s.i18n},s.shared.loading_status,{on_clear_status:()=>s.dispatch("clear_status",s.shared.loading_status)}]))):o.push("<!--[!-->"),o.push("<!--]--> "),s.props.buttons?.length?(o.push("<!--[-->"),y(o,{buttons:s.props.buttons,on_custom_button_click:t=>{s.dispatch("custom_button_click",{id:t});},children:t=>{s.props.buttons?.some(e=>typeof e=="string"&&e==="export")?(t.push("<!--[-->"),w(t,{Icon:l,label:"Export",onclick:v$1})):t.push("<!--[!-->"),t.push("<!--]--> "),s.props.buttons?.some(e=>typeof e=="string"&&e==="fullscreen")?(t.push("<!--[-->"),v(t,{fullscreen:i,onclick:e=>i=e})):t.push("<!--[!-->"),t.push("<!--]-->");}})):o.push("<!--[!-->"),o.push("<!--]--> "),c(o,{show_label:s.shared.show_label,info:void 0,children:t=>{t.push(`<!---->${escape_html(s.shared.label)}`);},$$slots:{default:true}}),o.push("<!----> "),s.props.value&&b?(o.push("<!--[-->"),o.push('<div class="svelte-19utvcn"></div> '),s.props.caption?(o.push("<!--[-->"),o.push(`<p class="caption svelte-19utvcn">${escape_html(s.props.caption)}</p>`)):o.push("<!--[!-->"),o.push("<!--]-->")):(o.push("<!--[!-->"),p(o,{unpadded_box:true,children:t=>{e(t);},$$slots:{default:true}})),o.push("<!--]-->");},$$slots:{default:true}});}do a=true,r=c$1.copy(),x(r);while(!a);c$1.subsume(r);});}

export { V as default };
//# sourceMappingURL=Index27-D5ArZyOB.js.map

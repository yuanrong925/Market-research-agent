import './async-D55cHugf.js';
import { a as attr, f as attr_class, i as stringify, d as bind_props, c as spread_props, e as ensure_array_like } from './index-6p4UEISu.js';
import { O as Os } from './2-DQcH4kU_.js';
import { G } from './Block-DFkF8ric.js';
import { c } from './BlockTitle-EFVvyUMr.js';
import { y } from './IconButtonWrapper-DtthXzCF.js';
import { s as ss } from './index3-CiV5UCJA.js';
export { default as BaseExample } from './Example26-ij_CWEOU.js';
import { e as escape_html } from './escaping-CBnpiEl5.js';
import './context-CBkBucIx.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './index-Cg-Pg6j3.js';
import './Info-ByOFUBYS.js';
import './html-CfyvkLET.js';
import './IconButton-DoTLxBZ_.js';
import './Clear-D7Yjckqz.js';

let $=0;function q(n,o){n.component(r=>{let{selected:p=void 0,display_value:c,internal_value:i,disabled:t,rtl:u,on_input:d}=o,l=p===i;r.push(`<label${attr("data-testid",`${stringify(c)}-radio-label`)}${attr_class("svelte-19qdtil",void 0,{disabled:t,selected:l,rtl:u})}><input${attr("disabled",t,true)} type="radio"${attr("name",`radio-${stringify(++$)}`)}${attr("value",i)}${attr("aria-checked",l)}${attr("checked",p===i,true)} class="svelte-19qdtil"/> <span class="svelte-19qdtil">${escape_html(c)}</span></label>`),bind_props(o,{selected:p});});}function D(n,o){n.component(r=>{const{$$slots:p,$$events:c$1,...i}=o,t=new Os(i);let u=!t.shared.interactive;t.props.value;let d=true,l;function m(v){G(v,{visible:t.shared.visible,type:"fieldset",elem_id:t.shared.elem_id,elem_classes:t.shared.elem_classes,container:t.shared.container,scale:t.shared.scale,min_width:t.shared.min_width,rtl:t.props.rtl,children:e=>{ss(e,spread_props([{autoscroll:t.shared.autoscroll,i18n:t.i18n},t.shared.loading_status,{on_clear_status:()=>t.dispatch("clear_status",t.shared.loading_status)}])),e.push("<!----> "),t.shared.show_label&&t.props.buttons&&t.props.buttons.length>0?(e.push("<!--[-->"),y(e,{buttons:t.props.buttons,on_custom_button_click:a=>{t.dispatch("custom_button_click",{id:a});}})):e.push("<!--[!-->"),e.push("<!--]--> "),c(e,{show_label:t.shared.show_label,info:t.props.info,children:a=>{a.push(`<!---->${escape_html(t.shared.label||t.i18n("radio.radio"))}`);},$$slots:{default:true}}),e.push('<!----> <div class="wrap svelte-e4x47i"><!--[-->');const h=ensure_array_like(t.props.choices);for(let a=0,f=h.length;a<f;a++){let[b,_]=h[a];q(e,{display_value:t.live_i18n(b),internal_value:_,disabled:u,rtl:t.props.rtl,on_input:()=>{t.dispatch("input"),t.dispatch("select",{value:_,index:a});},get selected(){return t.props.value},set selected(y){t.props.value=y,d=false;}});}e.push("<!--]--></div>");},$$slots:{default:true}});}do d=true,l=r.copy(),m(l);while(!d);r.subsume(l);});}

export { q as BaseRadio, D as default };
//# sourceMappingURL=Index42-Dbuf9wU7.js.map

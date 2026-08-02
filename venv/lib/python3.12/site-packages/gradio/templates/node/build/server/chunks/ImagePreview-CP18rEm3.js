import './async-D55cHugf.js';
import { f as attr_class, d as bind_props } from './index-6p4UEISu.js';
import { P as Ps } from './2-DQcH4kU_.js';
import { k } from './BlockLabel-Cwr2q1Ma.js';
import { u } from './DownloadLink-eCzvV1uC.js';
import { w } from './IconButton-DoTLxBZ_.js';
import { p } from './Empty-cEfRNAPl.js';
import { A } from './ShareButton-NRFUZk4D.js';
import { l } from './Download-DcU5dONL.js';
import { i } from './Image2-vcp9_ifi.js';
import { y } from './IconButtonWrapper-DtthXzCF.js';
import { v } from './FullscreenButton-Ktp2P70R.js';
import { j } from './Image-DYkfMGqQ.js';
import './escaping-CBnpiEl5.js';
import './context-CBkBucIx.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './index-Cg-Pg6j3.js';
import './Maximize-CuHbK64j.js';

/* empty css                                          */function R(f,p$1){f.component(t=>{let{value:a,label:e=void 0,show_label:m,buttons:l$1=[],on_custom_button_click:h=null,selectable:r=false,i18n:u$1,display_icon_button_wrapper_top_corner:g=false,fullscreen:i$1=false,show_button_background:_=true,onselect:P,onfullscreen:b,onshare:d,onerror:v$1,onload:w$1}=p$1;k(t,{show_label:m,Icon:i,label:m?e||u$1("image.image"):""}),t.push("<!----> "),a==null||!a?.url?(t.push("<!--[-->"),p(t,{unpadded_box:true,size:"large",children:s=>{i(s);},$$slots:{default:true}})):(t.push("<!--[!-->"),t.push('<div class="image-container svelte-12vrxzd">'),y(t,{display_top_corner:g,show_background:_,buttons:l$1,on_custom_button_click:h,children:s=>{l$1.some(o=>typeof o=="string"&&o==="fullscreen")?(s.push("<!--[-->"),v(s,{fullscreen:i$1,onclick:o=>{i$1=o,b?.(o);}})):s.push("<!--[!-->"),s.push("<!--]--> "),l$1.some(o=>typeof o=="string"&&o==="download")?(s.push("<!--[-->"),u(s,{href:a.url,download:a.orig_name||"image",children:o=>{w(o,{Icon:l,label:u$1("common.download")});},$$slots:{default:true}})):s.push("<!--[!-->"),s.push("<!--]--> "),l$1.some(o=>typeof o=="string"&&o==="share")?(s.push("<!--[-->"),A(s,{i18n:u$1,onshare:o=>d?.(o),onerror:o=>v$1?.(o),formatter:async o=>o?`<img src="${await Ps(o)}" />`:"",value:a})):s.push("<!--[!-->"),s.push("<!--]-->");}}),t.push(`<!----> <button class="svelte-12vrxzd"><div${attr_class("image-frame svelte-12vrxzd",void 0,{selectable:r})}>`),j(t,{src:a.url,restProps:{loading:"lazy",alt:""},onload:w$1}),t.push("<!----></div></button></div>")),t.push("<!--]-->"),bind_props(p$1,{fullscreen:i$1});});}

export { R as default };
//# sourceMappingURL=ImagePreview-CP18rEm3.js.map

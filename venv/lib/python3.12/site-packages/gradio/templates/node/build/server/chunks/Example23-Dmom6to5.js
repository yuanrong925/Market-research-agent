import './async-D55cHugf.js';
import { f as attr_class, e as ensure_array_like, a as attr } from './index-6p4UEISu.js';
import { j } from './Image-DYkfMGqQ.js';
import './2-DQcH4kU_.js';
import { c as ch } from './Video2-CvkgR7SS.js';
import { e as escape_html } from './escaping-CBnpiEl5.js';
import './context-CBkBucIx.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './index-Cg-Pg6j3.js';

function I(o,e){o.component(t=>{let{value:l={text:"",files:[]},type:a,selected:u=false}=e;t.push(`<div${attr_class("container svelte-xz0m7l",void 0,{table:a==="table",gallery:a==="gallery",selected:u,border:l})}><p>${escape_html(l.text?l.text:"")}</p> <!--[-->`);const m=ensure_array_like(l.files);for(let p=0,c=m.length;p<c;p++){let s=m[p];s.mime_type&&s.mime_type.includes("image")?(t.push("<!--[-->"),j(t,{src:s.url,alt:""})):(t.push("<!--[!-->"),s.mime_type&&s.mime_type.includes("video")?(t.push("<!--[-->"),ch(t,{src:s.url,alt:"",loop:true,is_stream:false})):(t.push("<!--[!-->"),s.mime_type&&s.mime_type.includes("audio")?(t.push("<!--[-->"),t.push(`<audio${attr("src",s.url)} controls></audio>`)):(t.push("<!--[!-->"),t.push(`${escape_html(s.orig_name)}`)),t.push("<!--]-->")),t.push("<!--]-->")),t.push("<!--]-->");}t.push("<!--]--></div>");});}

export { I as default };
//# sourceMappingURL=Example23-Dmom6to5.js.map

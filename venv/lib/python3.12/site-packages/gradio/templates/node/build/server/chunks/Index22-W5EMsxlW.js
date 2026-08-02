import './async-D55cHugf.js';
import { c as spread_props } from './index-6p4UEISu.js';
import { O as Os } from './2-DQcH4kU_.js';
import { k } from './BlockLabel-Cwr2q1Ma.js';
import { t as tick } from './index-server-BnQ31CjT.js';
import { p } from './Empty-cEfRNAPl.js';
import { i } from './File-DQh5d1OO.js';
import { y } from './IconButtonWrapper-DtthXzCF.js';
import { S, u as ul } from './FileUpload-CJjnI0Ni.js';
import { G } from './Block-DFkF8ric.js';
import { k as k$1 } from './UploadText-BslqYKOD.js';
import { s as ss } from './index3-CiV5UCJA.js';
export { default as BaseExample } from './Example5-Sv6lxPPF.js';
import './escaping-CBnpiEl5.js';
import './context-CBkBucIx.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './index-Cg-Pg6j3.js';
import './Upload2-CAgMsGRX.js';
import './IconButton-DoTLxBZ_.js';
import './Clear-D7Yjckqz.js';
import './Upload-BbxeBrrD.js';
import './DownloadLink-eCzvV1uC.js';
import './html-CfyvkLET.js';

function z(u,c){u.component(t=>{let{value:o,label:m,show_label:n,selectable:l,i18n:r,height:h,buttons:s=null,on_custom_button_click:i$1=null,on_select:p$1,on_download:_}=c;n&&s&&s.length>0?(t.push("<!--[-->"),y(t,{buttons:s,on_custom_button_click:i$1})):t.push("<!--[!-->"),t.push("<!--]--> "),k(t,{show_label:n,float:o===null,Icon:i,label:m||"File"}),t.push("<!----> "),o&&(!Array.isArray(o)||o.length>0)?(t.push("<!--[-->"),S(t,{i18n:r,selectable:l,onselect:p$1,ondownload:_,value:o,height:h??void 0})):(t.push("<!--[!-->"),p(t,{unpadded_box:true,size:"large",children:d=>{i(d);},$$slots:{default:true}})),t.push("<!--]-->");});}function N(u,c){u.component(t=>{const{$$slots:o,$$events:m,...n}=c;let l=null,r=false;class h extends Os{async get_data(){return l&&(await l,await tick()),await super.get_data()}}const s=new h(n);s.props.value;let i=true,p;function _(d){G(d,{visible:s.shared.visible,variant:s.props.value?"solid":"dashed",border_mode:r?"focus":"base",padding:false,elem_id:s.shared.elem_id,elem_classes:s.shared.elem_classes,container:s.shared.container,scale:s.shared.scale,min_width:s.shared.min_width,allow_overflow:false,children:e=>{ss(e,spread_props([{autoscroll:s.shared.autoscroll,i18n:s.i18n},s.shared.loading_status,{status:s.shared.loading_status?.status||"complete",on_clear_status:()=>s.dispatch("clear_status",s.shared.loading_status)}])),e.push("<!----> "),s.shared.interactive?(e.push("<!--[!-->"),ul(e,{upload:(...a)=>s.shared.client.upload(...a),stream_handler:(...a)=>s.shared.client.stream(...a),label:s.shared.label,show_label:s.shared.show_label,value:s.props.value,file_count:s.props.file_count,file_types:s.props.file_types,selectable:s.props._selectable,height:s.props.height??void 0,root:s.shared.root,allow_reordering:s.props.allow_reordering,max_file_size:s.shared.max_file_size,buttons:s.props.buttons,on_custom_button_click:a=>{s.dispatch("custom_button_click",{id:a});},onchange:a=>{s.props.value=a;},ondrag:a=>r=a,onclear:()=>s.dispatch("clear"),onselect:a=>s.dispatch("select",a),onupload:()=>s.dispatch("upload"),onerror:a=>{s.shared.loading_status=s.shared.loading_status||{},s.shared.loading_status.status="error",s.dispatch("error",a);},ondelete:a=>{s.dispatch("delete",a);},i18n:s.i18n,get upload_promise(){return l},set upload_promise(a){l=a,i=false;},children:a=>{k$1(a,{i18n:s.i18n,type:"file"});},$$slots:{default:true}})):(e.push("<!--[-->"),z(e,{on_select:a=>s.dispatch("select",a),on_download:a=>s.dispatch("download",a),selectable:s.props._selectable,value:s.props.value,label:s.shared.label,show_label:s.shared.show_label,height:s.props.height,i18n:s.i18n,buttons:s.props.buttons,on_custom_button_click:a=>{s.dispatch("custom_button_click",{id:a});}})),e.push("<!--]-->");},$$slots:{default:true}});}do i=true,p=t.copy(),_(p);while(!i);t.subsume(p);});}

export { z as BaseFile, ul as BaseFileUpload, S as FilePreview, N as default };
//# sourceMappingURL=Index22-W5EMsxlW.js.map

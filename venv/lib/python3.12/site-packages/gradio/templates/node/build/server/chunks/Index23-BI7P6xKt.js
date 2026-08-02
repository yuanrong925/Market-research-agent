import './async-D55cHugf.js';
import { c as spread_props, f as attr_class, j as clsx } from './index-6p4UEISu.js';
import { t as tick } from './index-server-BnQ31CjT.js';
import { G } from './Block-DFkF8ric.js';
import { O as Os } from './2-DQcH4kU_.js';
import { k } from './UploadText-BslqYKOD.js';
import { w } from './SelectSource-CjFx3b54.js';
import { h as Il, G as Qt } from './Gallery-Djj6odSH.js';
import { s as ss } from './index3-CiV5UCJA.js';
import { u as ul } from './FileUpload-CJjnI0Ni.js';
import { o as oe } from './Webcam2-BLjTe8Mm.js';
export { default as BaseExample } from './Example17-C_1EAEf8.js';
import './escaping-CBnpiEl5.js';
import './context-CBkBucIx.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './index-Cg-Pg6j3.js';
import './Upload-BbxeBrrD.js';
import './Microphone-BMM9-23W.js';
import './Video-FfbWmOVG.js';
import './Webcam-CvKMKUzA.js';
import './BlockLabel-Cwr2q1Ma.js';
import './IconButton-DoTLxBZ_.js';
import './Empty-cEfRNAPl.js';
import './ShareButton-NRFUZk4D.js';
import './Clear-D7Yjckqz.js';
import './Download-DcU5dONL.js';
import './Image2-vcp9_ifi.js';
import './Play-B_z3rKL1.js';
import './IconButtonWrapper-DtthXzCF.js';
import './FullscreenButton-Ktp2P70R.js';
import './Maximize-CuHbK64j.js';
import './Upload2-CAgMsGRX.js';
import './ModifyUpload-CbCOm4ku.js';
import './DownloadLink-eCzvV1uC.js';
import './Edit-DWZSi_T0.js';
import './Undo-Ce01x-M5.js';
import './Image-DYkfMGqQ.js';
import './Video2-CvkgR7SS.js';
import './File-DQh5d1OO.js';
import './html-CfyvkLET.js';
import './StreamingBar-BPXO3h4p.js';

function te(y,x){y.component(f=>{let n;let G$1 = class G extends Os{async get_data(){return n&&(await n,await tick()),await super.get_data()}};const{$$slots:q,$$events:E,...k$1}=x,e=new G$1(k$1,{selected_index:null,file_types:["image","video"]});let c=false;function B(t){if(!e.props.value)return;const{index:a}=t;e.dispatch("delete",t),e.props.value=e.props.value.filter((s,o)=>o!==a),e.dispatch("change",e.props.value);}async function r(t){return (await Promise.all(t.map(async s=>{if(s.path?.toLowerCase().endsWith(".svg")&&s.url){const l=await(await fetch(s.url)).text();return {...s,url:`data:image/svg+xml,${encodeURIComponent(l)}`}}return s}))).map(s=>s.mime_type?.includes("video")?{video:s,caption:null}:{image:s,caption:null})}let i=e.props.sources?e.props.sources[0]:"upload",m=e.props.value===null?true:e.props.value.length===0,u=e.props.file_types?.includes("video")&&e.props.sources.includes("webcam")?e.props.sources.concat(["webcam-video"]):e.props.sources;async function v(){navigator.clipboard.read().then(async t=>{let a=null;for(let s=0;s<t.length;s++){const o=t[s].types.find(l=>(e.props.file_types||["image"]).some(h=>l.startsWith(h+"/")));if(o){const l=await t[s].getType(o);a=new File([l],`clipboard.${o.replace("image/","")}`);break}}if(a){const s=await Il(a,l=>e.shared.client.upload(l,e.shared.root),"clipboard_upload"),o=await r(s);e.props.value?.push(...o),e.dispatch("change",e.props.value),i=null;}else e.dispatch("warning","No image or video found in clipboard");});}async function S(t){t==="clipboard"&&await v();}async function z(t){await tick(),t==="clipboard"?await v():(i=t,m=true);}let p=true,d;function A(t){G(t,{visible:e.shared.visible,variant:"solid",padding:false,elem_id:e.shared.elem_id,elem_classes:e.shared.elem_classes,container:e.shared.container,scale:e.shared.scale,min_width:e.shared.min_width,allow_overflow:false,height:e.props.height||void 0,get fullscreen(){return c},set fullscreen(a){c=a,p=false;},children:a=>{ss(a,spread_props([{autoscroll:e.shared.autoscroll,i18n:e.i18n},e.shared.loading_status,{on_clear_status:()=>e.dispatch("clear_status",e.shared.loading_status)}])),a.push("<!----> "),e.shared.interactive&&m?(a.push("<!--[-->"),a.push(`<div${attr_class(clsx(!e.props.value||i&&i.includes("webcam")?"hidden-upload-input":"upload-wrapper"),"svelte-vrqwbn")}>`),ul(a,{value:null,root:e.shared.root,label:e.shared.label,max_file_size:e.shared.max_file_size,file_count:"multiple",file_types:e.props.file_types,i18n:e.i18n,upload:(...s)=>e.shared.client.upload(...s),stream_handler:(...s)=>e.shared.client.stream(...s),onupload:async s=>{const o=Array.isArray(s)?s:[s];e.props.value=await r(o),i=null,e.dispatch("upload",e.props.value),e.dispatch("change",e.props.value);},onerror:s=>{e.shared.loading_status=e.shared.loading_status||{},e.shared.loading_status.status="error",e.dispatch("error",s);},get upload_promise(){return n},set upload_promise(s){n=s,p=false;},children:s=>{k(s,{i18n:e.i18n,type:"gallery"});},$$slots:{default:true}}),a.push("<!----></div> "),i==="webcam"?(a.push("<!--[-->"),oe(a,{root:e.shared.root,value:null,oncapture:async s=>{if(!(s instanceof Blob))return;const o=await Il(s,h=>e.shared.client.upload(h,e.shared.root),"webcam_upload"),l=await r(o);e.props.value?.push(...l),i=null,e.dispatch("change",e.props.value);},mirror_webcam:true,streaming:false,mode:"image",include_audio:false,i18n:e.i18n,upload:(...s)=>e.shared.client.upload(...s)})):(a.push("<!--[!-->"),i==="webcam-video"?(a.push("<!--[-->"),oe(a,{root:e.shared.root,value:null,oncapture:async s=>{if(!s)return;const o={...s};o.mime_type="video/webm";const l=await r([o]);e.props.value?.push(...l),i=null,e.dispatch("change",e.props.value);},mirror_webcam:true,streaming:false,mode:"video",include_audio:false,i18n:e.i18n,upload:(...s)=>e.shared.client.upload(...s)})):a.push("<!--[!-->"),a.push("<!--]-->")),a.push("<!--]--> "),u.length>1||u.includes("clipboard")?(a.push("<!--[-->"),w(a,{sources:u,handle_clear:()=>e.dispatch("clear"),handle_select:s=>S(s),get active_source(){return i},set active_source(s){i=s,p=false;}})):a.push("<!--[!-->"),a.push("<!--]-->")):(a.push("<!--[!-->"),Qt(a,{onchange:()=>e.dispatch("change"),onclear:()=>e.dispatch("change"),onselect:s=>e.dispatch("select",s),onshare:s=>e.dispatch("share",s.detail),onerror:s=>e.dispatch("error",s.detail),onpreview_open:()=>{e.dispatch("preview_open");},onpreview_close:()=>e.dispatch("preview_close"),onfullscreen:({detail:s})=>{c=s;},ondelete:B,onupload:async s=>{const o=Array.isArray(s)?s:[s],l=await r(o);e.props.value=e.props.value?[...e.props.value,...l]:l,e.dispatch("upload",l),e.dispatch("change",e.props.value);},sources:u,onsource_change:s=>z(s),label:e.shared.label,show_label:e.shared.show_label,columns:e.props.columns,rows:e.props.rows,height:e.props.height,preview:e.props.preview,object_fit:e.props.object_fit,interactive:e.shared.interactive,allow_preview:e.props.allow_preview,show_share_button:e.props.buttons.some(s=>typeof s=="string"&&s==="share"),show_download_button:e.props.buttons.some(s=>typeof s=="string"&&s==="download"),show_download_all_button:e.props.buttons.some(s=>typeof s=="string"&&s==="download_all"),fit_columns:e.props.fit_columns,i18n:e.i18n,_fetch:(...s)=>e.shared.client.fetch(...s),show_fullscreen_button:e.props.buttons.some(s=>typeof s=="string"&&s==="fullscreen"),buttons:e.props.buttons,oncustom_button_click:s=>{e.dispatch("custom_button_click",{id:s});},fullscreen:c,root:e.shared.root,file_types:e.props.file_types,max_file_size:e.shared.max_file_size,upload:(...s)=>e.shared.client.upload(...s),stream_handler:(...s)=>e.shared.client.stream(...s),get selected_index(){return e.props.selected_index},set selected_index(s){e.props.selected_index=s,p=false;},get value(){return e.props.value},set value(s){e.props.value=s,p=false;}})),a.push("<!--]-->");},$$slots:{default:true}});}do p=true,d=f.copy(),A(d);while(!p);f.subsume(d);});}

export { Qt as BaseGallery, te as default };
//# sourceMappingURL=Index23-BI7P6xKt.js.map

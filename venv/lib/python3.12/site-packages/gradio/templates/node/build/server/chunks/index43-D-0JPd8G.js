import './async-D55cHugf.js';
import { d as bind_props, c as spread_props } from './index-6p4UEISu.js';
import { e as ee } from './Upload2-CAgMsGRX.js';
import { k } from './BlockLabel-Cwr2q1Ma.js';
import { t as tick } from './index-server-BnQ31CjT.js';
import { r } from './Video-FfbWmOVG.js';
import { O as Os } from './2-DQcH4kU_.js';
import { e as escape_html } from './escaping-CBnpiEl5.js';
import { w } from './SelectSource-CjFx3b54.js';
import { o as oe } from './Webcam2-BLjTe8Mm.js';
import { P as Mt, p as Zt, V as Ft } from './VideoPreview-CVcvqYdI.js';
export { l as loaded, a as playable } from './VideoPreview-CVcvqYdI.js';
export { default as BaseExample } from './Example28-BPIZiCN8.js';
import { G } from './Block-DFkF8ric.js';
import { k as k$1 } from './UploadText-BslqYKOD.js';
import { s as ss } from './index3-CiV5UCJA.js';
import './context-CBkBucIx.js';
import './index5-BoOEKc6P.js';
import './dev-fallback-Bc5Ork7Y.js';
import './index-Cg-Pg6j3.js';
import './Upload-BbxeBrrD.js';
import './Microphone-BMM9-23W.js';
import './Webcam-CvKMKUzA.js';
import './StreamingBar-BPXO3h4p.js';
import './DownloadLink-eCzvV1uC.js';
import './IconButton-DoTLxBZ_.js';
import './Empty-cEfRNAPl.js';
import './ShareButton-NRFUZk4D.js';
import './Download-DcU5dONL.js';
import './IconButtonWrapper-DtthXzCF.js';
import './Maximize-CuHbK64j.js';
import './VolumeLevels-DlU2d99x.js';
import './Play-B_z3rKL1.js';
import './Undo-Ce01x-M5.js';
import './Video2-CvkgR7SS.js';
import './ModifyUpload-CbCOm4ku.js';
import './Clear-D7Yjckqz.js';
import './Edit-DWZSi_T0.js';

function is(y,g){y.component(h=>{let{value:i=null,subtitle:U=null,sources:k$1=["webcam","upload"],label:n=void 0,show_download_button:x=false,show_label:s=true,webcam_options:c,include_audio:_,autoplay:m,root:u,i18n:f,active_source:z="webcam",handle_reset_value:B=()=>{},max_file_size:p=null,upload:r$1,stream_handler:V,loop:l,uploading:t=void 0,upload_promise:a=void 0,playback_position:S=void 0,buttons:ps=null,on_custom_button_click:ns=null,onchange:w$1,onclear:q,onplay:A,onpause:C,onend:D,ondrag:us,onerror:I,onupload:F,onstart_recording:H,onstop_recording:J,onstop:K,children:G}=g,W=false,b=z??"webcam";function M(o){i=o,w$1?.(o),o&&F?.(o);}function E(){i=null,w$1?.(null),q?.();}function N(o){W=true,w$1?.(o);}function O({detail:o}){w$1?.(o);}let L=false,d=true,P;function Q(o){k(o,{show_label:s,Icon:r,label:n||"Video"}),o.push('<!----> <div data-testid="video" class="video-container svelte-ey25pz">'),i===null||i?.url===void 0?(o.push("<!--[-->"),o.push('<div class="upload-container svelte-ey25pz">'),b==="upload"?(o.push("<!--[-->"),ee(o,{filetype:"video/x-m4v,video/*",onload:M,max_file_size:p,onerror:e=>I?.(e),root:u,upload:r$1,stream_handler:V,aria_label:f("video.drop_to_upload"),get upload_promise(){return a},set upload_promise(e){a=e,d=false;},get dragging(){return L},set dragging(e){L=e,d=false;},get uploading(){return t},set uploading(e){t=e,d=false;},children:e=>{G?(e.push("<!--[-->"),G(e),e.push("<!---->")):e.push("<!--[!-->"),e.push("<!--]-->");},$$slots:{default:true}})):(o.push("<!--[!-->"),b==="webcam"?(o.push("<!--[-->"),oe(o,{root:u,mirror_webcam:c.mirror,webcam_constraints:c.constraints,include_audio:_,mode:"video",onerror:e=>I?.(e),oncapture:e=>O({detail:e}),onstart_recording:()=>H?.(),onstop_recording:()=>J?.(),i18n:f,upload:r$1,stream_every:1})):o.push("<!--[!-->"),o.push("<!--]-->")),o.push("<!--]--></div>")):(o.push("<!--[!-->"),i?.url?(o.push("<!--[-->"),o.push("<!---->"),Mt(o,{upload:r$1,root:u,interactive:true,autoplay:m,src:i.url,subtitle:U?.url,is_stream:false,onplay:()=>A?.(),onpause:()=>C?.(),onstop:()=>K?.(),onend:()=>D?.(),onerror:e=>I?.(e),mirror:c.mirror&&b==="webcam",label:n,handle_change:N,handle_reset_value:B,loop:l,value:i,i18n:f,show_download_button:x,handle_clear:E,has_change_history:W,get playback_position(){return S},set playback_position(e){S=e,d=false;}}),o.push("<!---->")):(o.push("<!--[!-->"),i.size?(o.push("<!--[-->"),o.push(`<div class="file-name svelte-ey25pz">${escape_html(i.orig_name||i.url)}</div> <div class="file-size svelte-ey25pz">${escape_html(Zt(i.size))}</div>`)):o.push("<!--[!-->"),o.push("<!--]-->")),o.push("<!--]-->")),o.push("<!--]--> "),w(o,{sources:k$1,handle_clear:E,get active_source(){return b},set active_source(e){b=e,d=false;}}),o.push("<!----></div>");}do d=true,P=h.copy(),Q(P);while(!d);h.subsume(P),bind_props(g,{value:i,uploading:t,upload_promise:a,playback_position:S});});}function Ws(y,g){y.component(h=>{const{$$slots:i,$$events:U,...k}=g;let n;class x extends Os{async get_data(){return n&&(await n,await tick()),await super.get_data()}}const s=new x(k);s.props.value;let c=false,_=false,m=s.props.sources?s.props.sources[0]:void 0,u=s.props.value;const f=()=>{u===null||s.props.value===u||(s.props.value=u);};function z(l){l!=null?s.props.value=l:s.props.value=null;}function B(l){const[t,a]=l.includes("Invalid file type")?["warning","complete"]:["error","error"];s.shared.loading_status.status=a,s.shared.loading_status.message=l,s.dispatch(t,l);}let p=true,r;function V(l){s.shared.interactive?(l.push("<!--[!-->"),G(l,{visible:s.shared.visible,variant:s.props.value===null&&m==="upload"?"dashed":"solid",border_mode:_?"focus":"base",padding:false,elem_id:s.shared.elem_id,elem_classes:s.shared.elem_classes,height:s.props.height||void 0,width:s.props.width,container:s.shared.container,scale:s.shared.scale,min_width:s.shared.min_width,allow_overflow:false,children:t=>{ss(t,spread_props([{autoscroll:s.shared.autoscroll,i18n:s.i18n},s.shared.loading_status,{on_clear_status:()=>s.dispatch("clear_status",s.shared.loading_status)}])),t.push("<!----> "),is(t,{value:s.props.value,subtitle:s.props.subtitles,onchange:z,ondrag:a=>_=a,onerror:B,label:s.shared.label,show_label:s.shared.show_label,buttons:s.props.buttons??["download","share"],on_custom_button_click:a=>{s.dispatch("custom_button_click",{id:a});},sources:s.props.sources,active_source:m,webcam_options:s.props.webcam_options,include_audio:s.props.include_audio,autoplay:s.props.autoplay,root:s.shared.root,loop:s.props.loop,handle_reset_value:f,onclear:()=>{s.props.value=null,s.dispatch("clear"),s.dispatch("input");},onplay:()=>s.dispatch("play"),onpause:()=>s.dispatch("pause"),onupload:()=>{s.dispatch("upload"),s.dispatch("input");},onstop:()=>s.dispatch("stop"),onend:()=>s.dispatch("end"),onstart_recording:()=>s.dispatch("start_recording"),onstop_recording:()=>s.dispatch("stop_recording"),i18n:s.i18n,max_file_size:s.shared.max_file_size,upload:(...a)=>s.shared.client.upload(...a),stream_handler:(...a)=>s.shared.client.stream(...a),get upload_promise(){return n},set upload_promise(a){n=a,p=false;},get uploading(){return c},set uploading(a){c=a,p=false;},get playback_position(){return s.props.playback_position},set playback_position(a){s.props.playback_position=a,p=false;},children:a=>{k$1(a,{i18n:s.i18n,type:"video"});},$$slots:{default:true}}),t.push("<!---->");},$$slots:{default:true}})):(l.push("<!--[-->"),G(l,{visible:s.shared.visible,variant:s.props.value===null&&m==="upload"?"dashed":"solid",border_mode:_?"focus":"base",padding:false,elem_id:s.shared.elem_id,elem_classes:s.shared.elem_classes,height:s.props.height||void 0,width:s.props.width,container:s.shared.container,scale:s.shared.scale,min_width:s.shared.min_width,allow_overflow:false,children:t=>{ss(t,spread_props([{autoscroll:s.shared.autoscroll,i18n:s.i18n},s.shared.loading_status,{on_clear_status:()=>s.dispatch("clear_status",s.shared.loading_status)}])),t.push("<!----> "),Ft(t,{value:s.props.value,subtitle:s.props.subtitles,label:s.shared.label,show_label:s.shared.show_label,autoplay:s.props.autoplay,loop:s.props.loop,buttons:s.props.buttons??["download","share"],on_custom_button_click:a=>{s.dispatch("custom_button_click",{id:a});},onplay:()=>s.dispatch("play"),onpause:()=>s.dispatch("pause"),onstop:()=>s.dispatch("stop"),onend:()=>s.dispatch("end"),onshare:a=>s.dispatch("share",a),onerror:a=>s.dispatch("error",a),i18n:s.i18n,upload:(...a)=>s.shared.client.upload(...a),get playback_position(){return s.props.playback_position},set playback_position(a){s.props.playback_position=a,p=false;}}),t.push("<!---->");},$$slots:{default:true}})),l.push("<!--]-->");}do p=true,r=h.copy(),V(r);while(!p);h.subsume(r);});}

export { is as BaseInteractiveVideo, Mt as BasePlayer, Ft as BaseStaticVideo, Ws as default, Zt as prettyBytes };
//# sourceMappingURL=index43-D-0JPd8G.js.map

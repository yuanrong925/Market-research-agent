import './async-D55cHugf.js';
import { w } from './IconButton-DoTLxBZ_.js';
import { X as Xe } from './2-DQcH4kU_.js';

function p(t){t.push('<svg id="icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="100%" height="100%"><path d="M23,20a5,5,0,0,0-3.89,1.89L11.8,17.32a4.46,4.46,0,0,0,0-2.64l7.31-4.57A5,5,0,1,0,18,7a4.79,4.79,0,0,0,.2,1.32l-7.31,4.57a5,5,0,1,0,0,6.22l7.31,4.57A4.79,4.79,0,0,0,18,25a5,5,0,1,0,5-5ZM23,4a3,3,0,1,1-3,3A3,3,0,0,1,23,4ZM7,19a3,3,0,1,1,3-3A3,3,0,0,1,7,19Zm16,9a3,3,0,1,1,3-3A3,3,0,0,1,23,28Z" fill="currentColor"></path></svg>');}function A(t,r){t.component(n=>{let{formatter:i,value:s,i18n:l,onshare:m,onerror:c}=r,a=false;w(n,{Icon:p,label:l("common.share"),pending:a,onclick:async()=>{try{a=!0;const e={description:await i(s)};m?.(e);}catch(o){console.error(o);let e=o instanceof Xe?o.message:"Share failed.";c?.(e);}finally{a=false;}}});});}

export { A, p };
//# sourceMappingURL=ShareButton-NRFUZk4D.js.map

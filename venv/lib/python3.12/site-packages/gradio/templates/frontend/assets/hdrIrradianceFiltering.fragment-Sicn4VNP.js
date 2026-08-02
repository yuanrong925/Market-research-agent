import{S as r}from"./index-BWbDOt8M.js";import"./helperFunctions-a-oFdAAo.js";import"./hdrFilteringFunctions-D04Bj3B1.js";import"./pbrBRDFFunctions-z5Wdivd0.js";import"./index-9Ev7iYt6.js";const e="hdrIrradianceFilteringPixelShader",i=`#include<helperFunctions>
#include<importanceSampling>
#include<pbrBRDFFunctions>
#include<hdrFilteringFunctions>
uniform samplerCube inputTexture;
#ifdef IBL_CDF_FILTERING
uniform sampler2D icdfTexture;
#endif
uniform vec2 vFilteringInfo;uniform float hdrScale;varying vec3 direction;void main() {vec3 color=irradiance(inputTexture,direction,vFilteringInfo,0.0,vec3(1.0),direction
#ifdef IBL_CDF_FILTERING
,icdfTexture
#endif
);gl_FragColor=vec4(color*hdrScale,1.0);}`;r.ShadersStore[e]||(r.ShadersStore[e]=i);const a={name:e,shader:i};export{a as hdrIrradianceFilteringPixelShader};

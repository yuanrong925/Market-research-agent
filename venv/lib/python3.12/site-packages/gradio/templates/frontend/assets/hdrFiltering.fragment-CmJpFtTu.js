import{S as i}from"./index-BWbDOt8M.js";import"./helperFunctions-a-oFdAAo.js";import"./hdrFilteringFunctions-D04Bj3B1.js";import"./pbrBRDFFunctions-z5Wdivd0.js";import"./index-9Ev7iYt6.js";const r="hdrFilteringPixelShader",e=`#include<helperFunctions>
#include<importanceSampling>
#include<pbrBRDFFunctions>
#include<hdrFilteringFunctions>
uniform float alphaG;uniform samplerCube inputTexture;uniform vec2 vFilteringInfo;uniform float hdrScale;varying vec3 direction;void main() {vec3 color=radiance(alphaG,inputTexture,direction,vFilteringInfo);gl_FragColor=vec4(color*hdrScale,1.0);}`;i.ShadersStore[r]||(i.ShadersStore[r]=e);const c={name:r,shader:e};export{c as hdrFilteringPixelShader};

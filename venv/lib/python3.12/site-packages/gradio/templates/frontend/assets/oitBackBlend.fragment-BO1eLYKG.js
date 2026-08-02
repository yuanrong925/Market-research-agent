import{S as r}from"./index-BWbDOt8M.js";import"./index-9Ev7iYt6.js";const o="oitBackBlendPixelShader",e=`precision highp float;uniform sampler2D uBackColor;void main() {glFragColor=texelFetch(uBackColor,ivec2(gl_FragCoord.xy),0);if (glFragColor.a==0.0) { 
discard;}}`;r.ShadersStore[o]||(r.ShadersStore[o]=e);const l={name:o,shader:e};export{l as oitBackBlendPixelShader};

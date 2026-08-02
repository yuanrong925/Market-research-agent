import{S as r}from"./index-BWbDOt8M.js";import"./helperFunctions-Zy_8Hamf.js";import"./index-9Ev7iYt6.js";const e="rgbdEncodePixelShader",t=`varying vUV: vec2f;var textureSamplerSampler: sampler;var textureSampler: texture_2d<f32>;
#include<helperFunctions>
#define CUSTOM_FRAGMENT_DEFINITIONS
@fragment
fn main(input: FragmentInputs)->FragmentOutputs {fragmentOutputs.color=toRGBD(textureSample(textureSampler,textureSamplerSampler,input.vUV).rgb);}`;r.ShadersStoreWGSL[e]||(r.ShadersStoreWGSL[e]=t);const m={name:e,shader:t};export{m as rgbdEncodePixelShaderWGSL};

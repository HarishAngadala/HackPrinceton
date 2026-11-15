// Adapted from Componentry Prism Gradient. Copyright 2026 Harsh Jadhav.
// MIT license: COMPONENTRY-LICENSE.txt
(() => {
const VERTEX_SHADER = `#version 300 es
in vec4 a_position;
void main() {
  gl_Position = a_position;
}`;
const FRAGMENT_SHADER = `#version 300 es
precision highp float;

uniform float u_time;
uniform float u_pixelRatio;
uniform vec2 u_resolution;
uniform float u_scale;
uniform float u_rotation;
uniform vec4 u_color1;
uniform vec4 u_color2;
uniform vec4 u_color3;
uniform float u_proportion;
uniform float u_softness;
uniform float u_shapeScale;
uniform float u_distortion;
uniform float u_swirl;
uniform float u_swirlIterations;

out vec4 fragColor;

#define TWO_PI 6.28318530718
#define PI 3.14159265358979323846

vec2 rotate(vec2 uv, float th) {
  return mat2(cos(th), sin(th), -sin(th), cos(th)) * uv;
}

float random(vec2 st) {
  return fract(sin(dot(st.xy, vec2(12.9898, 78.233))) * 43758.5453123);
}

float noise(vec2 st) {
  vec2 i = floor(st);
  vec2 f = fract(st);
  float a = random(i);
  float b = random(i + vec2(1.0, 0.0));
  float c = random(i + vec2(0.0, 1.0));
  float d = random(i + vec2(1.0, 1.0));
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

vec4 blendColors(vec4 c1, vec4 c2, vec4 c3, float mixer, float edgesWidth, float edgeBlur) {
  vec3 color1 = c1.rgb * c1.a;
  vec3 color2 = c2.rgb * c2.a;
  vec3 color3 = c3.rgb * c3.a;
  float r1 = smoothstep(.0 + .35 * edgesWidth, .7 - .35 * edgesWidth + .5 * edgeBlur, mixer);
  float r2 = smoothstep(.3 + .35 * edgesWidth, 1. - .35 * edgesWidth + edgeBlur, mixer);
  vec3 blendedColor2 = mix(color1, color2, r1);
  float blendedOpacity2 = mix(c1.a, c2.a, r1);
  vec3 color = mix(blendedColor2, color3, r2);
  float opacity = mix(blendedOpacity2, c3.a, r2);
  return vec4(color, opacity);
}

void main() {
  vec2 uv = gl_FragCoord.xy / u_resolution.xy;
  float time = .5 * u_time;
  float noiseScale = .0005 + .006 * u_scale;

  uv -= .5;
  uv *= noiseScale * u_resolution;
  uv = rotate(uv, u_rotation * .5 * PI);
  uv /= u_pixelRatio;
  uv += .5;

  float n1 = noise(uv + time);
  float n2 = noise(uv * 2. - time);
  float angle = n1 * TWO_PI;
  uv.x += 4. * u_distortion * n2 * cos(angle);
  uv.y += 4. * u_distortion * n2 * sin(angle);

  float iterations = ceil(clamp(u_swirlIterations, 1., 30.));
  for (float i = 1.; i <= iterations; i++) {
    uv.x += clamp(u_swirl, 0., 2.) / i * cos(time + i * 1.5 * uv.y);
    uv.y += clamp(u_swirl, 0., 2.) / i * cos(time + i * uv.x);
  }

  float proportion = clamp(u_proportion, 0., 1.);
  vec2 checksUv = uv * (.5 + 3.5 * u_shapeScale);
  float shape = .5 + .5 * sin(checksUv.x) * cos(checksUv.y);
  float mixer = shape + .48 * sign(proportion - .5) * pow(abs(proportion - .5), .5);
  vec4 colorMix = blendColors(
    u_color1,
    u_color2,
    u_color3,
    mixer,
    1. - clamp(u_softness, 0., 1.),
    .01 + .01 * u_scale
  );
  fragColor = colorMix;
}
`;
const canvas=document.getElementById('prism');
const gl=canvas.getContext('webgl2',{antialias:false,alpha:false});
if(!gl)return;
function compile(type,source){const shader=gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS)){console.warn(gl.getShaderInfoLog(shader));gl.deleteShader(shader);return null;}return shader;}
const vertex=compile(gl.VERTEX_SHADER,VERTEX_SHADER),fragment=compile(gl.FRAGMENT_SHADER,FRAGMENT_SHADER);
if(!vertex||!fragment)return;
const program=gl.createProgram();gl.attachShader(program,vertex);gl.attachShader(program,fragment);gl.linkProgram(program);
if(!gl.getProgramParameter(program,gl.LINK_STATUS))return;
gl.useProgram(program);
const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
const position=gl.getAttribLocation(program,'a_position');gl.enableVertexAttribArray(position);gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
const uniform=name=>gl.getUniformLocation(program,name),time=uniform('u_time'),resolution=uniform('u_resolution');
function resize(){canvas.width=Math.max(1,innerWidth);canvas.height=Math.max(1,innerHeight);gl.viewport(0,0,canvas.width,canvas.height);}
resize();window.addEventListener('resize',resize);
for(const [name,value] of Object.entries({u_pixelRatio:1,u_scale:.01,u_rotation:-50*Math.PI/180,u_proportion:.35,u_softness:.47,u_shapeScale:.45,u_distortion:0,u_swirl:.5,u_swirlIterations:16}))gl.uniform1f(uniform(name),value);
gl.uniform4fv(uniform('u_color1'),[5/255,5/255,5/255,1]);gl.uniform4fv(uniform('u_color2'),[102/255,179/255,1,1]);gl.uniform4fv(uniform('u_color3'),[1,1,1,1]);
const motion=matchMedia('(prefers-reduced-motion: reduce)');let frame,last=-Infinity;
function draw(now){if(now-last>=1000/30){last=now;gl.uniform1f(time,motion.matches?-2.99:now/1000*.65-2.99);gl.uniform2f(resolution,canvas.width,canvas.height);gl.drawArrays(gl.TRIANGLES,0,6);}if(!motion.matches)frame=requestAnimationFrame(draw);}
function resume(){cancelAnimationFrame(frame);if(!document.hidden){last=-Infinity;frame=requestAnimationFrame(draw);}}
document.addEventListener('visibilitychange',resume);motion.addEventListener('change',resume);
canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();cancelAnimationFrame(frame);});
window.addEventListener('pagehide',()=>{cancelAnimationFrame(frame);gl.deleteBuffer(buffer);gl.deleteProgram(program);gl.deleteShader(vertex);gl.deleteShader(fragment);});
frame=requestAnimationFrame(draw);
})();

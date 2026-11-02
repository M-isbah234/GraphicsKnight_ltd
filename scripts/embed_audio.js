const fs = require('fs');
const path = require('path');

const rootDir = path.resolve(__dirname, '..');
const introPath = path.join(rootDir, 'audio', 'intro.mp3');
const loopPath = path.join(rootDir, 'audio', 'loop.mp3');
const indexPath = path.join(rootDir, 'index.html');
const appJsPath = path.join(rootDir, 'js', 'app.js');

const introB64 = fs.readFileSync(introPath).toString('base64');
const loopB64 = fs.readFileSync(loopPath).toString('base64');

console.log('Intro b64 length:', introB64.length);
console.log('Loop b64 length:', loopB64.length);

let indexContent = fs.readFileSync(indexPath, 'utf-8');

// Replace the mehak.studio audio fallbacks
const oldAudioBlock = `  function mk(){if(intro)return;intro=new Audio();intro.preload="auto";intro.src=src("intro");intro.onerror=()=>{if(!intro.src.includes("mehak.studio"))intro.src="https://mehak.studio/audio/intro.mp3"};loop=new Audio();loop.preload="auto";loop.loop=true;loop.src=src("loop");loop.onerror=()=>{if(!loop.src.includes("mehak.studio"))loop.src="https://mehak.studio/audio/loop.mp3"};`;
const newAudioBlock = `  function mk(){if(intro)return;intro=new Audio();intro.preload="auto";intro.src=src("intro");loop=new Audio();loop.preload="auto";loop.loop=true;loop.src=src("loop");`;

if (indexContent.includes(oldAudioBlock)) {
  indexContent = indexContent.replace(oldAudioBlock, newAudioBlock);
} else {
  console.log('Notice: oldAudioBlock not matched exactly in index.html, will do regex replacement if needed.');
}

// Embed window.__AUD before const SND
const audDef = `window.__AUD = { intro: "data:audio/mp3;base64,${introB64}", loop: "data:audio/mp3;base64,${loopB64}" };\n`;

if (!indexContent.includes('window.__AUD = {')) {
  indexContent = indexContent.replace('const SND=(()=>{', audDef + 'const SND=(()=>{');
} else {
  // Update existing window.__AUD
  indexContent = indexContent.replace(/window\.__AUD\s*=\s*\{[\s\S]*?\};\n/, audDef);
}

fs.writeFileSync(indexPath, indexContent, 'utf-8');
console.log('Successfully updated index.html with embedded audio!');

// Also update js/app.js
let appJsContent = fs.readFileSync(appJsPath, 'utf-8');
if (appJsContent.includes(oldAudioBlock)) {
  appJsContent = appJsContent.replace(oldAudioBlock, newAudioBlock);
  fs.writeFileSync(appJsPath, appJsContent, 'utf-8');
  console.log('Updated js/app.js audio block.');
}

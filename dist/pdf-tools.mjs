import * as pdfjs from './vendor/pdf.mjs';
import {inferGrid} from './library.mjs';
import {layout,marks,annotations,MM_TO_PT as PT} from './layout.mjs';
pdfjs.GlobalWorkerOptions.workerSrc=new URL('./vendor/pdf.worker.mjs',import.meta.url).href;
export async function inspectPDF(bytes,page=1){
  await PDFLib.PDFDocument.load(bytes.slice());
  const task=pdfjs.getDocument({data:bytes.slice(),isEvalSupported:false,cMapUrl:new URL('./vendor/cmaps/',import.meta.url).href,cMapPacked:true,standardFontDataUrl:new URL('./vendor/standard_fonts/',import.meta.url).href,wasmUrl:new URL('./vendor/wasm/',import.meta.url).href});
  const doc=await task.promise;
  try{
    if(!Number.isInteger(page)||page<1||page>doc.numPages)throw Error('页面不存在。');
    const p=await doc.getPage(page),v=p.getViewport({scale:1}),view=p.getViewport({scale:Math.min(1.8,1000/Math.max(v.width,v.height))});
    const canvas=document.createElement('canvas');canvas.width=Math.ceil(view.width);canvas.height=Math.ceil(view.height);
    await p.render({canvasContext:canvas.getContext('2d'),viewport:view}).promise;
    const text=(await p.getTextContent()).items.map(i=>i.str).join(' ');

    return {preview:canvas.toDataURL('image/png'),paperW:v.width/PT,paperH:v.height/PT,pages:doc.numPages,inferred:inferGrid(text)};
  }finally{await task.destroy();}
}
async function normalize(bytes,page){
  const {PDFDocument,degrees}=PDFLib,src=await PDFDocument.load(bytes.slice()),p=src.getPage(page-1),box=p.getCropBox(),rot=((p.getRotation().angle%360)+360)%360;
  const out=await PDFDocument.create(),art=await out.embedPage(p,{left:box.x,bottom:box.y,right:box.x+box.width,top:box.y+box.height});
  const swap=rot===90||rot===270,pg=out.addPage(swap?[box.height,box.width]:[box.width,box.height]);
  const position=rot===90?{x:0,y:box.width,rotate:degrees(-90)}:rot===180?{x:box.width,y:box.height,rotate:degrees(180)}:rot===270?{x:box.height,y:0,rotate:degrees(90)}:{x:0,y:0};
  pg.drawPage(art,{width:box.width,height:box.height,...position});return out.save();
}
export async function repeatPDF(bytes,page,count){
  if(!Number.isSafeInteger(count)||count<1||count>500)throw Error('单次最多生成500页，请减少本次数量后分批打印。');
  const {PDFDocument,PDFName}=PDFLib,pdf=await PDFDocument.create();
  const [art]=await pdf.embedPdf(await normalize(bytes,page),[0]);
  pdf.catalog.set(PDFName.of('ViewerPreferences'),pdf.context.obj({PrintScaling:'None',PickTrayByPDFSize:true,NumCopies:1}));
  pdf.setTitle(`标签整版打印 - ${count}张纸`);pdf.setCreator('标签用量助手');
  for(let i=0;i<count;i++)pdf.addPage([art.width,art.height]).drawPage(art,{x:0,y:0,width:art.width,height:art.height});
  return pdf.save();
}
function decode64(s){return Uint8Array.from(atob(s),c=>c.charCodeAt(0));}
export async function projectToPDF(project){
  if(project?.app!=='label-sheet-studio'||!project.source?.data||!project.state)throw Error('无法识别尺切拼版工程。');
  const s=project.state,l=layout(s);if(l.error)throw Error(l.error);
  if(s.exportMode==='cut')throw Error('这是仅裁切模板工程，请先在尺切网页导出含图稿的PDF。');
  const input=decode64(project.source.data);if(input.length>30*1024*1024)throw Error('工程图稿超过30MB。');
  let sourcePDF;
  if(/\.svg$/i.test(project.source.name)){
    const el=new DOMParser().parseFromString(new TextDecoder().decode(input),'image/svg+xml').documentElement;
    if(el.localName!=='svg'||el.querySelector('parsererror,style,link,script,foreignObject,iframe,animate,set'))throw Error('SVG工程含不支持的内容，请先从尺切网页导出PDF。');
    for(const node of [el,...el.querySelectorAll('*')])for(const a of node.attributes){
      if(/^on/i.test(a.name)||(/href$/i.test(a.name)&&!a.value.startsWith('#')&&!/^data:image\/(png|jpeg);base64,/i.test(a.value))||/url\(|@import/i.test(a.value)||node.localName==='style')throw Error('SVG工程含外部或动态资源，请先导出PDF。');
    }
    const sw=+el.getAttribute('width')?.replace('mm',''),sh=+el.getAttribute('height')?.replace('mm','');
    if(!(sw>0&&sh>0))throw Error('SVG工程尺寸无法识别，请先导出PDF。');
    const js=new jspdf.jsPDF({unit:'pt',format:[sw*PT,sh*PT],orientation:sw>sh?'landscape':'portrait',compress:true});
    const host=document.createElement('div');host.style.cssText='position:fixed;left:-10000px;visibility:hidden';host.append(el);document.body.append(host);
    try{await js.svg(el,{x:0,y:0,width:sw*PT,height:sh*PT});sourcePDF=new Uint8Array(js.output('arraybuffer'));}finally{host.remove();}
  }else sourcePDF=await normalize(input,project.source.page||1);
  const {PDFDocument,rgb,degrees}=PDFLib,pdf=await PDFDocument.create(),pg=pdf.addPage([l.pw*PT,l.ph*PT]);
  const [art]=await pdf.embedPdf(sourcePDF,[0]);
  for(const c of l.cells){if(s.rotate)pg.drawPage(art,{x:c.x*PT,y:(l.ph-c.y)*PT,width:c.h*PT,height:c.w*PT,rotate:degrees(-90)});else pg.drawPage(art,{x:c.x*PT,y:(l.ph-c.y-c.h)*PT,width:c.w*PT,height:c.h*PT});}
  if(s.exportMode!=='art'){
    for(const a of marks(l))pg.drawLine({start:{x:a[0]*PT,y:(l.ph-a[1])*PT},end:{x:a[2]*PT,y:(l.ph-a[3])*PT},thickness:.12*PT,color:rgb(.08,.08,.08)});
    if(s.numbering){pdf.registerFontkit(fontkit);const font=await pdf.embedFont(await(await fetch(new URL('./fonts/LabelAnnotations-Medium.ttf',import.meta.url))).arrayBuffer(),{subset:true});for(const a of annotations(l)){const size=a.size*PT;pg.drawText(a.text,{x:a.x*PT-font.widthOfTextAtSize(a.text,size)/2,y:(l.ph-a.y)*PT,size,font,color:rgb(.08,.08,.08)});}}
  }
  return {bytes:await pdf.save(),cols:l.cols,rows:l.rows};
}

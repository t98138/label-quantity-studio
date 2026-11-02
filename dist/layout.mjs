export const MM_TO_PT=72/25.4;
export const DEFAULT_SAFE=10;
export const MIN_SAFE=7; // Reserve space for the footer and crop marks.
export function layout(s){
  const p=s.paper==='A3'?[297,420]:s.paper==='A4'?[210,297]:[+s.paperW,+s.paperH];
  if(s.landscape&&s.paper!=='custom')p.reverse();
  const w=+(s.rotate?s.labelH:s.labelW),h=+(s.rotate?s.labelW:s.labelH);
  const cols=+s.cols,rows=+s.rows,gx=+s.gapX,gy=+s.gapY;
  const safeX=+(s.safeX??DEFAULT_SAFE),safeY=+(s.safeY??DEFAULT_SAFE);
  const bw=w*cols+gx*(cols-1),bh=h*rows+gy*(rows-1);
  const x=(p[0]-bw)/2,y=(p[1]-bh)/2;
  const error=![...p,w,h,cols,rows,gx,gy,safeX,safeY].every(Number.isFinite)?'请输入有效数字。':p.some(v=>v<30||v>1200)?'纸张尺寸须为 30–1200 mm。':w<=0||h<=0?'标签尺寸必须大于 0。':!Number.isInteger(cols)||!Number.isInteger(rows)||cols<1||rows<1?'行数和列数须为正整数。':cols*rows>2000?'每页最多支持 2000 张标签。':gx<0||gy<0?'标签间距不能小于 0。':safeX<MIN_SAFE||safeY<MIN_SAFE||safeX>600||safeY>600?'横向和纵向安全距离须为 7–600 mm。':x<safeX-1e-7||y<safeY-1e-7?'拼版超出安全区域，请减少行列、调整标签尺寸或换用更大纸张。':'';
  const cells=[];
  if(!error)for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)cells.push({x:x+c*(w+gx),y:y+r*(h+gy),w,h,r,c});
  const unique=a=>[...new Set(a.map(v=>Math.round(v*1e6)/1e6))].sort((a,b)=>a-b);
  const xs=unique(Array.from({length:Math.min(2001,Math.max(0,cols))},(_,i)=>[x+i*(w+gx),x+i*(w+gx)+w]).flat());
  const ys=unique(Array.from({length:Math.min(2001,Math.max(0,rows))},(_,i)=>[y+i*(h+gy),y+i*(h+gy)+h]).flat());
  return {pw:p[0],ph:p[1],w,h,cols,rows,gx,gy,safeX,safeY,bw,bh,x,y,total:cols*rows,cells,xs,ys,error};
}
export function autoFit(s){
  const l=layout({...s,cols:1,rows:1});
  if(l.error)return null;
  const cols=Math.floor((l.pw-2*l.safeX+l.gx+1e-7)/(l.w+l.gx)),rows=Math.floor((l.ph-2*l.safeY+l.gy+1e-7)/(l.h+l.gy));
  return cols>=1&&rows>=1&&cols*rows<=2000?{cols,rows}:null;
}
export function marks(l,full=false){
  const a=[];
  const topReach=l.y<8.5?Math.min(4,Math.max(1.5,l.y-4.56)):4;
  for(const x of l.xs){a.push([x,l.y-topReach,x,l.y-1],[x,l.y+l.bh+1,x,l.y+l.bh+3]);if(full)a.push([x,l.y,x,l.y+l.bh]);}
  const sideReach=l.x<8.5?Math.min(4,Math.max(1.5,l.x-4.56)):4;
  const sideGap=l.x<8.5?.25:1;
  for(const y of l.ys){a.push([l.x-sideReach,y,l.x-sideGap,y],[l.x+l.bw+sideGap,y,l.x+l.bw+sideReach,y]);if(full)a.push([l.x,y,l.x+l.bw,y]);}
  return a;
}
export function annotations(l){
  const text=`共 ${l.total} 张｜${l.cols} 列 × ${l.rows} 行`;
  const footerSize=Math.min((l.y>=8&&l.y<9?8:10)/MM_TO_PT,(l.pw-4)/text.length);
  // In the 8–12 mm footer band, keep ink inside a 4.5 mm printable inset.
  // Put compact summaries between column cut marks, rather than on top of them.
  const compact=l.y>=8&&l.y<12;
  const footerY=compact?Math.min(l.y+l.bh+6.3,l.ph-4.5-footerSize*.3):l.y+l.bh+6.3;
  let a;
  if(compact&&l.cols>=2&&l.w<40){
    const first=Math.max(0,Math.floor(l.cols/2)-1);
    const parts=[`共 ${l.total} 张`,`${l.cols} 列 × ${l.rows} 行`];
    a=parts.map((text,i)=>({x:l.x+(first+i)*(l.w+l.gx)+l.w/2,y:footerY,text,size:Math.min(footerSize,(l.w-2)/(text.length*.7))}));
  }else a=[{x:l.pw/2,y:footerY,text,size:footerSize}];
  const colDigits=String(l.cols).padStart(2,'0').length,rowDigits=String(l.rows).padStart(2,'0').length;
  const colSize=Math.min(9/MM_TO_PT,l.w/(colDigits*.75));
  const rowSize=Math.min(9/MM_TO_PT,l.h*.8,Math.max(.5,l.x-5.1)/(rowDigits*.65));
  const rowX=Math.max(l.x-5,4.5+rowSize*rowDigits*.65/2);
  const colY=Math.max(l.y-2.2,4.5+colSize*.72);
  for(let c=0;c<l.cols;c++)a.push({x:l.x+c*(l.w+l.gx)+l.w/2,y:colY,text:String(c+1).padStart(2,'0'),size:colSize});
  for(let r=0;r<l.rows;r++)a.push({x:rowX,y:l.y+r*(l.h+l.gy)+l.h/2+rowSize*.36,text:String(r+1).padStart(2,'0'),size:rowSize});
  return a;
}

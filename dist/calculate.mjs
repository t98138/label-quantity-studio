export function calculate(quantity, cols, rows) {
  if (![quantity, cols, rows].every(Number.isSafeInteger) || quantity < 1 || cols < 1 || rows < 1) throw Error('请输入大于0的整数。');
  const capacity=cols*rows;
  if (!Number.isSafeInteger(capacity) || capacity>1000000) throw Error('每纸容量超出支持范围。');
  const sheets=Math.ceil(quantity/capacity), fullSheets=Math.floor(quantity/capacity), remainder=quantity%capacity;
  const produced=sheets*capacity;
  if (!Number.isSafeInteger(produced)) throw Error('数量过大，请分批计算。');
  return {quantity,cols,rows,capacity,sheets,fullSheets,remainder,fullRows:Math.floor(remainder/cols),extraLabels:remainder%cols,produced,surplus:produced-quantity};
}
export function breakdown(r) {
  if (!r.remainder) return `${r.fullSheets}张整纸，刚好够用`;
  const parts=[];
  if(r.fullSheets)parts.push(`${r.fullSheets}张整纸`);
  const tail=(r.fullRows?`${r.fullRows}行`:'')+(r.extraLabels?`${r.extraLabels}枚`:'');
  if(tail)parts.push(tail);
  return parts.join('＋');
}

const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../docs/index.html'),'utf8');
const script=html.match(/<script id="mt-model">([\s\S]*?)<\/script>/)[1];
const context=vm.createContext({});vm.runInContext(script,context);const model=context.MTModel;
let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',data=>input+=data);
process.stdin.on('end',()=>{
 const cases=JSON.parse(input);
 function near(a,b,label){assert.ok(Number.isFinite(a)&&Math.abs(a-b)<1e-9*Math.max(1,Math.abs(b)),`${label}: ${a} != ${b}`);}
 for(const test of cases){
  if(test.error){assert.throws(()=>model.solve(test.inputs));continue;}
  const actual=model.solve(test.inputs),expected=test.result;
  for(const key of ['N_trays_integer','feed_stage_from_top'])assert.equal(actual.summary[key],expected.summary[key]);
  near(actual.summary.N_trays_fractional,expected.summary.N_trays_fractional,'fractional trays');
  for(const key of Object.keys(expected.operating))near(actual.operating[key],expected.operating[key],key);
  assert.equal(actual.stages.length,expected.stages.length);
  actual.stages.forEach((row,i)=>{near(row.x,expected.stages[i].x,'x');near(row.y,expected.stages[i].y,'y');assert.equal(row.section,expected.stages[i].section);});
  assert.equal(actual.staircase.length,expected.staircase.length);
  actual.staircase.forEach((point,i)=>point.forEach((v,j)=>near(v,expected.staircase[i][j],'staircase')));
  const qline=model.series(actual).find(s=>s.name==='q-line');for(const point of qline.points)for(const v of point)assert.ok(v>=-1e-10&&v<=1+1e-10);
 }
 console.log(`PASS: ${cases.length} web/Python cases; operating lines, stage compositions, counts, q-line and staircase match.`);
});

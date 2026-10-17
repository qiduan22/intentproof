"""Offline generator tests only; these do not simulate an external RTL proof."""
import importlib.util,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import upstream_benchmark as u

# Intentionally tiny invented fixture. Not included in final upstream-results
# counts; used exclusively to test wrapper/config generation without network.
FIXTURE='''`default_nettype none
module sfifo #(parameter BW=8,parameter LGFLEN=2,
parameter OPT_ASYNC_READ=1,OPT_WRITE_ON_FULL=0,OPT_READ_ON_EMPTY=0)(
 input wire i_clk,i_reset,i_wr,i_rd,input wire [BW-1:0] i_data,
 output wire o_full,output wire o_empty, output reg [LGFLEN:0] o_fill,
 output wire [BW-1:0] o_data);
 reg r_empty; reg [LGFLEN:0] wr_addr,rd_addr;
 reg [BW-1:0] mem[0:(1<<LGFLEN)-1];
 wire take_write = (i_wr && !o_full);
 wire take_read = (i_rd && !o_empty);
 initial begin o_fill=0; r_empty=1;wr_addr=0;rd_addr=0;end
 always @(posedge i_clk) begin
 if(i_reset) begin o_fill<=0; r_empty<=1;wr_addr<=0;rd_addr<=0;end
 else begin
 case({take_write,take_read}) 2'b01: o_fill<=o_fill-1;2'b10:o_fill<=o_fill+1;endcase
 case({take_write,take_read}) 2'b01:r_empty<=(o_fill<=1);2'b10:r_empty<=0;endcase
 if(take_write)wr_addr<=wr_addr+1;
 if(take_read)rd_addr<=rd_addr+1;
 end
 if(take_write)mem[wr_addr[LGFLEN-1:0]]<=i_data;
 end
 wire r_full=o_fill[LGFLEN];
 assign o_full = (i_rd && OPT_WRITE_ON_FULL) ? 1'b0 : r_full;
 assign o_empty=r_empty;
 assign o_data=mem[rd_addr[LGFLEN-1:0]];
 `ifdef FORMAL
  wire f_test;
  `ifdef F_PEEK
  wire f_deeper;
  `endif
 `endif
endmodule
`default_nettype wire
'''
class TestGenerator(unittest.TestCase):
 def test_source_preserved_without_ad_hoc_preprocessing(self):
  txt=u.validate_upstream_rtl(FIXTURE)
  self.assertEqual(txt,FIXTURE)
  self.assertIn('`ifdef FORMAL',txt)
  self.assertNotIn('wire w_wr',txt)  # old benchmark failed here for no reason
 def test_mutation(self):
  txt=u.mutate(u.validate_upstream_rtl(FIXTURE))
  self.assertIn("assign o_full = 1'b0; // INTENT2PROOF INJECTED",txt)
  self.assertNotIn('wire w_wr',txt)
  with self.assertRaises(ValueError):u.mutate(txt)
  with self.assertRaises(ValueError):u.mutate('module sfifo; endmodule')
 def test_sby_reads_original_in_synthesis_mode(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)
   for kind in ('full','coi','contract','mutant','cover'):
    cfg=u.sby_config(kind,'config',p/'bench.v',p/'sfifo.v',p,30,'abc pdr')
    t=cfg.read_text()
    self.assertIn('[script]\nread_verilog -sv sfifo.v\n',t)
    self.assertIn('read_verilog -formal -sv bench.v\n',t)
    self.assertNotIn('read_verilog -formal -sv sfifo.v',t)
    self.assertEqual(t.count('read_verilog -formal -sv ref.v'),1 if kind=='contract' else 0)
 def test_generated_wrappers(self):
  for kind in ['full','coi','contract','mutant','cover']:
   t=u.wrapper(kind,3,16)
   self.assertIn('assert(o_fill == external_count)',t)
   self.assertIn('module intent2proof_bench',t)
  self.assertIn('output wire [15:0] exposed_data',u.wrapper('full',3,16))
  self.assertNotIn('exposed_data',u.wrapper('coi',3,16))
 def test_prepare_only_with_fixture(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td); repo=p/'repo'; (repo/'rtl').mkdir(parents=True)
   (repo/u.RTL).write_text(FIXTURE)
   subprocess.run(['git','init',str(repo)],capture_output=True,check=True)
   subprocess.run(['git','-C',str(repo),'add',u.RTL],check=True)
   subprocess.run(['git','-C',str(repo),'-c','user.email=test@example.invalid','-c','user.name=Test','commit','-m','fixture'],capture_output=True,check=True)
   work=p/'work'
   run=subprocess.run([sys.executable,str(ROOT/'upstream_benchmark.py'),'--repo-path',str(repo),'--work',str(work),'--offline','--only-prepare'],capture_output=True,text=True)
   self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr)
   self.assertEqual(len(list(work.glob('*.sby'))),15)
   # SBY [files] aliases must supply the names used in [script].
   for cfg in work.glob('*.sby'):
    body=cfg.read_text()
    self.assertIn('read_verilog -sv sfifo.v\nread_verilog -formal -sv bench.v',body)
    self.assertIn('[files]\nsfifo.v ',body)
    self.assertIn('\nbench.v ',body)
    self.assertTrue((work/'source_synthesis_view.v').exists())
    self.assertEqual((work/'source_synthesis_view.v').read_bytes(), (repo/u.RTL).read_bytes())
    if cfg.stem.endswith('_contract'):
     self.assertIn('read_verilog -formal -sv ref.v',body)
     self.assertIn('\nref.v ',body)
    else:
     self.assertNotIn('\nref.v ',body)
   rows=json.loads((work/'benchmark_results.json').read_text())
   self.assertEqual(len(rows),15)
   self.assertTrue(all(r['status']=='NOT_RUN' for r in rows))
   self.assertEqual(len(json.loads((work/'manifest.json').read_text())['repository_commit_sha']),40)
   self.assertIn('INTENT2PROOF', (work/'source_mutant.v').read_text())
   # Dirty upstream source must block unsupported commit-based provenance.
   (repo/u.RTL).write_text(FIXTURE+'\n// dirty\n')
   dirty=subprocess.run([sys.executable,str(ROOT/'upstream_benchmark.py'),'--repo-path',str(repo),'--work',str(p/'dirty'),'--offline','--only-prepare'],capture_output=True,text=True)
   self.assertNotEqual(dirty.returncode,0)
 def test_expected_mutant_failure_nonzero_exit(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td)/'sfifo_LG2_BW8_mutant_task';d.mkdir()
   (d/'status').write_text('FAIL\n')
   # SBY generally reports a counterexample by nonzero exit code.
   self.assertEqual(u.analyze_status(d,{'execution':'NONZERO_EXIT','exit_code':1}),'PROPERTY_FAILED')
   self.assertEqual(u.analyze_status(d,{'execution':'TIMEOUT','exit_code':None}),'NOT_PROVED_TIMEOUT')
 def test_pass_requires_completed_exit(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td)/'sfifo_LG2_BW8_full_task';d.mkdir()
   (d/'status').write_text('PASS\n')
   self.assertEqual(u.analyze_status(d,{'execution':'COMPLETED','exit_code':0}),'PROVED')
   self.assertNotEqual(u.analyze_status(d,{'execution':'NONZERO_EXIT','exit_code':2}),'PROVED')

 def test_strict_gate_rejects_unrun_and_unknown(self):
  from gate_upstream_results import audit
  with tempfile.TemporaryDirectory() as td:
   self.assertFalse(audit(Path(td))['accepted'])
   p=Path(td)
   (p/'manifest.json').write_text(json.dumps({"repository_commit_sha":"0"*40,
     "source":"rtl/sfifo.v","source_sha256":"0"*64,
     "synthesis_view_sha256":"1"*64,"mutant_sha256":"2"*64}))
   (p/'benchmark_results.json').write_text(json.dumps([{"variant":"sfifo_LG2_BW8",
     "case":"full","status":"UNKNOWN"}]))
   self.assertFalse(audit(p)['accepted'])

if __name__=='__main__':unittest.main()

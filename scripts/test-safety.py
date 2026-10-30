#!/usr/bin/env python3
# Exercise ownership and destructive-script refusal paths without cloud access.
import json, os, subprocess, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

class SafetyTests(unittest.TestCase):
    def test_replica_migration_preserves_other_historical_fields(self):
        previous = {'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':'web-app','namespace':'web-app'},'spec':{'replicas':2,'obsolete':'must remain until apply'}}
        live = {'spec':{'replicas':8},'metadata':{'annotations':{'kubectl.kubernetes.io/last-applied-configuration':json.dumps(previous)}}}
        output = subprocess.check_output(['python3',str(ROOT/'scripts/migrate-replicas.py')], input=json.dumps(live), text=True)
        result = json.loads(output)
        self.assertNotIn('replicas',result['spec'])
        self.assertEqual(result['spec']['obsolete'],'must remain until apply')
        self.assertEqual(live['spec']['replicas'],8)
        live['metadata']['annotations']['kubectl.kubernetes.io/last-applied-configuration']=output
        self.assertEqual(subprocess.check_output(['python3',str(ROOT/'scripts/migrate-replicas.py')],input=json.dumps(live),text=True),'')
    def run_teardown(self, flags=(), overrides=None, answers=''):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)
            stub = r'''#!/usr/bin/env python3
import json,os,sys
args=sys.argv[1:]
with open(os.environ['CALLS'],'a') as f: f.write(json.dumps([os.path.basename(sys.argv[0])]+args)+'\n')
cmd=' '.join(args)
if 'current-context' in cmd: print(os.environ.get('MOCK_CONTEXT','do-sfo3-web-app-cluster'))
elif 'config view' in cmd: print(os.environ.get('MOCK_ENDPOINT','https://expected'))
elif 'cluster get' in cmd: print('[{"id":"cluster-id","endpoint":"https://expected"}]')
elif 'registry get' in cmd: print(os.environ.get('MOCK_REGISTRY','pooja-doks-demo-2026'))
elif 'delete namespace' in cmd and os.environ.get('FAIL_DELETE'): sys.exit(1)
'''
            for tool in ['kubectl','doctl']:
                (path/tool).write_text(stub); (path/tool).chmod(0o755)
            env={**os.environ,'PATH':f'{path}:'+os.environ['PATH'],'CALLS':str(path/'calls'),**(overrides or {})}
            run=subprocess.run(['bash',str(ROOT/'scripts/99-teardown.sh'),*flags],input=answers,text=True,capture_output=True,env=env)
            calls=[json.loads(line) for line in (path/'calls').read_text().splitlines()]
            mutations=[c for c in calls if 'delete' in c]
            return run, mutations
    def test_default_is_read_only(self):
        run, mutations=self.run_teardown(); self.assertEqual(run.returncode,0,run.stderr); self.assertEqual(mutations,[])
    def test_wrong_context_endpoint_and_registry_refuse_before_mutation(self):
        for env in [{'MOCK_CONTEXT':'production'},{'MOCK_ENDPOINT':'https://wrong'},{'MOCK_REGISTRY':'shared-registry'}]:
            run, mutations=self.run_teardown(['--execute','--delete-registry'],env,'delete cluster-id\npooja-doks-demo-2026\n')
            self.assertNotEqual(run.returncode,0); self.assertEqual(mutations,[])
    def test_failed_namespace_deletion_stops_cluster_deletion(self):
        run, mutations=self.run_teardown(['--execute'],{'FAIL_DELETE':'1'},'delete cluster-id\n')
        self.assertNotEqual(run.returncode,0); self.assertEqual(len(mutations),1); self.assertIn('namespace',mutations[0])
    def test_cancelled_confirmation_does_not_delete(self):
        run, mutations=self.run_teardown(['--execute'],answers='no\n')
        self.assertNotEqual(run.returncode,0); self.assertEqual(mutations,[])
    def test_confirmed_cluster_preserves_registry_and_associated_resources(self):
        run, mutations=self.run_teardown(['--execute'],answers='delete cluster-id\n')
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(len(mutations),2)
        self.assertIn('cluster-id',mutations[1]); self.assertNotIn('--dangerous',mutations[1])
    def test_selected_registry_is_not_force_deleted(self):
        run, mutations=self.run_teardown(['--execute','--delete-registry'],answers='delete cluster-id\npooja-doks-demo-2026\n')
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(mutations[-1],['doctl','registry','delete'])

if __name__=='__main__': unittest.main(verbosity=2)

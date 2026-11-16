import copy
import unittest
from medcalc.source_repair import make_source_packet,repair_call,role_candidates
from medcalc.enforcement import Rejected
from medcalc.registry import SPECS

class SourceRepairTests(unittest.TestCase):
    def call(self,cid,quantities):
        return {'calculator_id':cid,'formula_version':SPECS[cid]['version'],
                'arguments':{k:{'value':v,'unit':u,'evidence_id':'model'} for k,(v,u) in quantities.items()}}
    def execute(self,call,note):return repair_call(call,make_source_packet(call['calculator_id'],note),note)
    def test_unit_label_error_is_repaired(self):
        c=self.call('6',{'height':(170,'m'),'weight':(57,'kg')})
        out=self.execute(c,'Height 170 cm, weight 57 kg.')
        self.assertAlmostEqual(out['result'],57/1.7**2)
        self.assertEqual(out['evidence']['height']['action'],'source_unit_repair')
        self.assertEqual(c['arguments']['height']['unit'],'m')
    def test_mixed_unit_list_roles(self):
        n='Leukocyte count, hemoglobin and platelet count were 5900/µL, 14.7 g/dL and 191000/µL, respectively.'
        obs=role_candidates(n)
        self.assertEqual([(o['value'],o['field_hint']) for o in obs],[(5900,'other'),(14.7,'other'),(191000,'platelets')])
    def test_swapped_enzyme_values_are_repaired_from_unique_named_sources(self):
        c=self.call('19',{'age':(60,'years'),'ast':(16,'U/L'),'alt':(11,'U/L'),'platelets':(191000,'10^9/L')})
        n='A 60-year-old man. AST 11 U/L; ALT 16 U/L; platelets 191000/µL.'
        out=self.execute(c,n)
        self.assertAlmostEqual(out['result'],60*11/(191*4))
    def test_ambiguous_unknown_value_abstains(self):
        c=self.call('6',{'height':(170,'cm'),'weight':(71,'kg')})
        with self.assertRaises(Rejected):self.execute(c,'Height 170 cm. Weight 70 kg. Later weight 72 kg.')
    def test_changed_note_tampered_packet_and_stale_version_reject(self):
        c=self.call('6',{'height':(170,'cm'),'weight':(57,'kg')});n='Height 170 cm, weight 57 kg.';p=make_source_packet('6',n)
        with self.assertRaises(Rejected):repair_call(c,p,n.replace('57','58'))
        p['observations'][0]['unit']='m'
        with self.assertRaises(Rejected):repair_call(c,p,n)
        c['formula_version']='unapproved'
        with self.assertRaises(Rejected):self.execute(c,n)
    def test_bool_is_not_repaired_into_measurement(self):
        c=self.call('6',{'height':(True,'m'),'weight':(57,'kg')})
        with self.assertRaises(Rejected):self.execute(c,'Height 1 m, weight 57 kg.')
    def test_compound_unit_is_not_truncated(self):
        obs=role_candidates('BMI 24 kg/m², urine protein 1 g/g creatinine, height 170 cm.')
        self.assertEqual([(o['value'],o['unit']) for o in obs],[(170,'cm')])
    def test_feet_inches_are_combined(self):
        c=self.call('6',{'height':(1.778,'m'),'weight':(72,'kg')})
        out=self.execute(c,'Height 5 feet 10 inches, weight 72 kg.')
        self.assertAlmostEqual(out['result'],72/1.778**2)
    def test_later_matching_value_is_remaining_limitation(self):
        c=self.call('6',{'height':(170,'cm'),'weight':(72,'kg')})
        out=self.execute(c,'Height 170 cm. Admission weight 70 kg. Later weight 72 kg.')
        self.assertTrue(out['released'])  # source consistency does not establish timepoint

if __name__=='__main__':unittest.main()

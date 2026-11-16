import copy
import unittest
from medcalc.source_binding import packet_for, execute_selection, observations
from medcalc.enforcement import Rejected

class SourceBindingTests(unittest.TestCase):
    def bmi(self):
        note='A woman is 170 cm tall and weighs 57 kg.'
        p=packet_for('6',note)
        s={'selections':{k:v[0] for k,v in p['allowed'].items()}}
        return note,p,s

    def test_source_unit_is_preserved_then_converted(self):
        note,p,s=self.bmi();out=execute_selection(s,p,note)
        self.assertAlmostEqual(out['result'],57/1.7**2)
        self.assertEqual(out['call']['arguments']['height']['unit'],'cm')

    def test_tampered_value_or_unit_is_rejected(self):
        note,p,s=self.bmi()
        for key,value in [('value',17000),('unit','m')]:
            altered=copy.deepcopy(p);altered['observations'][0][key]=value
            with self.assertRaises(Rejected):execute_selection(s,altered,note)

    def test_changed_source_and_unknown_id_are_rejected(self):
        note,p,s=self.bmi()
        with self.assertRaises(Rejected):execute_selection(s,p,note.replace('57','58'))
        s['selections']['height']='fabricated'
        with self.assertRaises(Rejected):execute_selection(s,p,note)

    def test_blood_pressure_components_cannot_be_swapped(self):
        note='Blood pressure 120/80 mmHg.';p=packet_for('5',note)
        s={'selections':{k:v[0] for k,v in p['allowed'].items()}}
        self.assertAlmostEqual(execute_selection(s,p,note)['result'],280/3)
        s['selections']['sbp']=p['allowed']['dbp'][0]
        with self.assertRaises(Rejected):execute_selection(s,p,note)

    def test_count_scales_and_spaced_thousands(self):
        obs=observations('Platelets 407 × 103/mm3, then 367 000/µL, then 213 × 10^9/L.')
        self.assertEqual([(x['value'],x['unit']) for x in obs],[(407000,'uL'),(367000,'uL'),(213000000000,'L')])

    def test_reference_bounds_are_not_measurements(self):
        obs=observations('Sodium 144 (136-145 mEq/L), glucose 106 (70-105 mg/dL).')
        self.assertEqual([x['value'] for x in obs],[144,106])

    def test_shared_unit_distributed_without_swapping_values(self):
        obs=observations('AST and ALT were 83 and 144 units per liter, respectively.')
        self.assertEqual([(x['value'],x['unit']) for x in obs],[(83,'u/l'),(144,'u/l')])

    def test_missing_source_abstains(self):
        note='Weight is not recorded. Height 1.7 m.';p=packet_for('6',note)
        self.assertEqual(p['allowed']['weight'],[])
        s={'selections':{'height':p['allowed']['height'][0],'weight':'NONE'}}
        with self.assertRaises(Rejected):execute_selection(s,p,note)

    def test_same_dimension_wrong_variable_is_outside_guarantee(self):
        note='Sodium 140 mmol/L; glucose 100 mg/dL.';p=packet_for('26',note)
        sodium=next(o['id'] for o in p['observations'] if o['value']==140)
        # A source-consistent ID may still be clinically misassigned by the LLM.
        out=execute_selection({'selections':{'sodium':sodium,'glucose':sodium}},p,note)
        self.assertTrue(out['released'])

if __name__=='__main__':unittest.main()

import unittest
from medcalc.live import strict_json, check_spans, evaluate_gates, planner_messages, extractor_messages
from medcalc.enforcement import Rejected

class LiveContracts(unittest.TestCase):
    def test_strict_json_rejects_duplicates_nonfinite_and_prose(self):
        for text in ['{"x":1,"x":2}', '{"x":NaN}', 'Here: {"x":1}', '[1,2]']:
            with self.assertRaises(ValueError): strict_json(text)

    def test_unit_normalization_changes_bmi(self):
        call = {'calculator_id':'6','formula_version':'kg-over-m2','arguments':{
            'height':{'value':170,'unit':'cm','evidence_id':'a'},
            'weight':{'value':65,'unit':'kg','evidence_id':'b'}}}
        quotes = {'height':'Height 170 cm', 'weight':'Weight 65 kg'}
        out = evaluate_gates(call, quotes, 'Height 170 cm. Weight 65 kg.')
        self.assertAlmostEqual(out['L2_unit_domain']['result'],65/1.7**2)
        self.assertTrue(out['L3_literal_span']['released'])
        self.assertAlmostEqual(out['L1_schema_only']['result'],65/170**2)

    def test_fabricated_quote_and_value_fail(self):
        c={'arguments':{'age':{'value':33,'unit':'years'}}}
        with self.assertRaises(Rejected): check_spans(c,{'age':'33 years'},'A 34-year-old man.')
        with self.assertRaises(Rejected): check_spans(c,{'age':'34-year-old man'},'A 34-year-old man.')

    def test_partial_quote_gate_does_not_establish_variable_attachment(self):
        # An explicit limitation: a literal number alone can support a wrong field.
        c={'arguments':{'glucose':{'value':140,'unit':'mg/dL'}}}
        check_spans(c,{'glucose':'Sodium 140 mmol/L'},'Sodium 140 mmol/L')

    def test_prompt_builders_only_accept_nongold_inputs(self):
        import inspect
        self.assertEqual(list(inspect.signature(planner_messages).parameters),['question'])
        self.assertEqual(list(inspect.signature(extractor_messages).parameters),['question','note','cid'])

    def test_scorer_counts_abstention_and_wrong_tool(self):
        from score_live import correct, score
        gold = {'calculator_id':'6','ground_truth':'20','lower':'19','upper':'21',
                'quantities':{'height':{'value':2,'unit':'m'},'weight':{'value':80,'unit':'kg'}}}
        wrong = {'selected_calculator_id':'60'}
        self.assertFalse(correct(wrong,{'released':True,'result':20},gold))
        rows=[{'case_id':'a','group_id':'a','source_row':'1','selected_calculator_id':'6',
               'wall_seconds':1,'gates':{'L2_unit_domain':{'released':True,'result':20}}},
              {'case_id':'b','group_id':'b','source_row':'2','wall_seconds':1,
               'workflow_error':'Missing data'}]
        out=score(rows,{'1':gold,'2':gold})['gates']['L2_unit_domain']
        self.assertEqual(out['correct_released'],1)
        self.assertEqual(out['end_to_end_accuracy'],.5)
        self.assertEqual(out['accuracy_among_released'],1)
        self.assertEqual(out['blocked_or_failed'],1)

if __name__ == '__main__': unittest.main()

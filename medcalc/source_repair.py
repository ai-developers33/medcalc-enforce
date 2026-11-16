"""Repair model proposals using source-bound quantities; no reference labels.

A verified canonical source match is preferred; a unique native-number match
repairs a unit label. A sole explicitly named observation can repair a wrong
number. Ambiguous or unsupported proposals abstain. Full clinical semantics and
source correctness are outside this adapter's guarantee.
"""
import copy, hashlib, math, re
from .source_binding import observations, compatible
from .registry import SPECS, canonical_value, calculate
from .enforcement import POLICIES, Rejected, validate

# Neglected non-target labels are included to stop association from crossing a
# different lab measurement. Labels are a source-parser lexicon, not model gold.
LABELS={
 'creatinine':r'creatinine', 'sbp':r'systolic(?: blood)? pressure',
 'dbp':r'diastolic(?: blood)? pressure', 'height':r'height|length|tall',
 'weight':r'weight|weigh(?:ed|s|ing)?', 'calcium':r'calcium|Ca2\+|Ca\+\+',
 'albumin':r'albumin', 'heart_rate':r'heart rate|pulse(?: rate)?',
 'qt':r'QT(?: interval)?',
 'alt':r'alanine (?:amino)?trans(?:aminase|ferase)|ALT|SGPT|glutamic.pyruvic transaminase',
 'ast':r'aspartate (?:amino)?trans(?:aminase|ferase)|AST|SGOT|glutamic.oxaloacetic transaminase',
 'platelets':r'platelets?|platelet counts?', 'glucose':r'glucose|blood sugar',
 'sodium':r'sodium|Na\+', 'bun':r'blood urea nitrogen|BUN',
 'chloride':r'chloride|Cl-', 'bicarbonate':r'bicarbonate|HCO3-?',
 'other':r'potassium|K\+|hemoglobin|haemoglobin|white blood cells?|leukocytes?(?: count)?|WBC|bilirubin|ferritin|phosphorus|phosphate|lactate|amylase|lipase|total protein|alkaline phosphatase|respirations?|respiratory rate|head circumference|QTc|corrected QT|urea(?! nitrogen)',
}
PATTERNS={k:re.compile(r'(?<![A-Za-z])(?:'+v+r')(?![A-Za-z])',re.I) for k,v in LABELS.items()}

def role_candidates(note):
    obs=[o for o in observations(note)
         if not re.match(r'\s*(?:[/^]|[²³⁻])',note[o['end']:o['end']+8])]
    # A complete feet/inches quantity is one length, not two body measurements.
    merged=[];i=0
    while i<len(obs):
        a=obs[i]
        if i+1<len(obs):
            b=obs[i+1]
            if a['unit']=='ft' and b['unit']=='in' and re.fullmatch(r'\s*(?:and\s*)?',note[a['end']:b['start']]):
                c=dict(a,value=a['value']*12+b['value'],unit='in',end=b['end'],
                       source=note[a['start']:b['end']],rule='compound_length',id=a['id']+'c')
                c['context']=note[max(0,c['start']-100):min(len(note),c['end']+70)]
                merged.append(c);i+=2;continue
        merged.append(a);i+=1
    obs=merged
    for o in obs:
        if o['field_hint']:continue
        if o['unit'] in ['years','months','weeks','days']:
            prefix=note[max(0,o['start']-25):o['start']]
            suffix=note[o['end']:o['end']+12]
            o['field_hint']='age' if ('old' in o['source'].lower() or re.search(r'\b(?:age|aged)\W*$',prefix,re.I) or re.match(r'\s+of age',suffix,re.I)) else 'other'
            continue
        prefix=note[max(0,o['start']-140):o['start']]
        # Keep nearby named fields; resolve 'AST and ALT ... 83 and 144 U/L'
        # by explicit shared-unit list order, preserving each number's position.
        matches=[]
        for field,pattern in PATTERNS.items():
            matches.extend((m.start(),m.end(),field) for m in pattern.finditer(prefix))
        matches.sort()
        if o['rule']=='shared_explicit_unit' and re.search(r'\brespectively\b',note[o['end']:o['end']+25],re.I):
            siblings=[x for x in obs if x['start']==o['start'] and x['end']==o['end'] and x['rule']==o['rule']]
            names=[]
            for _,_,field in matches:
                if not names or names[-1]!=field:names.append(field)
            if len(names)>=len(siblings):
                o['field_hint']=names[-len(siblings):][siblings.index(o)]
                continue
        if matches:
            _,end,field=matches[-1]
            tail=prefix[end:]
            if not re.search(r'[.;\n]|\d',tail) and len(tail)<=70:
                o['field_hint']=field
        # Anthropometric units can follow the value: '170 cm tall'.
        if o['field_hint'] is None and re.match(r'\s*(?:tall|in height)\b',note[o['end']:o['end']+20],re.I):o['field_hint']='height'
    # Resolve explicit lists with a unit on each number, e.g. leukocytes,
    # hemoglobin and platelets were 5900/uL, 14.7 g/dL and 191000/uL respectively.
    for marker in re.finditer(r'\brespectively\b',note,re.I):
        start=max(0,marker.start()-600)
        breaks=list(re.finditer(r'[.!?]\s+(?=[A-Z])',note[start:marker.start()]))
        if breaks:start+=breaks[-1].end()
        values=[o for o in obs if start<=o['start'] and o['end']<=marker.start() and o['unit']!='category']
        if not values:continue
        prefix=note[start:values[0]['start']]
        hits=sorted((m.start(),m.end(),field) for field,pattern in PATTERNS.items() for m in pattern.finditer(prefix))
        names=[]
        for _,_,field in hits:
            if not names or names[-1]!=field or field=='other':names.append(field)
        if len(names)==len(values) and len(values)>=2:
            for o,field in zip(values,names):o['field_hint']=field
        elif len(names)>=2:
            # Do not confidently attach the last name to the first number in
            # a list whose structure is not understood.
            for o in values:
                if o['rule'] not in ['blood_pressure_pair','explicit_sex_term']:o['field_hint']=None
    return obs

def make_source_packet(cid,note):
    return {'calculator_id':cid,'version':SPECS[cid]['version'],
        'note_sha256':hashlib.sha256(note.encode()).hexdigest(), 'observations':role_candidates(note)}

def same(a,b):
    return a==b if isinstance(a,str) or isinstance(b,str) else math.isclose(a,b,rel_tol=1e-6,abs_tol=1e-8)

def unique_semantic(field,items):
    result=[]
    for o in items:
        value=canonical_value(field,o['value'],o['unit'])
        if not any(same(value,canonical_value(field,x['value'],x['unit'])) for x in result):result.append(o)
    return result

def repair_call(call,packet,note):
    cid=call.get('calculator_id')
    if cid not in SPECS or packet['calculator_id']!=cid:raise Rejected('UNKNOWN_TOOL')
    if packet!=make_source_packet(cid,note):raise Rejected('SOURCE_OR_REGISTRY_CHANGED')
    spec=SPECS[cid]
    if call.get('formula_version')!=spec['version']:raise Rejected('FORMULA_VERSION')
    if not isinstance(call.get('arguments'),dict) or set(call['arguments'])!=set(spec['params']):raise Rejected('ARGUMENT_SET')
    repaired={'calculator_id':cid,'formula_version':spec['version'],'arguments':{}}
    audit={}
    for field,proposal in call['arguments'].items():
        if not isinstance(proposal,dict) or 'value' not in proposal or 'unit' not in proposal:raise Rejected('ARGUMENT_SCHEMA',field)
        if not isinstance(proposal['unit'],str):raise Rejected('UNIT_TYPE',field)
        if field=='sex':
            if proposal['value'] not in ['Male','Female']:raise Rejected('CATEGORY',field)
        elif isinstance(proposal['value'],bool) or not isinstance(proposal['value'],(int,float)) or not math.isfinite(proposal['value']):raise Rejected('FINITE_NUMBER',field)
        candidates=[o for o in packet['observations'] if compatible(field,o)]
        # An explicit variable label outranks unlabelled quantities. This avoids
        # treating a normal sodium concentration as a glucose measurement.
        named=[o for o in candidates if o['field_hint']==field]
        pool=named if named else candidates
        try:asserted=canonical_value(field,proposal['value'],proposal['unit'])
        except (ValueError,TypeError):asserted=None
        exact=[o for o in pool if asserted is not None and same(asserted,canonical_value(field,o['value'],o['unit']))]
        if exact:
            chosen=exact[0];action='canonical_source_match'
        else:
            raw=[o for o in pool if same(o['value'],proposal['value'])]
            raw=unique_semantic(field,raw)
            if len(raw)==1:
                chosen=raw[0];action='source_unit_repair'
            else:
                sole=unique_semantic(field,named)
                if len(sole)!=1:raise Rejected('AMBIGUOUS_OR_UNSUPPORTED_SOURCE',field)
                chosen=sole[0];action='unique_named_source_repair'
        repaired['arguments'][field]={'value':chosen['value'],'unit':chosen['unit'],'evidence_id':chosen['id']}
        audit[field]={'action':action,'proposal':copy.deepcopy(proposal),'source_id':chosen['id'],
                      'source':chosen['source'],'start':chosen['start'],'end':chosen['end'],'field_hint':chosen['field_hint']}
    values=validate(repaired,{}, {},POLICIES[2])
    value=calculate(cid,values)
    if not math.isfinite(value):raise Rejected('NONFINITE_RESULT')
    return {'released':True,'result':value,'call':repaired,'canonical_inputs':values,
            'evidence':audit,'note_sha256':packet['note_sha256']}

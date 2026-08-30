"""Comprehensive Emergency Clinical Red-Flag Patterns for Indian OPD / Emergency Triage.

Covers high-incidence emergencies in India:
1. Acute Coronary Syndrome (ACS / MI)
2. Acute Ischemic / Hemorrhagic Stroke (FAST criteria)
3. Acute Respiratory Failure / Status Asthmaticus
4. Anaphylaxis & Angioedema
5. Gastrointestinal Hemorrhage & Hypovolemic Shock
6. Acute Abdomen / Peritonitis
7. Sepsis & Meningococcal / Intracranial Infection
8. Obstetric Emergencies (Eclampsia / Antepartum Hemorrhage)
9. Snakebite, Scorpion Sting & Organophosphate Poisoning
10. Psychiatric Emergency & Suicidal Ideation
"""

from typing import Any, Dict, List

EMERGENCY_PATTERNS: List[Dict[str, Any]] = [
    # 1. ACUTE CORONARY SYNDROME (ACS / MI)
    {
        "category": "ACUTE_CORONARY_SYNDROME",
        "severity": "CRITICAL",
        "description": "Suspected Acute Myocardial Infarction / Angina Pectoris",
        "primary_triggers": [
            r"\b(chest|angina).{0,20}(pain|pressure|tightness|heavy|heaviness|squeezing)\b",
            r"(सीने|छाती|दिल).{0,25}(दर्द|भारीपन|दबाव|जकड़न)",
            r"நெஞ்சு.{0,20}வலி",
        ],
        "co_symptoms": [
            r"\b(breath|breathless|shortness of breath|dyspnea)\b",
            r"(सांस|दम|दम फूलना)",
            r"மூச்சு",
            r"\b(sweat|sweating|perspiration)\b",
            r"(पसीना|घबराहट)",
            r"\b(left arm|arm|jaw|neck|shoulder)\b",
            r"(बायें हाथ|बाएं हाथ|हाथ|कंधे|जबड़े)",
            r"\b(dizzy|dizziness|faint|fainting|syncope)\b",
            r"(चक्कर|बेहोशी)",
        ],
        "action": "Immediate ECG, move to emergency resuscitation bay, oxygen, sublingual nitrate.",
    },

    # 2. ACUTE STROKE (FAST CRITERIA)
    {
        "category": "ACUTE_STROKE",
        "severity": "CRITICAL",
        "description": "Acute Cerebrovascular Event / Transient Ischemic Attack",
        "primary_triggers": [
            r"\b(facial droop|slurred speech|slurring|speech difficulty)\b",
            r"\b(sudden weakness|paralysis|hemiparesis|one side weakness)\b",
            r"(आवाज लड़खड़ाना|लकवा|फालिज|एक तरफ कमजोरी|चेहरा टेढ़ा)",
            r"பக்கவாதம்",
        ],
        "co_symptoms": [
            r"\b(face|arm|leg|one side|vision loss|double vision)\b",
            r"(चेहरा|हाथ|पैर|दिखाई नहीं दे रहा)",
        ],
        "action": "Activate Code Stroke, record exact time of onset, expedite non-contrast CT brain.",
    },

    # 3. ACUTE RESPIRATORY FAILURE / STRIDOR
    {
        "category": "ACUTE_RESPIRATORY_FAILURE",
        "severity": "CRITICAL",
        "description": "Severe Respiratory Distress / Stridor / Status Asthmaticus",
        "primary_triggers": [
            r"\b(gasping|gasping for air|cannot breathe|suffocating|stridor)\b",
            r"\b(severe asthma attack|choking|inability to speak)\b",
            r"(सांस नहीं आ रही|दम घुट रहा है|गले में आवाज|गंभीर दमा)",
            r"மூச்சுத் திணறல்",
        ],
        "co_symptoms": [],
        "action": "High-flow oxygen, nebulization, assess airway patency, prepare intubation tray.",
    },

    # 4. ANAPHYLAXIS & ANGIOEDEMA
    {
        "category": "ANAPHYLAXIS",
        "severity": "CRITICAL",
        "description": "Severe Allergic Anaphylactic Shock / Airway Angioedema",
        "primary_triggers": [
            r"\b(anaphylaxis|swollen tongue|throat swelling|lip swelling)\b",
            r"\b(allergic reaction.{0,20}cannot breathe)\b",
            r"(जीभ सूज गई|गला बंद हो रहा है|दवा की भयंकर एलर्जी)",
        ],
        "co_symptoms": [
            r"\b(hives|itching|rash|wheezing|dizziness|vomiting)\b",
            r"(चकत्ते|खुजली|घबराहट)",
        ],
        "action": "Administer IM Adrenaline (Epinephrine) 0.5mg immediately, IV hydrocortisone.",
    },

    # 5. ACUTE GI BLEED & HYPOVOLEMIC SHOCK
    {
        "category": "ACUTE_GI_BLEED",
        "severity": "CRITICAL",
        "description": "Acute Upper/Lower Gastrointestinal Hemorrhage",
        "primary_triggers": [
            r"\b(vomiting blood|hematemesis|black stool|melena|blood in stool)\b",
            r"(खून की उल्टी|काला शौच|मल में ताजा खून)",
            r"இரத்த வாந்தி",
        ],
        "co_symptoms": [
            r"\b(dizzy|fainting|pale|cold sweats|weak pulse)\b",
            r"(बेहोशी|कमजोरी|पसीना)",
        ],
        "action": "Wide-bore IV access, fluid resuscitation, urgent blood cross-match, call gastroenterology.",
    },

    # 6. THUNDERCLAP HEADACHE / MENINGEAL SIGNS
    {
        "category": "SEVERE_HEADACHE_THUNDERCLAP",
        "severity": "HIGH",
        "description": "Suspected Subarachnoid Hemorrhage / Meningitis",
        "primary_triggers": [
            r"\b(worst headache of life|thunderclap headache|sudden severe headache)\b",
            r"(जिंदगी का सबसे भयंकर सिरदर्द|असहनीय सिरदर्द)",
        ],
        "co_symptoms": [
            r"\b(neck stiffness|stiff neck|vomiting|fever|photophobia|altered)\b",
            r"(गर्दन अकड़ना|उल्टी|तेज बुखार|बेहोशी)",
        ],
        "action": "Urgent non-contrast head CT, lumbar puncture consideration, neurosurgical consultation.",
    },

    # 7. SNAKEBITE & POISONING (HIGH OCCURRENCE IN RURAL INDIA)
    {
        "category": "SNAKEBITE_POISONING",
        "severity": "CRITICAL",
        "description": "Suspected Ophitoxaemia / Organophosphate Toxin Ingestion",
        "primary_triggers": [
            r"\b(snake bite|snakebite|poison|poisoning|insecticide|pesticide)\b",
            r"(सांप ने काटा|सर्पदंश|जहर खा लिया|कीटनाशक पी लिया)",
            r"பாம்புக்கடி",
        ],
        "co_symptoms": [],
        "action": "Administer Polyvalent Anti-Snake Venom (ASV) or Atropine/Pralidoxime as indicated.",
    },

    # 8. OBSTETRIC EMERGENCY
    {
        "category": "OBSTETRIC_EMERGENCY",
        "severity": "CRITICAL",
        "description": "Antepartum Hemorrhage / Eclampsia in Pregnancy",
        "primary_triggers": [
            r"\b(pregnant.{0,20}(bleeding|seizure|convulsion|unconscious))\b",
            r"(गर्भावस्था में खून बहना|गर्भवती महिला को दौरा|गर्भवती बेहोश)",
        ],
        "co_symptoms": [],
        "action": "Immediate transfer to labour room / OB-GYN emergency, left lateral position, fetal monitoring.",
    },

    # 9. PSYCHIATRIC CRISIS
    {
        "category": "PSYCHIATRIC_CRISIS",
        "severity": "CRITICAL",
        "description": "Acute Suicidal Ideation / High-Risk Self-Harm Intent",
        "primary_triggers": [
            r"\b(suicide|suicidal|kill myself|want to die|end my life)\b",
            r"(आत्महत्या|खुद को नुकसान|मरना चाहता हूं|जान देना चाहता)",
        ],
        "co_symptoms": [],
        "action": "Immediate safe observation, psychiatric evaluation, 1-on-1 supervision.",
    },
]

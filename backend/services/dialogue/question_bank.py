"""Structured Question Bank and State Definitions for MediKiosk Dialogue Manager.

Covers Allopathic history taking (Chief Complaint, SOCRATES HPI, Past Medical,
Drugs, Allergies, Family, Personal, ROS) and AYUSH Dashavidha Pariksha.
Supports multilingual text (English, Hindi, Tamil) and touch options.
"""

from typing import Any, Dict, List

QUESTION_BANK: Dict[str, Dict[str, Any]] = {
    # --------------------------------------------------------------------------
    # 1. INITIAL CHIEF COMPLAINT (OPEN-ENDED)
    # --------------------------------------------------------------------------
    "CHIEF_COMPLAINT": {
        "section": "CHIEF_COMPLAINT",
        "question": {
            "en": "Please tell me what problem brought you to the hospital today?",
            "hi": "नमस्ते! कृपया बताएं कि आज आपको अस्पताल किस तकलीफ के कारण आना पड़ा है?",
            "ta": "வணக்கம்! இன்று மருத்துவமனைக்கு வரக் காரணமான பிரச்சனை என்ன என்று கூறுங்கள்?",
        },
        "touch_options": [
            {"label": {"en": "Chest Pain / Discomfort", "hi": "सीने में दर्द या भारीपन", "ta": "நெஞ்சு வலி"}, "value": "chest_pain"},
            {"label": {"en": "Fever & Chills", "hi": "बुखार और ठंड लगना", "ta": "காய்ச்சல்"}, "value": "fever"},
            {"label": {"en": "Abdominal / Stomach Pain", "hi": "पेट में दर्द", "ta": "வயிற்று வலி"}, "value": "abdominal_pain"},
            {"label": {"en": "Joint or Body Pain", "hi": "जोड़ों या बदन में दर्द", "ta": "மூட்டு வலி"}, "value": "joint_pain"},
            {"label": {"en": "Cough or Breathing Issue", "hi": "खांसी या सांस लेने में परेशानी", "ta": "இருமல் / மூச்சுத் திணறல்"}, "value": "respiratory_issue"},
            {"label": {"en": "Digestive / Gas Issue", "hi": "अपच, गैस या बदहजमी", "ta": "செரிமான பிரச்சனை"}, "value": "digestive_issue"},
        ],
    },

    # --------------------------------------------------------------------------
    # 2. HPI (SOCRATES FOR PAIN / SYMPTOM ONSET)
    # --------------------------------------------------------------------------
    "HPI_DURATION": {
        "section": "HPI",
        "question": {
            "en": "How long have you had this problem?",
            "hi": "यह तकलीफ आपको कितने समय से हो रही है?",
            "ta": "இந்த பிரச்சனை உங்களுக்கு எவ்வளவு நாட்களாக உள்ளது?",
        },
        "touch_options": [
            {"label": {"en": "Less than 24 hours", "hi": "24 घंटे से कम", "ta": "24 மணி நேரத்திற்கும் குறைவாக"}, "value": "<1_day"},
            {"label": {"en": "1 to 3 days", "hi": "1 से 3 दिन", "ta": "1 முதல் 3 நாட்கள்"}, "value": "1-3_days"},
            {"label": {"en": "1 to 2 weeks", "hi": "1 से 2 सप्ताह", "ta": "1 முதல் 2 வாரங்கள்"}, "value": "1-2_weeks"},
            {"label": {"en": "More than a month", "hi": "एक महीने से अधिक समय से", "ta": "ஒரு மாதத்திற்கும் மேல்"}, "value": ">1_month"},
        ],
    },
    "HPI_SOCRATES_CHARACTER": {
        "section": "HPI_SOCRATES",
        "question": {
            "en": "How would you describe the feeling or pain?",
            "hi": "दर्द या तकलीफ का अहसास कैसा है?",
            "ta": "வலி அல்லது அசௌகரியம் எப்படிப்பட்டது?",
        },
        "touch_options": [
            {"label": {"en": "Heavy pressure / Tightness", "hi": "भारीपन या दबाव जैसा", "ta": "அழுத்தம் போன்ற வலி"}, "value": "heavy_pressure"},
            {"label": {"en": "Sharp / Stabbing", "hi": "तेज चुभने जैसा", "ta": "கூர்மையான வலி"}, "value": "sharp_stabbing"},
            {"label": {"en": "Dull ache", "hi": "हल्का धीमा दर्द", "ta": "மந்தமான வலி"}, "value": "dull_ache"},
            {"label": {"en": "Burning sensation", "hi": "जलन जैसा", "ta": "எரிச்சல் வலி"}, "value": "burning"},
            {"label": {"en": "Throbbing", "hi": "टीस मारने जैसा (धड़कता हुआ)", "ta": "துடிக்கும் வலி"}, "value": "throbbing"},
        ],
    },
    "HPI_SOCRATES_RADIATION": {
        "section": "HPI_SOCRATES",
        "question": {
            "en": "Does the pain travel or radiate anywhere else?",
            "hi": "क्या यह दर्द शरीर के किसी अन्य हिस्से में फैलता है?",
            "ta": "வலி உடலின் வேறு எங்காவது பரவுகிறதா?",
        },
        "touch_options": [
            {"label": {"en": "Spreads to Left Arm / Shoulder", "hi": "बाएं हाथ या कंधे की तरफ", "ta": "இடது கைக்கு பரவுகிறது"}, "value": "left_arm"},
            {"label": {"en": "Spreads to Neck or Jaw", "hi": "गर्दन या जबड़े की तरफ", "ta": "கழுத்து / தாடைக்கு பரவுகிறது"}, "value": "neck_jaw"},
            {"label": {"en": "Spreads to Back", "hi": "पीठ की तरफ", "ta": "முதுகுக்கு பரவுகிறது"}, "value": "back"},
            {"label": {"en": "Stays in one spot (No radiation)", "hi": "कहीं नहीं फैलता (एक ही जगह रहता है)", "ta": "எங்கும் பரவவில்லை"}, "value": "none"},
        ],
    },
    "HPI_SOCRATES_SEVERITY": {
        "section": "HPI_SOCRATES",
        "question": {
            "en": "On a scale of 1 to 10, how severe is your pain or discomfort right now?",
            "hi": "1 से 10 के पैमाने पर, आपका दर्द या तकलीफ अभी कितनी तीव्र है?",
            "ta": "1 முதல் 10 வரை உள்ள அளவில் உங்கள் வலி இப்போது எவ்வளவு தீவிரமானது?",
        },
        "touch_options": [
            {"label": {"en": "Mild (1 - 3)", "hi": "हल्का (1 - 3)", "ta": "லேசானது (1 - 3)"}, "value": "mild_3"},
            {"label": {"en": "Moderate (4 - 6)", "hi": "मध्यम (4 - 6)", "ta": "நடுத்தரமானது (4 - 6)"}, "value": "moderate_6"},
            {"label": {"en": "Severe (7 - 8)", "hi": "तेज दर्द (7 - 8)", "ta": "கடுமையானது (7 - 8)"}, "value": "severe_8"},
            {"label": {"en": "Very Severe / Unbearable (9 - 10)", "hi": "असहनीय (9 - 10)", "ta": "பொறுக்க முடியாதது (9 - 10)"}, "value": "unbearable_10"},
        ],
    },

    # --------------------------------------------------------------------------
    # 3. PAST MEDICAL HISTORY
    # --------------------------------------------------------------------------
    "PAST_MEDICAL_HISTORY": {
        "section": "PAST_MEDICAL_HISTORY",
        "question": {
            "en": "Do you have any existing chronic health conditions, or past surgeries?",
            "hi": "क्या आपको पहले से कोई पुरानी बीमारी (जैसे बीपी, शुगर) है, या कोई ऑपरेशन हुआ है?",
            "ta": "உங்களுக்கு ஏற்கனவே ஏதேனும் நாள்பட்ட நோய்கள் அல்லது அறுவை சிகிச்சைகள் உள்ளதா?",
        },
        "touch_options": [
            {"label": {"en": "High Blood Pressure (BP)", "hi": "हाई ब्लड प्रेशर (बीपी)", "ta": "உயர் இரத்த அழுத்தம்"}, "value": "hypertension"},
            {"label": {"en": "Diabetes (Sugar)", "hi": "डायबिटीज (शुगर)", "ta": "சர்க்கரை நோய்"}, "value": "diabetes"},
            {"label": {"en": "Heart Condition", "hi": "हृदय रोग", "ta": "இதய நோய்"}, "value": "heart_disease"},
            {"label": {"en": "Asthma / Respiratory", "hi": "अस्थमा या दमा", "ta": "ஆஸ்துமா"}, "value": "asthma"},
            {"label": {"en": "Past Surgery / Operation", "hi": "पूर्व में कोई सर्जरी / ऑपरेशन", "ta": "முந்தைய அறுவை சிகிச்சை"}, "value": "past_surgery"},
            {"label": {"en": "None / No known conditions", "hi": "कोई पुरानी बीमारी नहीं", "ta": "எதுவும் இல்லை"}, "value": "none"},
        ],
    },

    # --------------------------------------------------------------------------
    # 4. DRUG HISTORY
    # --------------------------------------------------------------------------
    "DRUG_HISTORY": {
        "section": "DRUG_HISTORY",
        "question": {
            "en": "Are you currently taking any regular medicines, including Ayurvedic or home remedies?",
            "hi": "क्या आप वर्तमान में कोई नियमित दवाइयां, आयुर्वेदिक चूर्ण, या घरेलू उपचार ले रहे हैं?",
            "ta": "நீங்கள் தற்போது ஏதேனும் மருந்துகள் அல்லது ஆயுர்வேத மருந்துகளை உட்கொள்கிறீர்களா?",
        },
        "touch_options": [
            {"label": {"en": "Daily BP / Heart Medicines", "hi": "बीपी या दिल की दवाएं", "ta": "இரத்த அழுத்த மருந்துகள்"}, "value": "bp_meds"},
            {"label": {"en": "Diabetes / Insulin", "hi": "शुगर की दवाएं या इंसुलिन", "ta": "சர்க்கரை மருந்துகள்"}, "value": "diabetes_meds"},
            {"label": {"en": "Ayurvedic Remedies / Churna", "hi": "आयुर्वेदिक दवाएं या चूर्ण", "ta": "ஆயுர்வேத மருந்துகள்"}, "value": "ayush_meds"},
            {"label": {"en": "Painkillers / Gas tablets", "hi": "दर्द निवारक या गैस की गोली", "ta": "வலி நிவாரணிகள்"}, "value": "otc_meds"},
            {"label": {"en": "No current medications", "hi": "कोई दवा नहीं ले रहे", "ta": "எந்த மருந்தும் இல்லை"}, "value": "none"},
        ],
    },

    # --------------------------------------------------------------------------
    # 5. ALLERGY HISTORY
    # --------------------------------------------------------------------------
    "ALLERGY_HISTORY": {
        "section": "ALLERGY_HISTORY",
        "question": {
            "en": "Do you have any known allergies to medicines (e.g. Penicillin) or foods?",
            "hi": "क्या आपको किसी दवा (जैसे पेनिसिलिन) या खाने-पीने की चीज से कोई एलर्जी है?",
            "ta": "உங்களுக்கு ஏதேனும் மருந்து அல்லது உணவு ஒவ்வாமை (அலர்ஜி) உள்ளதா?",
        },
        "touch_options": [
            {"label": {"en": "Antibiotic / Drug Allergy", "hi": "दवाओं या एंटीबायोटिक से एलर्जी", "ta": "மருந்து அலர்ஜி"}, "value": "drug_allergy"},
            {"label": {"en": "Food / Dust Allergy", "hi": "खाद्य पदार्थ या धूल से एलर्जी", "ta": "உணவு / தூசி அலர்ஜி"}, "value": "food_allergy"},
            {"label": {"en": "Skin Rash / Itching from pills", "hi": "दवा खाने से खुजली या चकत्ते", "ta": "தோல் அரிப்பு"}, "value": "skin_allergy"},
            {"label": {"en": "No Known Allergies", "hi": "कोई ज्ञात एलर्जी नहीं है", "ta": "எந்த அலர்ஜியும் இல்லை"}, "value": "none"},
        ],
    },

    # --------------------------------------------------------------------------
    # 6. FAMILY HISTORY
    # --------------------------------------------------------------------------
    "FAMILY_HISTORY": {
        "section": "FAMILY_HISTORY",
        "question": {
            "en": "Does anyone in your immediate family have a history of heart attack, diabetes, or cancer?",
            "hi": "क्या आपके परिवार (माता-पिता, भाई-बहन) में दिल का दौरा, शुगर, या कैंसर का इतिहास है?",
            "ta": "உங்கள் குடும்பத்தில் யாருக்காவது இதய நோய், சர்க்கரை நோய் அல்லது புற்றுநோய் உள்ளதா?",
        },
        "touch_options": [
            {"label": {"en": "Family Heart Disease / Stroke", "hi": "परिवार में दिल की बीमारी या स्ट्रोक", "ta": "குடும்பத்தில் இதய நோய்"}, "value": "family_heart"},
            {"label": {"en": "Family Diabetes", "hi": "परिवार में शुगर (डायबिटीज)", "ta": "குடும்பத்தில் சர்க்கரை நோய்"}, "value": "family_diabetes"},
            {"label": {"en": "Family Hypertension", "hi": "परिवार में हाई बीपी", "ta": "குடும்பத்தில் இரத்த அழுத்தம்"}, "value": "family_hypertension"},
            {"label": {"en": "No significant family illness", "hi": "परिवार में ऐसी कोई गंभीर बीमारी नहीं", "ta": "குடும்பத்தில் எதுவும் இல்லை"}, "value": "none"},
        ],
    },

    # --------------------------------------------------------------------------
    # 7. PERSONAL HISTORY (LIFESTYLE & HABITS)
    # --------------------------------------------------------------------------
    "PERSONAL_HISTORY": {
        "section": "PERSONAL_HISTORY",
        "question": {
            "en": "Tell me about your lifestyle: What is your diet and do you consume tobacco or alcohol?",
            "hi": "आपकी जीवनशैली के बारे में बताएं: आपका खान-पान कैसा है और क्या आप तंबाकू या शराब लेते हैं?",
            "ta": "உங்கள் வாழ்க்கை முறை: உணவு பழக்கம், புகையிலை அல்லது மது அருந்தும் பழக்கம் உள்ளதா?",
        },
        "touch_options": [
            {"label": {"en": "Vegetarian Diet (शाकाहारी)", "hi": "शुद्ध शाकाहारी", "ta": "சைவம்"}, "value": "diet_veg"},
            {"label": {"en": "Non-Vegetarian Diet (मांसाहारी)", "hi": "मांसाहारी या अंडा", "ta": "அசைவம்"}, "value": "diet_nonveg"},
            {"label": {"en": "Tobacco User (Bidi/Gutkha)", "hi": "तंबाकू, बीड़ी या गुटखा लेते हैं", "ta": "புகையிலை பழக்கம்"}, "value": "tobacco_active"},
            {"label": {"en": "Alcohol Consumer", "hi": "शराब का सेवन करते हैं", "ta": "மது அருந்துபவர்"}, "value": "alcohol_active"},
            {"label": {"en": "No substance use / Clean", "hi": "कोई नशा नहीं करते", "ta": "பழக்கம் எதுவும் இல்லை"}, "value": "substance_none"},
        ],
    },

    # --------------------------------------------------------------------------
    # 8. REVIEW OF SYSTEMS (ROS)
    # --------------------------------------------------------------------------
    "REVIEW_OF_SYSTEMS": {
        "section": "REVIEW_OF_SYSTEMS",
        "question": {
            "en": "Any other symptoms: breathlessness, swelling in feet, dizziness, or stomach bloating?",
            "hi": "क्या कोई अन्य लक्षण हैं: जैसे सांस फूलना, पैरों में सूजन, चक्कर आना या पेट फूलना?",
            "ta": "வேறு ஏதேனும் அறிகுறிகள்: மூச்சுத் திணறல், கால் வீக்கம், தலைசுற்றல் அல்லது வாய்வு உள்ளதா?",
        },
        "touch_options": [
            {"label": {"en": "Breathlessness on exertion", "hi": "चलने पर सांस फूलना", "ta": "மூச்சுத் திணறல்"}, "value": "dyspnea"},
            {"label": {"en": "Swelling in feet / legs", "hi": "पैरों या टखनों में सूजन", "ta": "கால் வீக்கம்"}, "value": "pedal_edema"},
            {"label": {"en": "Dizziness / Giddiness", "hi": "चक्कर आना या कमजोरी", "ta": "தலைசுற்றல்"}, "value": "dizziness"},
            {"label": {"en": "Nausea / Vomiting feeling", "hi": "जी मिचलाना या उल्टी का अहसास", "ta": "குமட்டல்"}, "value": "nausea"},
            {"label": {"en": "No other symptoms", "hi": "कोई अन्य लक्षण नहीं हैं", "ta": "வேறு எந்த அறிகுறியும் இல்லை"}, "value": "none"},
        ],
    },

    # --------------------------------------------------------------------------
    # 9. AYUSH MODE: DASHAVIDHA PARIKSHA (PRAKRITI & AGNI)
    # --------------------------------------------------------------------------
    "AYUSH_PRAKRITI": {
        "section": "AYUSH_DASHAVIDHA",
        "question": {
            "en": "[AYUSH] Body constitution (Prakriti): Do you feel more sensitive to cold, heat, or heavy weather?",
            "hi": "[आयुर्वेद प्रकृति] आपको ठंड अधिक लगती है, गर्मी अधिक लगती है, या भारीपन रहता है?",
            "ta": "[ஆயுஷ்] உங்கள் உடல் தன்மை: உங்களுக்கு குளிர் அதிகம் பிடிக்காதா அல்லது வெப்பமா?",
        },
        "touch_options": [
            {"label": {"en": "Vata: Cold sensitivity, Dry skin, Light sleep", "hi": "वात: ठंड अधिक लगना, रूखी त्वचा, हल्की नींद", "ta": "வாதம்: குளிர் அதிகம், வறண்ட தோல்"}, "value": "vata"},
            {"label": {"en": "Pitta: Heat intolerance, High appetite, Thirst", "hi": "पित्त: गर्मी बर्दाश्त न होना, तेज भूख व प्यास", "ta": "பித்தம்: வெப்பம் அதிகம், அதிக பசி"}, "value": "pitta"},
            {"label": {"en": "Kapha: Heavy build, Calm, Prefers warmth", "hi": "कफ: भारी शरीर, शांत स्वभाव, सुस्ती", "ta": "கபம்: கனமான உடல், அமைதி"}, "value": "kapha"},
            {"label": {"en": "Mixed / Dual Prakriti (Vata-Pitta)", "hi": "मिश्रित प्रकृति (वात-पित्त)", "ta": "கலப்பு தன்மை"}, "value": "vata_pitta"},
        ],
    },
    "AYUSH_AGNI_KOSHTHA": {
        "section": "AYUSH_DASHAVIDHA",
        "question": {
            "en": "[AYUSH] Digestive Power (Agni) and Bowel (Koshtha): How is your digestion and bowel movement?",
            "hi": "[आयुर्वेद अग्नि व कोष्ठ] आपकी पाचन शक्ति और पेट साफ होने की स्थिति कैसी है?",
            "ta": "[ஆயுஷ்] உங்கள் செரிமான சக்தி மற்றும் மலச்சிக்கல் நிலை எப்படி உள்ளது?",
        },
        "touch_options": [
            {"label": {"en": "Samagni: Good appetite, Timely smooth digestion", "hi": "समाग्नि: समय पर भूख, सामान्य पाचन", "ta": "சமமான செரிமானம்"}, "value": "samagni"},
            {"label": {"en": "Vishamagni: Irregular appetite, Bloating/Gas", "hi": "विषमाग्नि: कभी भूख कभी नहीं, गैस/अफारा", "ta": "ஒழுங்கற்ற செரிமானம்"}, "value": "vishamagni"},
            {"label": {"en": "Mandagni: Poor appetite, Sluggish digestion", "hi": "मंदाग्नि: भूख न लगना, भारीपन", "ta": "மந்தமான செரிமானம்"}, "value": "mandagni"},
            {"label": {"en": "Krura Koshtha: Hard stool / Constipation tendency", "hi": "क्रूर कोष्ठ: कब्ज या कड़ा मल", "ta": "மலச்சிக்கல் தன்மை"}, "value": "krura_koshtha"},
        ],
    },
}

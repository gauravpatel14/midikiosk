"""Jinja2 HTML and Plain Text Clinical Summary Templates for MediKiosk.

Designed for hospital OPD physicians, AIIMS / AIIA clinical EMR workflows,
and ABDM PHR health document uploads.
"""

HTML_SUMMARY_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MediKiosk Clinical Summary - {{ patient.name }}</title>
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    background: #f8fafc;
    margin: 0;
    padding: 24px;
    line-height: 1.5;
  }
  .summary-container {
    max-width: 900px;
    margin: 0 auto;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 32px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
  }
  .header {
    border-bottom: 2px solid #0f766e;
    padding-bottom: 16px;
    margin-bottom: 20px;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }
  .hospital-title {
    font-size: 20px;
    font-weight: 800;
    color: #0f766e;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0;
  }
  .sub-title {
    font-size: 13px;
    color: #64748b;
    margin-top: 4px;
  }
  .meta-tag {
    font-size: 12px;
    background: #f1f5f9;
    padding: 4px 10px;
    border-radius: 4px;
    color: #475569;
    font-weight: 600;
  }
  .demographics-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    background: #f8fafc;
    padding: 14px;
    border-radius: 6px;
    margin-bottom: 24px;
    font-size: 13px;
    border: 1px solid #edf2f7;
  }
  .demo-item strong {
    color: #475569;
    display: block;
    font-size: 11px;
    text-transform: uppercase;
  }
  .section {
    margin-bottom: 20px;
  }
  .section-title {
    font-size: 14px;
    font-weight: 700;
    color: #0f766e;
    text-transform: uppercase;
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 4px;
    margin-bottom: 10px;
    display: flex;
    justify-content: space-between;
  }
  .badge-redflag {
    background: #fee2e2;
    color: #b91c1c;
    border: 1px solid #f87171;
    padding: 8px 14px;
    border-radius: 6px;
    font-weight: 700;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .editable-area {
    background: #ffffff;
    border: 1px dashed #94a3b8;
    border-radius: 6px;
    padding: 10px 14px;
    min-height: 48px;
    outline: none;
    font-size: 13px;
    transition: border-color 0.2s;
  }
  .editable-area:focus {
    border-color: #0f766e;
    background: #f0fdfa;
  }
  table.clinical-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    margin-top: 6px;
  }
  table.clinical-table th, table.clinical-table td {
    padding: 8px 12px;
    border: 1px solid #e2e8f0;
    text-align: left;
  }
  table.clinical-table th {
    background: #f1f5f9;
    font-weight: 600;
    color: #334155;
  }
  .val-high {
    background: #fef2f2;
    color: #dc2626;
    font-weight: 700;
  }
  .val-low {
    background: #fffbeb;
    color: #d97706;
    font-weight: 700;
  }
  .val-normal {
    color: #16a34a;
  }
  .doctor-sign-block {
    margin-top: 36px;
    padding-top: 16px;
    border-top: 1px solid #cbd5e1;
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    color: #64748b;
  }
  @media print {
    body { background: #ffffff; padding: 0; }
    .summary-container { border: none; box-shadow: none; padding: 12px; }
    .editable-area { border: none; }
  }
</style>
</head>
<body>

<div class="summary-container">
  <!-- Header -->
  <div class="header">
    <div>
      <h1 class="hospital-title">{{ hospital_name or "All India Institute of Ayurveda - Clinical OPD" }}</h1>
      <div class="sub-title">Pre-Consultation Patient Clinical History Summary | Generated via MediKiosk</div>
    </div>
    <div class="meta-tag">
      Date: {{ generated_date }}
    </div>
  </div>

  <!-- Red Flag Emergency Alert Banner (if present) -->
  {% if red_flag %}
  <div class="badge-redflag">
    <span>⚠️ <strong>CRITICAL CLINICAL ALERT:</strong> {{ red_flag.category }} - {{ red_flag.message or red_flag.rule }}</span>
  </div>
  {% endif %}

  <!-- 1. Patient Demographics -->
  <div class="demographics-grid">
    <div class="demo-item">
      <strong>Patient Name</strong>
      <span>{{ patient.name or "N/A" }}</span>
    </div>
    <div class="demo-item">
      <strong>Age / Gender</strong>
      <span>{{ patient.age or "--" }} Y / {{ patient.gender or "--" }}</span>
    </div>
    <div class="demo-item">
      <strong>ABHA ID / Temp ID</strong>
      <span>{{ patient.abha_id or patient.temp_id or "Unlinked Walk-in" }}</span>
    </div>
    <div class="demo-item">
      <strong>Phone / Language</strong>
      <span>{{ patient.phone or "--" }} ({{ patient.language or "Hindi" }})</span>
    </div>
  </div>

  <!-- 2. Chief Complaint -->
  <div class="section">
    <div class="section-title">Chief Complaint</div>
    <p><strong>Primary Complaint:</strong> {{ chief_complaint.text or "Not stated" }}</p>
  </div>

  <!-- 3. History of Present Illness (SOCRATES) -->
  <div class="section">
    <div class="section-title">History of Present Illness (HPI)</div>
    <table class="clinical-table">
      <tr>
        <th width="30%">Duration / Onset</th>
        <td>{{ hpi.duration or "Unspecified duration" }}</td>
      </tr>
      {% if hpi.character %}
      <tr>
        <th>Character / Feeling</th>
        <td>{{ hpi.character }}</td>
      </tr>
      {% endif %}
      {% if hpi.radiation %}
      <tr>
        <th>Radiation / Spread</th>
        <td>{{ hpi.radiation }}</td>
      </tr>
      {% endif %}
      {% if hpi.severity %}
      <tr>
        <th>Severity Score</th>
        <td>{{ hpi.severity }} / 10</td>
      </tr>
      {% endif %}
    </table>
  </div>

  <!-- 4. Past Medical History -->
  <div class="section">
    <div class="section-title">Past Medical & Surgical History</div>
    {% if past_medical and past_medical|length > 0 %}
      <ul>
      {% for item in past_medical %}
        <li>{{ item }}</li>
      {% endfor %}
      </ul>
    {% else %}
      <p style="color:#64748b; font-size:13px;">No prior chronic diseases or major surgeries reported.</p>
    {% endif %}
  </div>

  <!-- 5. Drug History -->
  <div class="section">
    <div class="section-title">Drug History (Current Medications)</div>
    {% if medications and medications|length > 0 %}
      <table class="clinical-table">
        <thead>
          <tr>
            <th>Medication Name</th>
            <th>Dosage</th>
            <th>Frequency</th>
            <th>Duration</th>
          </tr>
        </thead>
        <tbody>
        {% for med in medications %}
          <tr>
            <td><strong>{{ med.name }}</strong></td>
            <td>{{ med.dosage or "--" }}</td>
            <td>{{ med.frequency or "--" }}</td>
            <td>{{ med.duration or "--" }}</td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    {% else %}
      <p style="color:#64748b; font-size:13px;">No regular medications currently taken.</p>
    {% endif %}
  </div>

  <!-- 6. Allergy History -->
  <div class="section">
    <div class="section-title">Allergy History</div>
    {% if allergies and allergies|length > 0 %}
      <ul>
      {% for alg in allergies %}
        <li style="color:#b91c1c; font-weight:600;">⚠️ {{ alg }}</li>
      {% endfor %}
      </ul>
    {% else %}
      <p style="color:#16a34a; font-size:13px;">No known drug, food, or environmental allergies (NKDA).</p>
    {% endif %}
  </div>

  <!-- 7. Family History -->
  <div class="section">
    <div class="section-title">Family History</div>
    {% if family_history and family_history|length > 0 %}
      <ul>
      {% for item in family_history %}
        <li>{{ item }}</li>
      {% endfor %}
      </ul>
    {% else %}
      <p style="color:#64748b; font-size:13px;">No significant familial cardiac, metabolic, or genetic history.</p>
    {% endif %}
  </div>

  <!-- 8. Personal History (Lifestyle) -->
  <div class="section">
    <div class="section-title">Personal History (Diet & Lifestyle)</div>
    {% if personal_history and personal_history|length > 0 %}
      <ul>
      {% for item in personal_history %}
        <li>{{ item }}</li>
      {% endfor %}
      </ul>
    {% else %}
      <p style="color:#64748b; font-size:13px;">Standard diet, non-smoker, non-alcoholic.</p>
    {% endif %}
  </div>

  <!-- 9. Review of Systems (ROS) -->
  <div class="section">
    <div class="section-title">Review of Systems (ROS)</div>
    {% if review_of_systems and review_of_systems|length > 0 %}
      <ul>
      {% for sym in review_of_systems %}
        <li>{{ sym }}</li>
      {% endfor %}
      </ul>
    {% else %}
      <p style="color:#64748b; font-size:13px;">Negative for systemic constitutional, respiratory, or GI complaints.</p>
    {% endif %}
  </div>

  <!-- 10. Prior Investigations Summary (Document Extraction Table with Abnormal Highlight) -->
  <div class="section">
    <div class="section-title">Prior Investigations & Lab Results</div>
    {% if laboratory_results and laboratory_results|length > 0 %}
      <table class="clinical-table">
        <thead>
          <tr>
            <th>Investigation / Test Name</th>
            <th>Observed Value</th>
            <th>Unit</th>
            <th>Reference Range</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
        {% for lab in laboratory_results %}
          <tr>
            <td><strong>{{ lab.test_name }}</strong></td>
            <td class="{% if lab.interpretation == 'High' %}val-high{% elif lab.interpretation == 'Low' %}val-low{% else %}val-normal{% endif %}">
              {{ lab.value }}
            </td>
            <td>{{ lab.unit or "--" }}</td>
            <td>{{ lab.reference_range or "--" }}</td>
            <td>
              {% if lab.interpretation == 'High' %}
                <span style="color:#dc2626; font-weight:700;">▲ High</span>
              {% elif lab.interpretation == 'Low' %}
                <span style="color:#d97706; font-weight:700;">▼ Low</span>
              {% else %}
                <span style="color:#16a34a;">Normal</span>
              {% endif %}
            </td>
          </tr>
        {% endfor %}
        </tbody>
      </table>
    {% else %}
      <p style="color:#64748b; font-size:13px;">No prior laboratory investigations extracted from scanned records.</p>
    {% endif %}
  </div>

  <!-- Potential Drug Interactions Section -->
  {% if drug_interactions and drug_interactions|length > 0 %}
  <div class="section" style="border-left: 4px solid #ef4444;">
    <div class="section-title" style="color: #b91c1c;">⚠️ Potential Drug Interactions Detected</div>
    <table class="clinical-table">
      <thead>
        <tr>
          <th>Interacting Pair</th>
          <th>Severity</th>
          <th>Clinical Mechanism / Warning</th>
          <th>Source</th>
        </tr>
      </thead>
      <tbody>
      {% for di in drug_interactions %}
        <tr>
          <td><strong>{{ di.drug_a }} + {{ di.drug_b }}</strong></td>
          <td>
            {% if di.severity == 'Major' %}
              <span style="background:#fee2e2; color:#b91c1c; padding:3px 8px; border-radius:4px; font-weight:700;">MAJOR</span>
            {% elif di.severity == 'Moderate' %}
              <span style="background:#fef3c7; color:#b45309; padding:3px 8px; border-radius:4px; font-weight:700;">MODERATE</span>
            {% else %}
              <span style="background:#f1f5f9; color:#475569; padding:3px 8px; border-radius:4px;">MINOR</span>
            {% endif %}
          </td>
          <td>{{ di.description }}</td>
          <td style="font-size:11px; color:#64748b;">{{ di.source }}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  <!-- AYUSH Safety Alerts Section -->
  {% if ayush_alerts and ayush_alerts|length > 0 %}
  <div class="section" style="border-left: 4px solid #d97706;">
    <div class="section-title" style="color: #b45309;">🌿 AYUSH Formulation & Heavy Metal Safety Alerts</div>
    {% for alert in ayush_alerts %}
      <div style="background:#fffbeb; border:1px solid #fde68a; border-radius:6px; padding:12px; margin-bottom:10px;">
        <div style="font-size:14px; font-weight:700; color:#92400e; margin-bottom:4px;">
          {{ alert.formulation }} ({{ alert.regulatory_status }})
        </div>
        <p style="margin:4px 0; font-size:13px; color:#78350f;"><strong>Toxicity Notice:</strong> {{ alert.toxicity_alert }}</p>
        <p style="margin:4px 0; font-size:12px; color:#78350f;"><strong>Key Herbo-Mineral Elements:</strong> {{ alert.elements|join(', ') }}</p>
        {% if alert.triggered_contraindications %}
        <div style="background:#fee2e2; border:1px solid #fca5a5; padding:6px 10px; border-radius:4px; margin-top:6px;">
          <strong style="color:#b91c1c; font-size:12px;">CRITICAL PATIENT CONTRAINDICATION:</strong>
          <span style="color:#7f1d1d; font-size:12px;">{{ alert.triggered_contraindications|join(', ') }}</span>
        </div>
        {% endif %}
      </div>
    {% endfor %}
  </div>
  {% endif %}

  <!-- Medical Document Timeline Section -->
  {% if document_timeline and document_timeline|length > 0 %}
  <div class="section">
    <div class="section-title">Medical Document Timeline (Chronological)</div>
    <table class="clinical-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Document Date</th>
          <th>Document Type</th>
          <th>Filename</th>
          <th>OCR Confidence</th>
        </tr>
      </thead>
      <tbody>
      {% for doc in document_timeline %}
        <tr>
          <td>{{ loop.index }}</td>
          <td><strong>{{ doc.date }}</strong></td>
          <td>{{ doc.type }}</td>
          <td>{{ doc.filename }}</td>
          <td>{{ (doc.confidence * 100)|round(1) }}%</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
  {% endif %}

  <!-- 11. AYUSH Dashavidha Pariksha Table (if mode == AYUSH) -->
  {% if is_ayush %}
  <div class="section">
    <div class="section-title">AYUSH Dashavidha Pariksha (दशविध परीक्षा)</div>
    <table class="clinical-table">
      <thead>
        <tr>
          <th width="40%">Pariksha Parameter</th>
          <th>Clinical Finding / Assessment</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>1. Prakriti (प्रकृति - Body Constitution)</strong></td>
          <td>{{ ayush.prakriti or "Vata-Pitta Prakriti" }}</td>
        </tr>
        <tr>
          <td><strong>2. Vikriti (विकृति - Pathological State)</strong></td>
          <td>{{ ayush.vikriti or "Vata Vriddhi / Dosha Dushti" }}</td>
        </tr>
        <tr>
          <td><strong>3. Sara (सार - Tissue Quality)</strong></td>
          <td>{{ ayush.sara or "Madhyama Sara (Moderate)" }}</td>
        </tr>
        <tr>
          <td><strong>4. Samhanana (संहनन - Compactness)</strong></td>
          <td>{{ ayush.samhanana or "Madhyama Samhanana" }}</td>
        </tr>
        <tr>
          <td><strong>5. Pramana (प्रमाण - Anthropometry)</strong></td>
          <td>{{ ayush.pramana or "Yatha-pramana (Proportionate)" }}</td>
        </tr>
        <tr>
          <td><strong>6. Satmya (सात्म्य - Adaptability)</strong></td>
          <td>{{ ayush.satmya or "Oka-satmya (Habituated)" }}</td>
        </tr>
        <tr>
          <td><strong>7. Sattva (सत्त्व - Mental Strength)</strong></td>
          <td>{{ ayush.sattva or "Madhyama Sattva" }}</td>
        </tr>
        <tr>
          <td><strong>8. Ahara Shakti & Agni (आहार शक्ति व अग्नि)</strong></td>
          <td>{{ ayush.agni or "Samagni (Balanced digestion)" }}</td>
        </tr>
        <tr>
          <td><strong>9. Vyayama Shakti (व्यायाम शक्ति - Physical Capacity)</strong></td>
          <td>{{ ayush.vyayama or "Madhyama (Moderate tolerance)" }}</td>
        </tr>
        <tr>
          <td><strong>10. Vaya (वय - Chronological Age Factor)</strong></td>
          <td>{{ ayush.vaya or "Madhyama Vaya (Adult)" }}</td>
        </tr>
      </tbody>
    </table>
  </div>
  {% endif %}

  <!-- 12. Physician Editable Assessment & Plan -->
  <!-- PHYSICIAN_EDITABLE_SECTION_START -->
  <div class="section">
    <div class="section-title">
      <span>Physician Assessment & Treatment Plan (Editable)</span>
      <span style="font-size:11px; font-weight:normal; text-transform:none; color:#64748b;">Click inside to edit notes</span>
    </div>
    <!-- PHYSICIAN_EDITABLE: Clinical Impression, Rx & Orders -->
    <div class="editable-area" contenteditable="true">
      {{ physician_notes or "Physician Clinical Notes: Patient examined. Plan for ECG and routine hemogram. Advised follow-up in OPD after 7 days." }}
    </div>
  </div>
  <!-- PHYSICIAN_EDITABLE_SECTION_END -->

  <!-- Doctor Signature & Verification Block -->
  <div class="doctor-sign-block">
    <div>
      <span>MediKiosk Auto-History Intake (v1.0)</span><br>
      <span>DPDP Act 2023 Consent Timestamp: {{ consent_time or generated_date }}</span>
    </div>
    <div style="text-align: right;">
      <span>Consulting Physician: ___________________________</span><br>
      <span>Registration No: _______________________________</span>
    </div>
  </div>
</div>

</body>
</html>
"""


PLAIN_TEXT_SUMMARY_TEMPLATE = """================================================================================
          MEDIKIOSK CLINICAL HISTORY SUMMARY - PHYSICIAN EMR NOTE
================================================================================
Generated Date: {{ generated_date }}
Facility: {{ hospital_name or "All India Institute of Ayurveda - Clinical OPD" }}

--------------------------------------------------------------------------------
1. PATIENT DEMOGRAPHICS
--------------------------------------------------------------------------------
Name: {{ patient.name or "N/A" }}
Age / Gender: {{ patient.age or "--" }} Y / {{ patient.gender or "--" }}
ABHA ID / Temp ID: {{ patient.abha_id or patient.temp_id or "Unlinked Walk-in" }}
Phone: {{ patient.phone or "--" }}
Language: {{ patient.language or "Hindi" }}

{% if red_flag %}
********************************************************************************
*** CRITICAL CLINICAL ALERT (RED FLAG DETECTED) ***
Category: {{ red_flag.category }}
Message: {{ red_flag.message or red_flag.rule }}
********************************************************************************
{% endif %}

--------------------------------------------------------------------------------
2. CHIEF COMPLAINT
--------------------------------------------------------------------------------
{{ chief_complaint.text or "Not stated" }}

--------------------------------------------------------------------------------
3. HISTORY OF PRESENT ILLNESS (HPI)
--------------------------------------------------------------------------------
- Duration: {{ hpi.duration or "Unspecified" }}
{% if hpi.character %}- Character: {{ hpi.character }}{% endif %}
{% if hpi.radiation %}- Radiation: {{ hpi.radiation }}{% endif %}
{% if hpi.severity %}- Severity Score: {{ hpi.severity }} / 10{% endif %}

--------------------------------------------------------------------------------
4. PAST MEDICAL & SURGICAL HISTORY
--------------------------------------------------------------------------------
{% if past_medical and past_medical|length > 0 %}
{% for item in past_medical %}
- {{ item }}
{% endfor %}
{% else %}
- None reported.
{% endif %}

--------------------------------------------------------------------------------
5. DRUG HISTORY (CURRENT MEDICATIONS)
--------------------------------------------------------------------------------
{% if medications and medications|length > 0 %}
{% for med in medications %}
- {{ med.name }} | Dose: {{ med.dosage or "--" }} | Freq: {{ med.frequency or "--" }} | Duration: {{ med.duration or "--" }}
{% endfor %}
{% else %}
- No current regular medications.
{% endif %}

--------------------------------------------------------------------------------
6. ALLERGY HISTORY
--------------------------------------------------------------------------------
{% if allergies and allergies|length > 0 %}
{% for alg in allergies %}
- [ALLERGY WARNING] {{ alg }}
{% endfor %}
{% else %}
- No known drug allergies (NKDA).
{% endif %}

--------------------------------------------------------------------------------
7. FAMILY HISTORY
--------------------------------------------------------------------------------
{% if family_history and family_history|length > 0 %}
{% for item in family_history %}
- {{ item }}
{% endfor %}
{% else %}
- Non-contributory.
{% endif %}

--------------------------------------------------------------------------------
8. PERSONAL HISTORY (DIET & LIFESTYLE)
--------------------------------------------------------------------------------
{% if personal_history and personal_history|length > 0 %}
{% for item in personal_history %}
- {{ item }}
{% endfor %}
{% else %}
- Standard diet, non-smoker, non-alcoholic.
{% endif %}

--------------------------------------------------------------------------------
9. REVIEW OF SYSTEMS (ROS)
--------------------------------------------------------------------------------
{% if review_of_systems and review_of_systems|length > 0 %}
{% for sym in review_of_systems %}
- {{ sym }}
{% endfor %}
{% else %}
- Negative for systemic complaints.
{% endif %}

--------------------------------------------------------------------------------
10. PRIOR INVESTIGATIONS (DOCUMENT OCR EXTRACTED LABS)
--------------------------------------------------------------------------------
{% if laboratory_results and laboratory_results|length > 0 %}
{% for lab in laboratory_results %}
- {{ lab.test_name }}: {{ lab.value }} {{ lab.unit or "" }} [Ref: {{ lab.reference_range or "--" }}] -> {{ lab.interpretation or "Normal" }}{% if lab.interpretation in ['High', 'Low'] %} (ABNORMAL){% endif %}
{% endfor %}
{% else %}
- No prior lab results recorded.
{% endif %}

{% if drug_interactions and drug_interactions|length > 0 %}
--------------------------------------------------------------------------------
POTENTIAL DRUG INTERACTIONS
--------------------------------------------------------------------------------
{% for di in drug_interactions %}
* [{{ di.severity|upper }}] {{ di.drug_a }} + {{ di.drug_b }}
  Description: {{ di.description }}
  Source: {{ di.source }}
{% endfor %}
{% endif %}

{% if ayush_alerts and ayush_alerts|length > 0 %}
--------------------------------------------------------------------------------
AYUSH SAFETY ALERTS
--------------------------------------------------------------------------------
{% for alert in ayush_alerts %}
* [{{ alert.severity|upper }}] {{ alert.formulation }}
  Toxicity Warning: {{ alert.toxicity_alert }}
  Elements: {{ alert.elements|join(', ') }}
  {% if alert.triggered_contraindications %}
  CONTRAINDICATIONS TRIGGERED: {{ alert.triggered_contraindications|join(', ') }}
  {% endif %}
{% endfor %}
{% endif %}

{% if document_timeline and document_timeline|length > 0 %}
--------------------------------------------------------------------------------
MEDICAL DOCUMENT TIMELINE
--------------------------------------------------------------------------------
{% for doc in document_timeline %}
{{ loop.index }}. [{{ doc.date }}] {{ doc.type }} - {{ doc.filename }} (Confidence: {{ (doc.confidence * 100)|round(1) }}%)
{% endfor %}
{% endif %}

{% if is_ayush %}
--------------------------------------------------------------------------------
11. AYUSH Dashavidha Pariksha (दशविध परीक्षा)
--------------------------------------------------------------------------------
- 1. Prakriti (Constitution): {{ ayush.prakriti or "Vata-Pitta Prakriti" }}
- 2. Vikriti (Morbidity): {{ ayush.vikriti or "Vata Vriddhi" }}
- 3. Sara (Tissue Quality): {{ ayush.sara or "Madhyama" }}
- 4. Samhanana (Compactness): {{ ayush.samhanana or "Madhyama" }}
- 5. Pramana (Proportions): {{ ayush.pramana or "Yatha-pramana" }}
- 6. Satmya (Habituation): {{ ayush.satmya or "Oka-satmya" }}
- 7. Sattva (Mental Tone): {{ ayush.sattva or "Madhyama" }}
- 8. Ahara Shakti & Agni: {{ ayush.agni or "Samagni" }}
- 9. Vyayama Shakti (Capacity): {{ ayush.vyayama or "Madhyama" }}
- 10. Vaya (Age Factor): {{ ayush.vaya or "Madhyama Vaya" }}
{% endif %}

--------------------------------------------------------------------------------
12. PHYSICIAN ASSESSMENT & PLAN (EDITABLE)
--------------------------------------------------------------------------------
<!-- PHYSICIAN_EDITABLE_SECTION -->
{{ physician_notes or "Physician Clinical Notes: Patient evaluated in OPD. Routine investigations ordered." }}
<!-- PHYSICIAN_EDITABLE_SECTION_END -->

Consulting Doctor: ________________________   Reg No: ______________________
================================================================================
"""

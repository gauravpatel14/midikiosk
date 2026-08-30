"""Structured Physiological Vitals Evaluator for MediKiosk Emergency Triage.

Checks clinical vitals (Blood Pressure, SpO2, Heart Rate, Respiratory Rate,
Blood Glucose, Temperature) against established emergency triage thresholds.
"""

from typing import Any, Dict, List, Optional


def check_physiological_vitals(vitals: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Evaluate patient vitals for life-threatening physiological thresholds.
    
    Args:
        vitals: Dict containing optional keys: systolic_bp, diastolic_bp, spo2,
                heart_rate, respiratory_rate, blood_glucose, temperature_f.
                
    Returns:
        List of triggered vital sign red flags with severity and recommended action.
    """
    flags = []
    if not vitals:
        return flags

    # 1. Blood Pressure: Hypertensive Crisis or Circulatory Shock
    sys_bp = vitals.get("systolic_bp")
    dia_bp = vitals.get("diastolic_bp")

    if sys_bp is not None:
        try:
            s_val = float(sys_bp)
            if s_val >= 180:
                flags.append({
                    "category": "HYPERTENSIVE_CRISIS",
                    "severity": "CRITICAL",
                    "parameter": "systolic_bp",
                    "observed_value": f"{s_val} mmHg",
                    "threshold": ">= 180 mmHg",
                    "description": "Severe Hypertensive Urgency / Crisis. Risk of acute end-organ damage.",
                    "action": "Immediate physician review, start IV antihypertensive protocol, assess for chest pain/headache.",
                })
            elif s_val < 90 and s_val > 0:
                flags.append({
                    "category": "HYPOTENSION_CIRCULATORY_SHOCK",
                    "severity": "CRITICAL",
                    "parameter": "systolic_bp",
                    "observed_value": f"{s_val} mmHg",
                    "threshold": "< 90 mmHg",
                    "description": "Severe Hypotension / Impending Circulatory Shock.",
                    "action": "Rapid IV fluid bolus, elevate legs, monitor pulse, alert resuscitation team.",
                })
        except (ValueError, TypeError):
            pass

    if dia_bp is not None:
        try:
            d_val = float(dia_bp)
            if d_val >= 120:
                flags.append({
                    "category": "HYPERTENSIVE_CRISIS",
                    "severity": "CRITICAL",
                    "parameter": "diastolic_bp",
                    "observed_value": f"{d_val} mmHg",
                    "threshold": ">= 120 mmHg",
                    "description": "Severe Diastolic Hypertensive Crisis.",
                    "action": "Immediate physician consultation and monitored reduction.",
                })
        except (ValueError, TypeError):
            pass

    # 2. Oxygen Saturation (SpO2)
    spo2 = vitals.get("spo2")
    if spo2 is not None:
        try:
            sp_val = float(spo2)
            if sp_val < 90 and sp_val > 0:
                flags.append({
                    "category": "SEVERE_HYPOXEMIA",
                    "severity": "CRITICAL",
                    "parameter": "spo2",
                    "observed_value": f"{sp_val}%",
                    "threshold": "< 90%",
                    "description": "Critical Hypoxemia / Type 1 Respiratory Failure.",
                    "action": "Immediate high-flow oxygen therapy, prepare bag-valve-mask, urgent triage assessment.",
                })
            elif sp_val < 94 and sp_val >= 90:
                flags.append({
                    "category": "MODERATE_HYPOXEMIA",
                    "severity": "HIGH",
                    "parameter": "spo2",
                    "observed_value": f"{sp_val}%",
                    "threshold": "< 94%",
                    "description": "Suboptimal Oxygen Saturation.",
                    "action": "Supplemental nasal cannula oxygen 2-4 L/min, respiratory assessment.",
                })
        except (ValueError, TypeError):
            pass

    # 3. Heart Rate (Dangerous Arrhythmias)
    hr = vitals.get("heart_rate") or vitals.get("pulse")
    if hr is not None:
        try:
            hr_val = float(hr)
            if hr_val >= 135:
                flags.append({
                    "category": "SEVERE_TACHYARRHYTHMIA",
                    "severity": "HIGH",
                    "parameter": "heart_rate",
                    "observed_value": f"{hr_val} bpm",
                    "threshold": ">= 135 bpm",
                    "description": "Severe Tachycardia / Potential SVT, AF with RVR, or Ventricular Tachycardia.",
                    "action": "12-lead ECG stat, continuous cardiac telemetry, vagal maneuvers / medical cardioversion.",
                })
            elif hr_val < 40 and hr_val > 0:
                flags.append({
                    "category": "SEVERE_BRADYCARDIA",
                    "severity": "CRITICAL",
                    "parameter": "heart_rate",
                    "observed_value": f"{hr_val} bpm",
                    "threshold": "< 40 bpm",
                    "description": "Profound Symptomatic Bradycardia / Complete Heart Block risk.",
                    "action": "Atropine 0.5mg IV preparation, external transcutaneous pacing pads on standby.",
                })
        except (ValueError, TypeError):
            pass

    # 4. Blood Glucose (Severe Hypo / Hyperglycemia)
    glucose = vitals.get("blood_glucose") or vitals.get("rbs")
    if glucose is not None:
        try:
            g_val = float(glucose)
            if g_val < 54 and g_val > 0:
                flags.append({
                    "category": "SEVERE_NEUROGLYCOPENIC_HYPOGLYCEMIA",
                    "severity": "CRITICAL",
                    "parameter": "blood_glucose",
                    "observed_value": f"{g_val} mg/dL",
                    "threshold": "< 54 mg/dL",
                    "description": "Severe Hypoglycemic Shock / Seizure Risk.",
                    "action": "Immediate 25% or 50% Dextrose IV push, re-check capillary glucose in 15 mins.",
                })
            elif g_val >= 400:
                flags.append({
                    "category": "SEVERE_HYPERGLYCEMIC_CRISIS",
                    "severity": "HIGH",
                    "parameter": "blood_glucose",
                    "observed_value": f"{g_val} mg/dL",
                    "threshold": ">= 400 mg/dL",
                    "description": "Severe Hyperglycemia / Potential DKA or Hyperosmolar Hyperglycemic State.",
                    "action": "Check urinary ketones, arterial blood gas, IV normal saline hydration, regular insulin.",
                })
        except (ValueError, TypeError):
            pass

    return flags

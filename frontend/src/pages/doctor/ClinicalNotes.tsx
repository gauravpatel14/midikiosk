import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, User, Mic, Save } from 'lucide-react'

export function ClinicalNotes() {
  const navigate = useNavigate()
  const { id } = useParams()

  return (
    <div className="flex flex-col h-full bg-[#F8FBFC]">
      <header className="bg-[#00447C] p-4 text-white flex justify-between items-center shadow-md z-10 sticky top-0">
        <div className="flex items-center gap-2">
          <button onClick={() => navigate(-1)} className="p-1 -ml-1">
            <ArrowLeft className="w-6 h-6" />
          </button>
          <span className="font-semibold">Clinical Notes</span>
        </div>
        <User className="w-8 h-8 bg-white/20 rounded-full p-1" />
      </header>

      <div className="p-4 flex-1 overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <div className="text-sm font-semibold text-[#00447C] flex items-center gap-2">
            <span className="w-2 h-2 bg-[#008891] rounded-full animate-pulse"></span>
            Documenting Care: Patient {id}, 62M
          </div>
        </div>

        {/* Dictation Box */}
        <div className="bg-white rounded-3xl p-6 shadow-sm border border-[#008891] mb-6 flex flex-col items-center justify-center text-center relative overflow-hidden">
          <div className="absolute top-0 w-full h-1 bg-gradient-to-r from-[#008891] to-blue-300"></div>
          <h3 className="font-bold text-[#00447C] mb-4 text-sm">AI Voice Dictation (English/Hindi)</h3>
          
          <div className="w-16 h-16 bg-[#008891] rounded-full flex items-center justify-center text-white shadow-lg shadow-[#008891]/30 mb-4 cursor-pointer hover:bg-[#00707a] active:scale-95 transition-all">
            <Mic className="w-8 h-8" />
          </div>
          <p className="text-xs text-gray-500 font-medium">
            Tap mic to dictate clinical notes.
          </p>
        </div>

        <div className="space-y-4">
          <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100">
            <h4 className="font-bold text-sm text-[#00447C] mb-2">Subjective (Patient Intake)</h4>
            <textarea 
              className="w-full bg-gray-50 border border-gray-200 rounded-xl p-3 text-sm text-gray-700 min-h-[80px] focus:outline-none focus:ring-2 focus:ring-[#008891]/50"
              defaultValue="Patient complains of right lower quadrant sharp pain for 12 hours. Pain is localized, aggravated by touch or cough. Nausea present."
            />
          </div>

          <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100">
            <h4 className="font-bold text-sm text-[#00447C] mb-2">Objective (Kiosk Automated Vitals)</h4>
            <div className="bg-gray-50 p-3 rounded-xl text-sm text-gray-700">
              Temp: 38.2°C (Elevated) - HR: 88 bpm - Blood Pressure: 135/85 mmHg - SpO2: 98% (Normal). Localized guarding at RLQ.
            </div>
          </div>

          <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100">
            <h4 className="font-bold text-sm text-[#00447C] mb-2">Assessment (AI Suggested)</h4>
            <div className="flex gap-2 flex-wrap mb-3">
              <span className="text-xs bg-red-50 text-red-700 font-bold px-3 py-1.5 rounded-full border border-red-100">Appendicitis (L)</span>
              <span className="text-xs bg-gray-100 text-gray-700 font-bold px-3 py-1.5 rounded-full border border-gray-200">Gastroenteritis</span>
              <span className="text-xs bg-gray-100 text-gray-700 font-bold px-3 py-1.5 rounded-full border border-gray-200">Renal Colic</span>
            </div>
            
            <h4 className="font-bold text-xs text-gray-500 mb-2 uppercase">Plan Quick Actions</h4>
            <div className="flex gap-2 flex-wrap">
              <button className="text-xs bg-[#E5F3F4] text-[#008891] font-bold px-3 py-1.5 rounded-full">Order Ultrasound</button>
              <button className="text-xs bg-[#E5F3F4] text-[#008891] font-bold px-3 py-1.5 rounded-full">Refer Surgery</button>
              <button className="text-xs bg-[#E5F3F4] text-[#008891] font-bold px-3 py-1.5 rounded-full">Prescribe</button>
            </div>
          </div>
          
          <button 
            className="w-full bg-[#00447C] text-white py-4 rounded-2xl font-bold text-lg active:scale-95 transition-transform flex items-center justify-center gap-2 mt-4 shadow-md"
          >
            <Save className="w-5 h-5" />
            SAVE & SIGN ENCOUNTER
          </button>
          
          <button className="w-full text-center py-2 text-gray-400 font-semibold text-sm">
            Save Draft
          </button>
        </div>
      </div>
    </div>
  )
}

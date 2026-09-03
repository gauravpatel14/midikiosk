import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, User, Activity, FileText, ShieldAlert } from 'lucide-react'

export function PatientDetail() {
  const navigate = useNavigate()
  const { id } = useParams()

  return (
    <div className="flex flex-col h-full bg-[#F8FBFC]">
      <header className="bg-[#00447C] p-4 text-white flex justify-between items-center shadow-md z-10 sticky top-0">
        <div className="flex items-center gap-2">
          <button onClick={() => navigate(-1)} className="p-1 -ml-1">
            <ArrowLeft className="w-6 h-6" />
          </button>
          <span className="font-semibold">Clinical Data Viewer</span>
        </div>
        <User className="w-8 h-8 bg-white/20 rounded-full p-1" />
      </header>

      <div className="p-4 flex-1 overflow-y-auto pb-6">
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100 mb-4 flex items-center gap-4">
          <div className="w-12 h-12 bg-[#008891] text-white rounded-full flex items-center justify-center font-bold text-lg">A</div>
          <div>
            <h2 className="font-bold text-xl text-[#00447C]">Patient {id}</h2>
            <p className="text-sm text-gray-500">62 years • Male • ABHA: 14-3897-901</p>
            <div className="flex gap-2 mt-2">
              <span className="text-[10px] bg-red-50 text-red-600 font-bold px-2 py-0.5 rounded border border-red-100">CRITICAL</span>
              <span className="text-[10px] bg-gray-100 text-gray-600 font-bold px-2 py-0.5 rounded">Wait: 12 min</span>
            </div>
          </div>
        </div>

        <div className="mb-6">
          <div className="flex justify-between items-center mb-2">
            <h3 className="font-bold text-[#00447C] flex items-center gap-2">
              <Activity className="w-4 h-4 text-[#008891]" />
              AI Clinical Summary
            </h3>
            <span className="text-xs text-gray-400 font-medium">Auto-generated</span>
          </div>
          <div className="bg-[#E5F3F4] rounded-2xl p-4 text-sm text-[#00447C] leading-relaxed border border-[#008891]/20">
            62-year-old male presenting with acute onset severe right lower quadrant abdominal pain, progressive, worsening over the past 12 hours. Accompanied by nausea and one episode of non-bilious emesis. Patient is febrile (38.2°C) with localized rebound tenderness. Clinical picture is highly suspicious for acute appendicitis.
            
            <div className="mt-4 flex gap-2">
              <button className="flex-1 bg-white border border-[#008891] text-[#008891] py-2 rounded-xl font-bold text-xs">Edit Summary</button>
              <button className="flex-1 bg-[#008891] text-white py-2 rounded-xl font-bold text-xs">Confirm Data</button>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          {/* Chief Complaint */}
          <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
            <h4 className="font-bold text-gray-700 mb-2 flex items-center justify-between">
              Chief Complaint
              <span className="text-gray-400 text-xl leading-none">+</span>
            </h4>
            <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded-xl italic">
              "Severe pain in the lower right stomach area, started last night."
            </p>
          </div>

          {/* History */}
          <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
            <h4 className="font-bold text-gray-700 mb-2">History of Present Illness</h4>
            <p className="text-sm text-gray-600">
              Pain initiated peri-umbilical approx 12 hrs ago, migrating to RLQ. Worsens with movement. Denies diarrhea, dysuria.
            </p>
          </div>

          {/* Past Med History */}
          <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
            <h4 className="font-bold text-gray-700 mb-2">Past Medical History</h4>
            <ul className="text-sm text-gray-600 list-disc pl-4 space-y-1">
              <li>Mild Asthma (childhood, resolved)</li>
              <li>No prior abdominal surgeries</li>
            </ul>
          </div>

          {/* Allergies */}
          <div className="bg-white rounded-2xl p-4 shadow-sm border border-red-100">
            <h4 className="font-bold text-red-600 mb-2 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4" /> Allergies & Medications
            </h4>
            <div className="flex gap-2">
              <span className="text-xs bg-red-50 text-red-700 font-bold px-2 py-1 rounded">Sulfa Drugs (Rash)</span>
              <span className="text-xs bg-gray-100 text-gray-700 font-bold px-2 py-1 rounded">Multivitamin Daily</span>
            </div>
          </div>

          {/* Vitals */}
          <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 mb-4">
            <h4 className="font-bold text-gray-700 mb-3">Realtime Vitals Chart</h4>
            <div className="flex justify-between divide-x divide-gray-100">
              <div className="px-2 text-center flex-1">
                <div className="text-2xl font-bold text-red-500">38.2°C</div>
                <div className="text-[10px] text-gray-500 font-medium uppercase mt-1">High</div>
              </div>
              <div className="px-2 text-center flex-1">
                <div className="text-2xl font-bold text-[#00447C]">88 bpm</div>
                <div className="text-[10px] text-gray-500 font-medium uppercase mt-1">Normal</div>
              </div>
              <div className="px-2 text-center flex-1">
                <div className="text-2xl font-bold text-[#008891]">98%</div>
                <div className="text-[10px] text-gray-500 font-medium uppercase mt-1">Normal</div>
              </div>
            </div>
          </div>
          
          <button 
            onClick={() => navigate(`/doctor/notes/${id}`)}
            className="w-full bg-[#00447C] text-white py-4 rounded-2xl font-bold text-lg active:scale-95 transition-transform flex items-center justify-center gap-2 mt-4 shadow-lg"
          >
            <FileText className="w-5 h-5" />
            Add Clinical Notes
          </button>
        </div>
      </div>
    </div>
  )
}
